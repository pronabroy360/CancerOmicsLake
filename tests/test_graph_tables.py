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
    pl.DataFrame(
        {
            "cancer_type": ["TCGA-BRCA"],
            "candidate_set": ["prioritized"],
            "pathway_id": ["R-HSA-1640170"],
            "pathway_name": ["Cell Cycle"],
            "pathway_source": ["Reactome"],
            "background_gene_count": [100],
            "candidate_gene_count": [10],
            "pathway_gene_count": [5],
            "overlap_gene_count": [3],
            "overlap_genes": ["CCNB1,CDK1,TP53"],
            "enrichment_ratio": [3.0],
            "odds_ratio": [4.0],
            "p_value": [0.001],
            "fdr_q_value": [0.01],
            "enrichment_score": [0.9],
            "enrichment_tier": ["fdr_enriched"],
            "pathway_caveat": ["Hypothesis generation only."],
        }
    ).write_parquet(gold_dir / "gold_pathway_enrichment.parquet")
    pathway_gmt = tmp_path / "reactome_pathways.gmt"
    pathway_gmt.write_text(
        "Cell Cycle\tR-HSA-1640170\tTP53\tCDK1\tCCNB1\tMDM2\tCDKN1A\n",
        encoding="utf-8",
    )

    node_summary = build_graph_nodes_table(
        silver_dir=silver_dir,
        gold_dir=gold_dir,
        output_path=gold_dir / "gold_graph_nodes.parquet",
        pathway_gmt_path=pathway_gmt,
    )
    edge_summary = build_graph_edges_table(
        silver_dir=silver_dir,
        gold_dir=gold_dir,
        output_path=gold_dir / "gold_graph_edges.parquet",
        pathway_gmt_path=pathway_gmt,
    )

    assert node_summary["count"] > 0
    assert edge_summary["count"] > 0

    nodes = load_graph_nodes(gold_dir / "gold_graph_nodes.parquet")
    edges = load_graph_edges(gold_dir / "gold_graph_edges.parquet")
    assert any(row["node_label"] == "CancerType" for row in nodes)
    assert any(row["node_id"] == "GENE:EGFR" for row in nodes)
    assert any(row["node_id"] == "GENE:CDKN1A" for row in nodes)
    assert any(row["node_id"] == "PATHWAY:R-HSA-1640170" for row in nodes)
    assert next(row for row in nodes if row["node_id"] == "GENE:CDKN1A")["source"] == "Reactome"
    assert any(row["edge_type"] == "MUTATED_IN_CANCER" for row in edges)
    assert any(row["edge_type"] == "EXPRESSED_IN_TISSUE" for row in edges)
    assert any(row["edge_type"] == "ENRICHED_IN_CANCER" for row in edges)
    assert any(row["edge_type"] == "MEMBER_OF_PATHWAY" for row in edges)


def test_load_graph_tables_fallback_to_stub(tmp_path: Path) -> None:
    nodes = load_graph_nodes(tmp_path / "missing_nodes.parquet")
    edges = load_graph_edges(tmp_path / "missing_edges.parquet")
    assert len(nodes) > 0
    assert len(edges) > 0
