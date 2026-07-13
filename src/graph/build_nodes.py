from __future__ import annotations

from pathlib import Path

import polars as pl

from src.graph.pathway_projection import (
    DEFAULT_MAX_PATHWAYS_PER_CANCER,
    select_enriched_pathways,
    selected_pathway_memberships,
)


def build_graph_nodes_stub() -> list[dict[str, str]]:
    return [
        {"node_id": "TCGA-BRCA", "node_label": "CancerType", "name": "Breast invasive carcinoma"},
        {"node_id": "ENSG00000141510", "node_label": "Gene", "name": "TP53"},
    ]


def _read_or_empty(path: Path, schema: dict[str, pl.DataType]) -> pl.DataFrame:
    if path.exists():
        return pl.read_parquet(path)
    return pl.DataFrame(schema=schema)


def build_graph_nodes_table(
    silver_dir: str | Path = "data/silver",
    gold_dir: str | Path = "data/gold",
    output_path: str | Path = "data/gold/gold_graph_nodes.parquet",
    pathway_gmt_path: str | Path = "data/bronze/reference/pathways/reactome_pathways.gmt",
    max_pathways_per_cancer: int = DEFAULT_MAX_PATHWAYS_PER_CANCER,
) -> dict[str, object]:
    silver_root = Path(silver_dir)
    gold_root = Path(gold_dir)

    projects = _read_or_empty(
        silver_root / "silver_projects.parquet",
        {"project_id": pl.Utf8, "primary_site": pl.Utf8, "disease_type": pl.Utf8},
    )
    genes = _read_or_empty(
        gold_root / "gold_mutation_frequency_by_gene.parquet",
        {
            "gene_symbol": pl.Utf8,
            "cancer_type": pl.Utf8,
            "mutated_sample_count": pl.Int64,
            "total_profiled_sample_count": pl.Int64,
            "mutation_frequency": pl.Float64,
            "top_variant_classification": pl.Utf8,
        },
    )
    samples = _read_or_empty(
        silver_root / "silver_samples.parquet",
        {"project_id": pl.Utf8, "case_id": pl.Utf8, "sample_id": pl.Utf8, "sample_type": pl.Utf8},
    )
    patients = _read_or_empty(
        silver_root / "silver_patients.parquet",
        {"project_id": pl.Utf8, "case_id": pl.Utf8, "submitter_id": pl.Utf8},
    )
    gtex = _read_or_empty(
        silver_root / "silver_expression_gtex.parquet",
        {
            "gtex_sample_id": pl.Utf8,
            "tissue_site": pl.Utf8,
            "tissue_detail": pl.Utf8,
            "gene_id": pl.Utf8,
            "gene_symbol": pl.Utf8,
            "expression_value": pl.Float64,
            "expression_unit": pl.Utf8,
            "log2_expression": pl.Float64,
            "source_version": pl.Utf8,
            "data_origin": pl.Utf8,
            "ingested_at": pl.Utf8,
        },
    )
    selected_pathways = select_enriched_pathways(
        gold_root / "gold_pathway_enrichment.parquet",
        max_pathways_per_cancer=max_pathways_per_cancer,
    )
    pathway_memberships = selected_pathway_memberships(
        selected_pathways,
        pathway_gmt_path=pathway_gmt_path,
    )

    cancer_nodes = (
        projects.select(
            [
                pl.col("project_id").alias("node_id"),
                pl.lit("CancerType").alias("node_label"),
                pl.col("project_id").alias("name"),
                pl.col("primary_site"),
                pl.lit("TCGA").alias("source"),
            ]
        )
        if not projects.is_empty()
        else pl.DataFrame(schema={"node_id": pl.Utf8, "node_label": pl.Utf8, "name": pl.Utf8, "primary_site": pl.Utf8, "source": pl.Utf8})
    )

    gene_symbols = pl.concat(
        [
            (
                genes.select([pl.col("gene_symbol").cast(pl.Utf8), pl.lit("TCGA").alias("gene_source")])
                if not genes.is_empty()
                else pl.DataFrame(schema={"gene_symbol": pl.Utf8, "gene_source": pl.Utf8})
            ),
            (
                gtex.select([pl.col("gene_symbol").cast(pl.Utf8), pl.lit("GTEx").alias("gene_source")])
                if not gtex.is_empty()
                else pl.DataFrame(schema={"gene_symbol": pl.Utf8, "gene_source": pl.Utf8})
            ),
            (
                pathway_memberships.select(
                    [pl.col("gene_symbol").cast(pl.Utf8), pl.lit("Reactome").alias("gene_source")]
                )
                if not pathway_memberships.is_empty()
                else pl.DataFrame(schema={"gene_symbol": pl.Utf8, "gene_source": pl.Utf8})
            ),
        ],
        how="vertical",
    ).filter(pl.col("gene_symbol").is_not_null() & (pl.col("gene_symbol") != ""))
    gene_symbols = gene_symbols.group_by("gene_symbol").agg(
        pl.col("gene_source").unique().sort().str.join("/").alias("gene_source")
    )
    gene_nodes = gene_symbols.select(
        [
            pl.concat_str([pl.lit("GENE:"), pl.col("gene_symbol")]).alias("node_id"),
            pl.lit("Gene").alias("node_label"),
            pl.col("gene_symbol").alias("name"),
            pl.lit("Unknown").alias("primary_site"),
            pl.col("gene_source").alias("source"),
        ]
    )

    pathway_nodes = (
        selected_pathways.select(
            [
                pl.concat_str([pl.lit("PATHWAY:"), pl.col("pathway_id")]).alias("node_id"),
                pl.lit("Pathway").alias("node_label"),
                pl.col("pathway_name").alias("name"),
                pl.lit("Multi").alias("primary_site"),
                pl.col("pathway_source").alias("source"),
            ]
        ).unique(subset=["node_id"])
        if not selected_pathways.is_empty()
        else pl.DataFrame(
            schema={
                "node_id": pl.Utf8,
                "node_label": pl.Utf8,
                "name": pl.Utf8,
                "primary_site": pl.Utf8,
                "source": pl.Utf8,
            }
        )
    )

    sample_nodes = (
        samples.select(
            [
                pl.concat_str([pl.lit("SAMPLE:"), pl.col("sample_id")]).alias("node_id"),
                pl.lit("Sample").alias("node_label"),
                pl.col("sample_id").alias("name"),
                pl.col("project_id").alias("primary_site"),
                pl.lit("TCGA").alias("source"),
            ]
        ).unique(subset=["node_id"])
        if not samples.is_empty()
        else pl.DataFrame(schema={"node_id": pl.Utf8, "node_label": pl.Utf8, "name": pl.Utf8, "primary_site": pl.Utf8, "source": pl.Utf8})
    )

    patient_nodes = (
        patients.select(
            [
                pl.concat_str([pl.lit("PATIENT:"), pl.col("case_id")]).alias("node_id"),
                pl.lit("Patient").alias("node_label"),
                pl.col("case_id").alias("name"),
                pl.col("project_id").alias("primary_site"),
                pl.lit("TCGA").alias("source"),
            ]
        ).unique(subset=["node_id"])
        if not patients.is_empty()
        else pl.DataFrame(schema={"node_id": pl.Utf8, "node_label": pl.Utf8, "name": pl.Utf8, "primary_site": pl.Utf8, "source": pl.Utf8})
    )

    tissue_nodes = (
        gtex.select(
            [
                pl.concat_str([pl.lit("TISSUE:"), pl.col("tissue_site")]).alias("node_id"),
                pl.lit("Tissue").alias("node_label"),
                pl.col("tissue_site").alias("name"),
                pl.col("tissue_site").alias("primary_site"),
                pl.lit("GTEx").alias("source"),
            ]
        ).unique(subset=["node_id"])
        if not gtex.is_empty()
        else pl.DataFrame(schema={"node_id": pl.Utf8, "node_label": pl.Utf8, "name": pl.Utf8, "primary_site": pl.Utf8, "source": pl.Utf8})
    )

    dataset_nodes = pl.DataFrame(
        [
            {"node_id": "DATASET:TCGA", "node_label": "Dataset", "name": "TCGA", "primary_site": "Multi", "source": "TCGA"},
            {"node_id": "DATASET:GTEX", "node_label": "Dataset", "name": "GTEx", "primary_site": "Multi", "source": "GTEx"},
        ]
    )

    nodes = pl.concat(
        [cancer_nodes, gene_nodes, pathway_nodes, sample_nodes, patient_nodes, tissue_nodes, dataset_nodes],
        how="vertical",
    ).unique(subset=["node_id", "node_label"])

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    nodes.write_parquet(out)
    return {"path": str(out), "count": int(nodes.height)}


def load_graph_nodes(
    graph_nodes_path: str | Path = "data/gold/gold_graph_nodes.parquet",
) -> list[dict[str, object]]:
    path = Path(graph_nodes_path)
    if not path.exists():
        return build_graph_nodes_stub()
    df = pl.read_parquet(path)
    if df.is_empty():
        return build_graph_nodes_stub()
    return df.to_dicts()
