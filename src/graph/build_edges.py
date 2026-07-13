from __future__ import annotations

from pathlib import Path

import polars as pl

from src.graph.pathway_projection import (
    DEFAULT_MAX_PATHWAYS_PER_CANCER,
    select_enriched_pathways,
    selected_pathway_memberships,
)


def build_graph_edges_stub() -> list[dict[str, str]]:
    return [
        {
            "edge_id": "edge-1",
            "source_node_id": "ENSG00000141510",
            "target_node_id": "TCGA-BRCA",
            "edge_type": "OVEREXPRESSED_IN",
            "weight": "1.0",
            "evidence_source": "stub",
        }
    ]


def _read_or_empty(path: Path, schema: dict[str, pl.DataType]) -> pl.DataFrame:
    if path.exists():
        return pl.read_parquet(path)
    return pl.DataFrame(schema=schema)


def build_graph_edges_table(
    silver_dir: str | Path = "data/silver",
    gold_dir: str | Path = "data/gold",
    output_path: str | Path = "data/gold/gold_graph_edges.parquet",
    pathway_gmt_path: str | Path = "data/bronze/reference/pathways/reactome_pathways.gmt",
    max_pathways_per_cancer: int = DEFAULT_MAX_PATHWAYS_PER_CANCER,
) -> dict[str, object]:
    silver_root = Path(silver_dir)
    gold_root = Path(gold_dir)

    samples = _read_or_empty(
        silver_root / "silver_samples.parquet",
        {"project_id": pl.Utf8, "case_id": pl.Utf8, "sample_id": pl.Utf8, "sample_type": pl.Utf8},
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
    mutation_by_gene = _read_or_empty(
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
    selected_pathways = select_enriched_pathways(
        gold_root / "gold_pathway_enrichment.parquet",
        max_pathways_per_cancer=max_pathways_per_cancer,
    )
    pathway_memberships = selected_pathway_memberships(
        selected_pathways,
        pathway_gmt_path=pathway_gmt_path,
    )

    has_sample = (
        samples.select(
            [
                pl.concat_str([pl.lit("HAS_SAMPLE:"), pl.col("case_id"), pl.lit(":"), pl.col("sample_id")]).alias("edge_id"),
                pl.concat_str([pl.lit("PATIENT:"), pl.col("case_id")]).alias("source_node_id"),
                pl.concat_str([pl.lit("SAMPLE:"), pl.col("sample_id")]).alias("target_node_id"),
                pl.lit("HAS_SAMPLE").alias("edge_type"),
                pl.lit(1.0).alias("weight"),
                pl.lit("TCGA").alias("evidence_source"),
            ]
        )
        if not samples.is_empty()
        else pl.DataFrame(
            schema={
                "edge_id": pl.Utf8,
                "source_node_id": pl.Utf8,
                "target_node_id": pl.Utf8,
                "edge_type": pl.Utf8,
                "weight": pl.Float64,
                "evidence_source": pl.Utf8,
            }
        )
    )

    belongs_to_cancer = (
        samples.select(
            [
                pl.concat_str([pl.lit("BELONGS_TO_CANCER:"), pl.col("sample_id"), pl.lit(":"), pl.col("project_id")]).alias("edge_id"),
                pl.concat_str([pl.lit("SAMPLE:"), pl.col("sample_id")]).alias("source_node_id"),
                pl.col("project_id").alias("target_node_id"),
                pl.lit("BELONGS_TO_CANCER").alias("edge_type"),
                pl.lit(1.0).alias("weight"),
                pl.lit("TCGA").alias("evidence_source"),
            ]
        )
        if not samples.is_empty()
        else has_sample.head(0)
    )

    expressed_in_tissue = (
        gtex.group_by(["gene_symbol", "tissue_site"])
        .agg(pl.col("log2_expression").mean().alias("mean_log2_expression"))
        .select(
            [
                pl.concat_str([pl.lit("EXPRESSED_IN_TISSUE:"), pl.col("gene_symbol"), pl.lit(":"), pl.col("tissue_site")]).alias("edge_id"),
                pl.concat_str([pl.lit("GENE:"), pl.col("gene_symbol")]).alias("source_node_id"),
                pl.concat_str([pl.lit("TISSUE:"), pl.col("tissue_site")]).alias("target_node_id"),
                pl.lit("EXPRESSED_IN_TISSUE").alias("edge_type"),
                pl.col("mean_log2_expression").cast(pl.Float64).alias("weight"),
                pl.lit("GTEx").alias("evidence_source"),
            ]
        )
        if not gtex.is_empty()
        else has_sample.head(0)
    )

    mutated_in_cancer = (
        mutation_by_gene.select(
            [
                pl.concat_str([pl.lit("MUTATED_IN_CANCER:"), pl.col("gene_symbol"), pl.lit(":"), pl.col("cancer_type")]).alias("edge_id"),
                pl.concat_str([pl.lit("GENE:"), pl.col("gene_symbol")]).alias("source_node_id"),
                pl.col("cancer_type").alias("target_node_id"),
                pl.lit("MUTATED_IN_CANCER").alias("edge_type"),
                pl.col("mutation_frequency").cast(pl.Float64).alias("weight"),
                pl.lit("TCGA").alias("evidence_source"),
            ]
        )
        if not mutation_by_gene.is_empty()
        else has_sample.head(0)
    )

    enriched_in_cancer = (
        selected_pathways.select(
            [
                pl.concat_str(
                    [
                        pl.lit("ENRICHED_IN_CANCER:"),
                        pl.col("pathway_id"),
                        pl.lit(":"),
                        pl.col("cancer_type"),
                    ]
                ).alias("edge_id"),
                pl.concat_str([pl.lit("PATHWAY:"), pl.col("pathway_id")]).alias("source_node_id"),
                pl.col("cancer_type").alias("target_node_id"),
                pl.lit("ENRICHED_IN_CANCER").alias("edge_type"),
                pl.col("enrichment_score").cast(pl.Float64).alias("weight"),
                pl.concat_str(
                    [pl.col("pathway_source"), pl.lit(":ORA:"), pl.col("candidate_set")]
                ).alias("evidence_source"),
            ]
        )
        if not selected_pathways.is_empty()
        else has_sample.head(0)
    )

    member_of_pathway = (
        pathway_memberships.select(
            [
                pl.concat_str(
                    [pl.lit("MEMBER_OF_PATHWAY:"), pl.col("gene_symbol"), pl.lit(":"), pl.col("pathway_id")]
                ).alias("edge_id"),
                pl.concat_str([pl.lit("GENE:"), pl.col("gene_symbol")]).alias("source_node_id"),
                pl.concat_str([pl.lit("PATHWAY:"), pl.col("pathway_id")]).alias("target_node_id"),
                pl.lit("MEMBER_OF_PATHWAY").alias("edge_type"),
                pl.lit(1.0).alias("weight"),
                pl.col("pathway_source").alias("evidence_source"),
            ]
        )
        if not pathway_memberships.is_empty()
        else has_sample.head(0)
    )

    edges = pl.concat(
        [
            has_sample,
            belongs_to_cancer,
            expressed_in_tissue,
            mutated_in_cancer,
            enriched_in_cancer,
            member_of_pathway,
        ],
        how="vertical",
    ).unique(subset=["edge_id"])

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    edges.write_parquet(out)
    return {"path": str(out), "count": int(edges.height)}


def load_graph_edges(
    graph_edges_path: str | Path = "data/gold/gold_graph_edges.parquet",
) -> list[dict[str, object]]:
    path = Path(graph_edges_path)
    if not path.exists():
        return build_graph_edges_stub()
    df = pl.read_parquet(path)
    if df.is_empty():
        return build_graph_edges_stub()
    return df.to_dicts()
