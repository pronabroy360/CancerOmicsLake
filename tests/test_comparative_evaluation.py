from __future__ import annotations

import json
from pathlib import Path

import polars as pl
import yaml

from src.operations.comparative_evaluation import (
    TASK_IDS,
    build_comparative_evaluation_report,
    collect_canceromicslake_baseline,
)


TOOLS = ("CancerOmicsLake", "TCGAbiolinks", "UCSC Xena", "cBioPortal")


def _config(root: Path) -> Path:
    path = root / "publication.yml"
    path.write_text(
        yaml.safe_dump(
            {
                "publication": {
                    "subject_tool": "CancerOmicsLake",
                    "required_comparators": list(TOOLS[1:]),
                    "required_comparison_tasks": list(TASK_IDS),
                }
            }
        ),
        encoding="utf-8",
    )
    return path


def _task(root: Path, tool: str, task_id: str, status: str = "passed") -> None:
    path = root / "evidence" / tool / task_id / "task.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "tool": tool,
                "task_id": task_id,
                "task_status": status,
                "tool_version": "fixture",
                "evidence": ["https://example.org/fixture.json"],
            }
        ),
        encoding="utf-8",
    )


def test_comparative_report_requires_all_twenty_tool_task_results(
    tmp_path: Path,
) -> None:
    config = _config(tmp_path)
    for tool in TOOLS:
        for task_id in TASK_IDS:
            _task(tmp_path, tool, task_id)

    payload = build_comparative_evaluation_report(
        publication_config_path=config.relative_to(tmp_path),
        root_dir=tmp_path,
        evidence_root="evidence",
    )

    assert payload["status"] == "passed"
    assert payload["required_result_count"] == 20
    assert payload["completed_result_count"] == 20
    assert payload["missing_result_count"] == 0


def test_comparative_report_preserves_incomplete_and_failed_results(
    tmp_path: Path,
) -> None:
    config = _config(tmp_path)
    for task_id in TASK_IDS:
        _task(tmp_path, "CancerOmicsLake", task_id)
    _task(tmp_path, "cBioPortal", "T1", status="failed")

    payload = build_comparative_evaluation_report(
        publication_config_path=config.relative_to(tmp_path),
        root_dir=tmp_path,
        evidence_root="evidence",
    )

    assert payload["status"] == "in_progress"
    assert payload["completed_result_count"] == 5
    assert payload["missing_result_count"] == 15
    assert payload["failed_result_count"] == 1


def _write_baseline_fixture(root: Path) -> None:
    gold = root / "data/gold"
    gold.mkdir(parents=True)
    pl.DataFrame(
        {
            "tcga_project_count": [3],
            "tcga_patient_count": [10],
            "tcga_sample_count": [12],
            "tcga_file_count": [20],
            "gtex_expression_sample_count": [4],
            "tcga_expression_row_count": [100],
            "gtex_expression_row_count": [80],
            "gene_count": [5],
            "mutation_record_count": [4],
            "protein_altering_mutation_record_count": [3],
            "mutation_profiled_sample_count": [2],
            "generated_at": ["fixture"],
        }
    ).write_parquet(gold / "gold_cohort_summary.parquet")
    pl.DataFrame(
        {
            "gene_symbol": ["TP53"],
            "cancer_type": ["TCGA-BRCA"],
            "median_tcga_tumor_expression": [10.0],
            "median_gtex_normal_expression": [2.0],
            "mean_tcga_tumor_expression": [11.0],
            "mean_gtex_normal_expression": [3.0],
            "log2_fold_change": [2.0],
            "sample_count_tumor": [10],
            "sample_count_normal": [4],
        }
    ).write_parquet(gold / "gold_tumor_vs_normal_expression.parquet")
    pl.DataFrame(
        {
            "gene_symbol": ["TP53"],
            "cancer_type": ["TCGA-LUAD"],
            "mutated_sample_count": [2],
            "total_profiled_sample_count": [4],
            "mutation_frequency": [0.5],
            "top_variant_classification": ["Missense_Mutation"],
            "protein_altering_event_count": [2],
            "all_somatic_event_count": [3],
            "synonymous_event_count": [1],
            "mutation_scope": ["protein_altering_only"],
        }
    ).write_parquet(gold / "gold_mutation_frequency_by_gene.parquet")

    reports = root / "outputs/reports"
    reports.mkdir(parents=True)
    (reports / "research_benchmark_report.json").write_text(
        json.dumps({"status": "passed", "workloads": [{"status": "passed"}]}),
        encoding="utf-8",
    )
    manuscript = root / "manuscript"
    manuscript.mkdir()
    (manuscript / "evidence_ledger.json").write_text(
        json.dumps({"status": "passed", "claims": [{"claim_id": "C01"}]}),
        encoding="utf-8",
    )

    graph = root / "outputs/graph_exports/neo4j"
    graph.mkdir(parents=True)
    pl.DataFrame(
        {
            "node_id": ["GENE:TP53", "CANCER:TCGA-LUAD"],
            "node_label": ["Gene", "CancerType"],
        }
    ).write_csv(graph / "nodes.csv")
    pl.DataFrame(
        {
            "source_node_id": ["GENE:TP53"],
            "target_node_id": ["CANCER:TCGA-LUAD"],
            "edge_type": ["MUTATED_IN_CANCER"],
        }
    ).write_csv(graph / "edges.csv")


def test_local_baseline_collector_writes_five_safe_tasks(
    monkeypatch,
    tmp_path: Path,
) -> None:
    _write_baseline_fixture(tmp_path)
    monkeypatch.setattr(
        "src.operations.comparative_evaluation._git_commit",
        lambda: "a" * 40,
    )

    records = collect_canceromicslake_baseline(root_dir=tmp_path)

    assert len(records) == 5
    assert all(record["task_status"] == "passed" for record in records)
    assert {record["task_id"] for record in records} == set(TASK_IDS)
    t5 = next(record for record in records if record["task_id"] == "T5")
    assert t5["result_summary"]["individual_identifier_hits"] == 0
