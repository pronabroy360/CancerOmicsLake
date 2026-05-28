from __future__ import annotations

import json
from pathlib import Path

import polars as pl

from src.operations.ingestion_traceability import (
    build_ingestion_traceability_report,
    write_ingestion_traceability_report,
)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_traceability_report_builds_project_modality_rows(tmp_path: Path) -> None:
    download_report = tmp_path / "outputs/reports/tcga_download_report.json"
    audit_report = tmp_path / "outputs/reports/gdc_ingestion_audit.json"
    expr_path = tmp_path / "data/silver/silver_expression_tcga.parquet"
    mut_path = tmp_path / "data/silver/silver_mutations.parquet"
    expr_path.parent.mkdir(parents=True, exist_ok=True)

    _write_json(
        download_report,
        {
            "pipeline_run_id": "run-1",
            "run_mode": "manual",
            "status": "completed",
            "candidate_counts_by_project_subdir": {
                "TCGA-BRCA|expression": 4,
                "TCGA-BRCA|mutations": 2,
            },
            "selected_counts_by_project_subdir": {
                "TCGA-BRCA|expression": 2,
                "TCGA-BRCA|mutations": 1,
            },
            "downloaded_counts_by_project_subdir": {
                "TCGA-BRCA|expression": 1,
                "TCGA-BRCA|mutations": 1,
            },
            "skipped_counts_by_project_subdir": {
                "TCGA-BRCA|expression": 1,
                "TCGA-BRCA|mutations": 0,
            },
            "failed_counts_by_project_subdir": {
                "TCGA-BRCA|expression": 0,
                "TCGA-BRCA|mutations": 0,
            },
            "total_candidates": 6,
            "selected_candidates": 3,
            "downloaded_count": 2,
            "skipped_existing_count": 1,
            "failed_count": 0,
        },
    )
    _write_json(audit_report, {"source_mode": "live"})

    pl.DataFrame(
        {
            "project_id": ["TCGA-BRCA", "TCGA-BRCA"],
            "data_origin": [
                "data/bronze/tcga/TCGA-BRCA/expression/f1.tsv",
                "data/bronze/tcga/TCGA-BRCA/expression/f2.tsv",
            ],
        }
    ).write_parquet(expr_path)
    pl.DataFrame(
        {
            "project_id": ["TCGA-BRCA"],
            "data_origin": ["data/bronze/tcga/TCGA-BRCA/mutations/m1.maf.gz"],
        }
    ).write_parquet(mut_path)

    payload = build_ingestion_traceability_report(
        download_report_path=download_report,
        gdc_audit_path=audit_report,
        silver_expression_tcga_path=expr_path,
        silver_mutations_path=mut_path,
    )

    assert payload["status"] == "passed"
    assert payload["summary"]["projects_covered"] == 1
    assert payload["summary"]["silver_expression_unique_files"] == 2
    assert payload["summary"]["silver_mutation_unique_files"] == 1
    assert len(payload["project_modality_traceability"]) == 2


def test_traceability_report_warns_on_stub_and_missing_rows(tmp_path: Path) -> None:
    download_report = tmp_path / "outputs/reports/tcga_download_report.json"
    expr_path = tmp_path / "data/silver/silver_expression_tcga.parquet"
    mut_path = tmp_path / "data/silver/silver_mutations.parquet"
    expr_path.parent.mkdir(parents=True, exist_ok=True)

    _write_json(
        download_report,
        {
            "status": "completed",
            "downloaded_counts_by_project_subdir": {"TCGA-BRCA|expression": 1},
            "skipped_counts_by_project_subdir": {"TCGA-BRCA|expression": 0},
        },
    )

    pl.DataFrame({"project_id": ["TCGA-BRCA"], "data_origin": ["stub"]}).write_parquet(expr_path)
    pl.DataFrame(schema={"project_id": pl.Utf8, "data_origin": pl.Utf8}).write_parquet(mut_path)

    payload = build_ingestion_traceability_report(
        download_report_path=download_report,
        silver_expression_tcga_path=expr_path,
        silver_mutations_path=mut_path,
    )

    assert payload["status"] == "passed_with_warnings"
    assert payload["summary"]["warning_count"] >= 1
    assert any("stub/demo-origin" in warning for warning in payload["warnings"])


def test_write_ingestion_traceability_report(tmp_path: Path) -> None:
    out = write_ingestion_traceability_report({"status": "passed"}, tmp_path / "trace.json")

    assert out.exists()
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["status"] == "passed"
