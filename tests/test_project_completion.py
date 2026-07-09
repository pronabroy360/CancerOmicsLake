from __future__ import annotations

from pathlib import Path

import polars as pl
import pytest

from src.operations.project_completion import build_project_completion_report
from src.operations import project_completion


def _touch(root: Path, relative_path: str, content: str = "") -> None:
    target = root / relative_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


def _parquet(root: Path, relative_path: str) -> None:
    target = root / relative_path
    target.parent.mkdir(parents=True, exist_ok=True)
    pl.DataFrame({"value": [1]}).write_parquet(target)


def _json(root: Path, relative_path: str, status: str = "passed") -> None:
    _touch(root, relative_path, f'{{"status": "{status}"}}')


def _build_complete_fixture(root: Path) -> None:
    for path in [
        "README.md",
        "Makefile",
        "pyproject.toml",
        "docker-compose.yml",
        "configs/project_config.yml",
        "AGENTS.md",
        "GUARDRAILS.md",
        "PRD.md",
        "WORKLOGS.md",
        "dbt/dbt_project.yml",
        "dbt/models/silver/schema.yml",
        "dbt/models/gold/schema.yml",
        "src/api/main.py",
        "dashboard/app.py",
        "dashboard/pages/1_Cohort_Explorer.py",
        "dashboard/pages/2_Gene_Expression.py",
        "dashboard/pages/3_Tumor_vs_Normal.py",
        "dashboard/pages/4_Mutation_Landscape.py",
        "dashboard/pages/5_Knowledge_Graph.py",
        "dashboard/pages/6_Data_Quality.py",
        "docs/architecture.md",
        "docs/data_dictionary.md",
        "docs/graph_schema.md",
        "docs/api_spec.md",
        "docs/compliance.md",
        "docs/professor_outreach_summary.md",
        "docs/reproducibility.md",
        "docs/sample_queries.md",
        ".github/workflows/ci.yml",
        ".github/workflows/manual_ingestion.yml",
        "data/bronze/tcga/metadata/tcga_metadata_live.csv",
        "data/bronze/tcga/metadata/gdc_manifest_live.tsv",
        "outputs/graph_exports/neo4j/nodes.csv",
        "outputs/graph_exports/neo4j/edges.csv",
        "outputs/graph_exports/neo4j/import_bulk.cypher",
        "outputs/graph_exports/graphify/nodes.csv",
        "outputs/graph_exports/graphify/edges.csv",
    ]:
        _touch(root, path, "fixture")

    for path in [
        "data/silver/silver_expression_tcga.parquet",
        "data/silver/silver_expression_gtex.parquet",
        "data/silver/silver_mutations.parquet",
        "data/gold/gold_mutation_frequency_by_gene.parquet",
        "data/gold/gold_mutation_frequency_by_cancer.parquet",
        "data/gold/gold_graph_nodes.parquet",
        "data/gold/gold_graph_edges.parquet",
    ]:
        _parquet(root, path)

    for path in [
        "outputs/reports/gdc_ingestion_audit.json",
        "outputs/reports/silver_data_quality_report.json",
        "outputs/reports/data_quality_report.json",
        "outputs/reports/dbt_execution_report.json",
        "outputs/reports/demo_check_report.json",
    ]:
        _json(root, path, "passed")


def test_project_completion_report_marks_all_milestones_done(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _build_complete_fixture(tmp_path)
    monkeypatch.setattr(project_completion, "_repo_root", lambda: tmp_path)

    payload = build_project_completion_report()

    assert payload["status"] == "complete"
    assert payload["completed_milestones"] == 9
    assert all(milestone["status"] == "done" for milestone in payload["milestones"])


def test_project_completion_report_flags_missing_dbt_report(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _build_complete_fixture(tmp_path)
    (tmp_path / "outputs/reports/dbt_execution_report.json").unlink()
    monkeypatch.setattr(project_completion, "_repo_root", lambda: tmp_path)

    payload = build_project_completion_report()
    statuses = {milestone["milestone_id"]: milestone["status"] for milestone in payload["milestones"]}

    assert payload["status"] == "complete_with_warnings"
    assert payload["warning_count"] == 1
    assert statuses["M5"] == "done"
