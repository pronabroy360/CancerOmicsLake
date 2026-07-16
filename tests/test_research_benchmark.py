from pathlib import Path

import polars as pl
import pytest

from src.operations.research_benchmark import run_research_benchmark


def _write_benchmark_fixture(gold: Path) -> None:
    gold.mkdir()
    pl.DataFrame({"tcga_project_count": [3]}).write_parquet(gold / "gold_cohort_summary.parquet")
    pl.DataFrame(
        {
            "gene_symbol": ["TP53"],
            "cancer_type": ["TCGA-LUAD"],
            "mutation_frequency": [0.5],
        }
    ).write_parquet(gold / "gold_mutation_frequency_by_gene.parquet")
    pl.DataFrame(
        {
            "cancer_type": ["TCGA-LUAD"],
            "gene_symbol": ["TP53"],
            "consensus_score": [0.8],
            "consensus_decision": ["prioritized"],
        }
    ).write_parquet(gold / "gold_consensus_candidate_genes.parquet")
    pl.DataFrame(
        {
            "cancer_type": ["TCGA-LUAD"],
            "fdr_q_value": [0.01],
        }
    ).write_parquet(gold / "gold_pathway_enrichment.parquet")
    pl.DataFrame(
        {
            "edge_type": ["MUTATED_IN_CANCER"],
        }
    ).write_parquet(gold / "gold_graph_edges.parquet")
    pl.DataFrame(
        {
            "cancer_type": ["TCGA-LUAD"],
            "gene_symbol": ["TP53"],
            "log2_fold_change": [1.2],
        }
    ).write_parquet(gold / "gold_tumor_vs_normal_expression.parquet")


def test_run_research_benchmark_writes_typed_workload_report(tmp_path: Path) -> None:
    gold = tmp_path / "gold"
    report = tmp_path / "benchmark.json"
    _write_benchmark_fixture(gold)

    payload = run_research_benchmark(gold, report, repeats=3, warmups=1, threads=1)

    assert payload["status"] == "passed"
    assert report.exists()
    assert len(payload["datasets"]) == 6
    assert len(payload["workloads"]) == 6
    assert all(workload["status"] == "passed" for workload in payload["workloads"])
    assert all(workload["latency_ms"]["median"] >= 0 for workload in payload["workloads"])
    assert all(len(workload["query_sha256"]) == 64 for workload in payload["workloads"])
    assert payload["environment"]["threads"] == 1


def test_run_research_benchmark_reports_missing_inputs_as_warnings(tmp_path: Path) -> None:
    gold = tmp_path / "gold"
    gold.mkdir()
    pl.DataFrame({"tcga_project_count": [3]}).write_parquet(gold / "gold_cohort_summary.parquet")

    payload = run_research_benchmark(gold, tmp_path / "report.json", repeats=1, warmups=0)

    assert payload["status"] == "passed_with_warnings"
    assert sum(workload["status"] == "skipped_missing_input" for workload in payload["workloads"]) == 5


def test_run_research_benchmark_rejects_invalid_run_parameters(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="repeats and threads"):
        run_research_benchmark(tmp_path, tmp_path / "report.json", repeats=0)
