from __future__ import annotations

import json
from pathlib import Path

import polars as pl

from src.operations.demo_check import run_demo_check, write_demo_check_report


def _write_demo_fixture(root: Path, *, tcga_origin: str = "data/bronze/tcga/TCGA-BRCA/expression/file.tsv") -> None:
    silver = root / "data" / "silver"
    gold = root / "data" / "gold"
    reports = root / "outputs" / "reports"
    neo4j = root / "outputs" / "graph_exports" / "neo4j"
    graphify = root / "outputs" / "graph_exports" / "graphify"
    for path in [silver, gold, reports, neo4j, graphify]:
        path.mkdir(parents=True, exist_ok=True)

    pl.DataFrame(
        {
            "project_id": ["TCGA-BRCA"],
            "case_id": ["case-1"],
            "sample_id": ["sample-1"],
            "sample_type": ["Primary Tumor"],
        }
    ).write_parquet(silver / "silver_samples.parquet")
    pl.DataFrame(
        {
            "project_id": ["TCGA-BRCA"],
            "case_id": ["case-1"],
            "sample_id": ["sample-1"],
            "sample_type": ["Primary Tumor"],
            "gene_id": ["ENSG00000141510"],
            "gene_symbol": ["TP53"],
            "expression_value": [10.0],
            "expression_unit": ["TPM"],
            "log2_expression": [3.459],
            "pipeline_workflow": ["STAR - Counts"],
            "data_origin": [tcga_origin],
            "ingested_at": ["2026-05-28T00:00:00Z"],
        }
    ).write_parquet(silver / "silver_expression_tcga.parquet")
    pl.DataFrame(
        {
            "gtex_sample_id": ["gtex-1"],
            "tissue_site": ["Breast - Mammary Tissue"],
            "tissue_detail": ["Breast - Mammary Tissue"],
            "gene_id": ["ENSG00000141510"],
            "gene_symbol": ["TP53"],
            "expression_value": [4.0],
            "expression_unit": ["TPM"],
            "log2_expression": [2.321],
            "source_version": ["v8"],
            "data_origin": ["data/bronze/gtex/expression/gtex.tsv"],
            "ingested_at": ["2026-05-28T00:00:00Z"],
        }
    ).write_parquet(silver / "silver_expression_gtex.parquet")
    pl.DataFrame(
        {
            "project_id": ["TCGA-BRCA"],
            "case_id": ["case-1"],
            "sample_id": ["sample-1"],
            "gene_id": ["ENSG00000141510"],
            "gene_symbol": ["TP53"],
            "variant_classification": ["Missense_Mutation"],
            "variant_type": ["SNP"],
            "chromosome": ["17"],
            "start_position": [7674220],
            "end_position": [7674220],
            "reference_allele": ["C"],
            "tumor_seq_allele": ["T"],
            "data_origin": ["data/bronze/tcga/TCGA-BRCA/mutations/file.maf.gz"],
            "ingested_at": ["2026-05-28T00:00:00Z"],
        }
    ).write_parquet(silver / "silver_mutations.parquet")

    pl.DataFrame(
        [
            {
                "tcga_project_count": 1,
                "tcga_patient_count": 1,
                "tcga_sample_count": 1,
                "tcga_file_count": 2,
                "gtex_expression_sample_count": 1,
                "tcga_expression_row_count": 1,
                "gtex_expression_row_count": 1,
                "gene_count": 1,
                "mutation_record_count": 1,
                "generated_at": "2026-05-28T00:00:00Z",
            }
        ]
    ).write_parquet(gold / "gold_cohort_summary.parquet")
    pl.DataFrame(
        {
            "gene_symbol": ["TP53"],
            "cancer_type": ["TCGA-BRCA"],
            "mutated_sample_count": [1],
            "total_profiled_sample_count": [1],
            "mutation_frequency": [1.0],
            "top_variant_classification": ["Missense_Mutation"],
        }
    ).write_parquet(gold / "gold_mutation_frequency_by_gene.parquet")
    pl.DataFrame(
        {
            "node_id": ["GENE:TP53", "CANCER:TCGA-BRCA"],
            "node_label": ["Gene", "CancerType"],
            "name": ["TP53", "TCGA-BRCA"],
            "primary_site": ["NA", "Breast"],
            "source": ["TCGA", "TCGA"],
        }
    ).write_parquet(gold / "gold_graph_nodes.parquet")
    pl.DataFrame(
        {
            "edge_id": ["edge-1"],
            "source_node_id": ["GENE:TP53"],
            "target_node_id": ["CANCER:TCGA-BRCA"],
            "edge_type": ["MUTATED_IN_CANCER"],
            "weight": [1.0],
            "evidence_source": ["gold_mutation_frequency_by_gene"],
        }
    ).write_parquet(gold / "gold_graph_edges.parquet")
    pl.DataFrame(
        {
            "node_id": ["CANCER:TCGA-BRCA", "GENE:TP53"],
            "node_label": ["CancerType", "Gene"],
            "name": ["TCGA-BRCA", "TP53"],
            "total_degree": [1, 1],
            "in_degree": [1, 0],
            "out_degree": [0, 1],
            "weighted_degree": [1.0, 1.0],
            "edge_type_count": [1, 1],
            "degree_rank": [1, 2],
        }
    ).write_parquet(gold / "gold_graph_node_metrics.parquet")

    quality = {
        "status": "passed_with_warnings",
        "pipeline_run_id": "demo-run",
        "generated_at": "2026-05-28T00:00:00Z",
        "checks": [{"check_name": "x", "status": "passed", "failed_rows": 0}],
    }
    (reports / "silver_data_quality_report.json").write_text(json.dumps(quality), encoding="utf-8")
    (reports / "graph_metrics_report.json").write_text(
        json.dumps({"status": "passed", "node_count": 2, "edge_count": 1, "metric_rows": 2}),
        encoding="utf-8",
    )
    (reports / "gdc_ingestion_audit.json").write_text(json.dumps({"source_mode": "live"}), encoding="utf-8")

    (neo4j / "nodes.csv").write_text("node_id,node_label,name\nGENE:TP53,Gene,TP53\n", encoding="utf-8")
    (neo4j / "edges.csv").write_text("edge_id,source_node_id,target_node_id\nedge-1,GENE:TP53,CANCER:TCGA-BRCA\n", encoding="utf-8")
    (neo4j / "import_bulk.cypher").write_text("LOAD CSV WITH HEADERS FROM 'file:///nodes.csv' AS row RETURN row;\n", encoding="utf-8")
    (graphify / "nodes.csv").write_text("node_id,node_label,name\nGENE:TP53,Gene,TP53\n", encoding="utf-8")
    (graphify / "edges.csv").write_text("edge_id,source_node_id,target_node_id\nedge-1,GENE:TP53,CANCER:TCGA-BRCA\n", encoding="utf-8")


def test_run_demo_check_passes_with_complete_fixture(tmp_path: Path, monkeypatch) -> None:
    _write_demo_fixture(tmp_path)
    monkeypatch.chdir(tmp_path)

    payload = run_demo_check(strict_no_stub=True)

    assert payload["status"] == "passed"
    assert payload["failed_count"] == 0
    assert payload["check_count"] > 10


def test_run_demo_check_strict_rejects_stub_origin(tmp_path: Path, monkeypatch) -> None:
    _write_demo_fixture(tmp_path, tcga_origin="stub")
    monkeypatch.chdir(tmp_path)

    payload = run_demo_check(strict_no_stub=True, include_dashboard=False, include_api=False)

    assert payload["status"] == "failed"
    failed = {check["check_name"] for check in payload["checks"] if check["status"] == "failed"}
    assert "strict_tcga_expression_no_stub" in failed


def test_write_demo_check_report(tmp_path: Path) -> None:
    output = write_demo_check_report({"status": "passed", "checks": []}, tmp_path / "demo.json")

    assert output.exists()
    assert json.loads(output.read_text(encoding="utf-8"))["status"] == "passed"
