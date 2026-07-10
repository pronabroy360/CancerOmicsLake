from pathlib import Path

import polars as pl

from src.graph.build_edges import build_graph_edges_table, load_graph_edges
from src.graph.build_nodes import build_graph_nodes_table, load_graph_nodes


def test_build_graph_nodes_and_edges_from_silver_gold(tmp_path: Path) -> None:
    silver_dir = tmp_path / "silver"
    gold_dir = tmp_path / "gold"
    silver_dir.mkdir(parents=True, exist_ok=True)
    gold_dir.mkdir(parents=True, exist_ok=True)

    pl.DataFrame(
        {
            "project_id": ["TCGA-BRCA"],
            "primary_site": ["Breast"],
            "disease_type": ["Adeno"],
        }
    ).write_parquet(silver_dir / "silver_projects.parquet")
    pl.DataFrame(
        {
            "project_id": ["TCGA-BRCA"],
            "case_id": ["case-1"],
            "submitter_id": ["sub-1"],
        }
    ).write_parquet(silver_dir / "silver_patients.parquet")
    pl.DataFrame(
        {
            "project_id": ["TCGA-BRCA"],
            "case_id": ["case-1"],
            "sample_id": ["sample-1"],
            "sample_type": ["Primary Tumor"],
        }
    ).write_parquet(silver_dir / "silver_samples.parquet")
    pl.DataFrame(
        {
            "gtex_sample_id": ["GTEX-1"],
            "tissue_site": ["Breast - Mammary Tissue"],
            "tissue_detail": ["Breast - Mammary Tissue"],
            "gene_id": ["ENSG2"],
            "gene_symbol": ["EGFR"],
            "expression_value": [1.0],
            "expression_unit": ["TPM"],
            "log2_expression": [1.0],
            "source_version": ["v8"],
            "data_origin": ["stub"],
            "ingested_at": ["x"],
        }
    ).write_parquet(silver_dir / "silver_expression_gtex.parquet")
    pl.DataFrame(
        {
            "gene_symbol": ["TP53"],
            "cancer_type": ["TCGA-BRCA"],
            "mutated_sample_count": [5],
            "total_profiled_sample_count": [20],
            "mutation_frequency": [0.25],
            "top_variant_classification": ["Missense_Mutation"],
        }
    ).write_parquet(gold_dir / "gold_mutation_frequency_by_gene.parquet")

    node_summary = build_graph_nodes_table(
        silver_dir=silver_dir,
        gold_dir=gold_dir,
        output_path=gold_dir / "gold_graph_nodes.parquet",
    )
    edge_summary = build_graph_edges_table(
        silver_dir=silver_dir,
        gold_dir=gold_dir,
        output_path=gold_dir / "gold_graph_edges.parquet",
    )

    assert node_summary["count"] > 0
    assert edge_summary["count"] > 0

    nodes = load_graph_nodes(gold_dir / "gold_graph_nodes.parquet")
    edges = load_graph_edges(gold_dir / "gold_graph_edges.parquet")
    assert any(row["node_label"] == "CancerType" for row in nodes)
    assert any(row["node_id"] == "GENE:EGFR" for row in nodes)
    assert any(row["edge_type"] == "MUTATED_IN_CANCER" for row in edges)
    assert any(row["edge_type"] == "EXPRESSED_IN_TISSUE" for row in edges)


def test_load_graph_tables_fallback_to_stub(tmp_path: Path) -> None:
    nodes = load_graph_nodes(tmp_path / "missing_nodes.parquet")
    edges = load_graph_edges(tmp_path / "missing_edges.parquet")
    assert len(nodes) > 0
    assert len(edges) > 0
