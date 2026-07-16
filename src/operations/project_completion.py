from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any

import polars as pl

from src.operations.demo_check import PASSING_QUALITY_STATUSES


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _exists(path: str | Path) -> bool:
    return (_repo_root() / Path(path)).exists()


def _json_payload(path: str | Path) -> dict[str, Any]:
    target = _repo_root() / Path(path)
    if not target.exists():
        return {}
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _json_status_ok(path: str | Path, allowed: set[str] | None = None) -> bool:
    payload = _json_payload(path)
    if not payload:
        return False
    status = str(payload.get("status", "unknown"))
    accepted = allowed or PASSING_QUALITY_STATUSES
    return status in accepted


def _parquet_nonempty(path: str | Path) -> bool:
    target = _repo_root() / Path(path)
    if not target.exists():
        return False
    try:
        return pl.read_parquet(target).height > 0
    except Exception:
        return False


def _make_check(name: str, passed: bool, evidence: list[str], *, required: bool = True) -> dict[str, Any]:
    return {
        "check_name": name,
        "status": "passed" if passed else "failed",
        "evidence": evidence,
        "required": required,
    }


def _milestone_status(checks: list[dict[str, Any]]) -> str:
    required_checks = [check for check in checks if check.get("required", True)]
    return "done" if all(check["status"] == "passed" for check in required_checks) else "in_progress"


def build_project_completion_report() -> dict[str, Any]:
    milestones: list[dict[str, Any]] = []

    m1_checks = [
        _make_check(
            "project_setup_files",
            all(
                _exists(path)
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
                ]
            ),
            [
                "README.md",
                "Makefile",
                "pyproject.toml",
                "docker-compose.yml",
                "configs/project_config.yml",
                "AGENTS.md",
                "GUARDRAILS.md",
                "PRD.md",
                "WORKLOGS.md",
            ],
        )
    ]
    milestones.append(
        {
            "milestone_id": "M1",
            "name": "Project Setup",
            "status": _milestone_status(m1_checks),
            "checks": m1_checks,
        }
    )

    m2_checks = [
        _make_check(
            "metadata_outputs_present",
            _exists("outputs/reports/gdc_ingestion_audit.json")
            and any(
                (_repo_root() / "data/bronze/tcga/metadata").glob("tcga_metadata_*.csv")
            )
            and any(
                (_repo_root() / "data/bronze/tcga/metadata").glob("gdc_manifest_*.tsv")
            ),
            [
                "outputs/reports/gdc_ingestion_audit.json",
                "data/bronze/tcga/metadata/tcga_metadata_*.csv",
                "data/bronze/tcga/metadata/gdc_manifest_*.tsv",
            ],
        )
    ]
    milestones.append(
        {
            "milestone_id": "M2",
            "name": "Metadata Ingestion",
            "status": _milestone_status(m2_checks),
            "checks": m2_checks,
        }
    )

    m3_checks = [
        _make_check(
            "silver_expression_tables_nonempty",
            _parquet_nonempty("data/silver/silver_expression_tcga.parquet")
            and _parquet_nonempty("data/silver/silver_expression_gtex.parquet"),
            [
                "data/silver/silver_expression_tcga.parquet",
                "data/silver/silver_expression_gtex.parquet",
            ],
        )
    ]
    milestones.append(
        {
            "milestone_id": "M3",
            "name": "Expression Processing",
            "status": _milestone_status(m3_checks),
            "checks": m3_checks,
        }
    )

    m4_checks = [
        _make_check(
            "mutation_pipeline_outputs_nonempty",
            _parquet_nonempty("data/silver/silver_mutations.parquet")
            and _parquet_nonempty("data/silver/silver_mutation_profile.parquet")
            and _parquet_nonempty("data/gold/gold_mutation_frequency_by_gene.parquet")
            and _parquet_nonempty("data/gold/gold_mutation_frequency_by_cancer.parquet"),
            [
                "data/silver/silver_mutations.parquet",
                "data/silver/silver_mutation_profile.parquet",
                "data/gold/gold_mutation_frequency_by_gene.parquet",
                "data/gold/gold_mutation_frequency_by_cancer.parquet",
            ],
        )
    ]
    milestones.append(
        {
            "milestone_id": "M4",
            "name": "Mutation Processing",
            "status": _milestone_status(m4_checks),
            "checks": m4_checks,
        }
    )

    m5_checks = [
        _make_check(
            "dbt_models_present",
            all(
                _exists(path)
                for path in [
                    "dbt/dbt_project.yml",
                    "dbt/models/silver/schema.yml",
                    "dbt/models/gold/schema.yml",
                ]
            ),
            [
                "dbt/dbt_project.yml",
                "dbt/models/silver/schema.yml",
                "dbt/models/gold/schema.yml",
            ],
        ),
        _make_check(
            "dbt_execution_report_passing",
            _json_status_ok("outputs/reports/dbt_execution_report.json", {"passed"}),
            [
                "outputs/reports/dbt_execution_report.json",
            ],
            required=False,
        )
    ]
    milestones.append(
        {
            "milestone_id": "M5",
            "name": "dbt Warehouse",
            "status": _milestone_status(m5_checks),
            "checks": m5_checks,
        }
    )

    m6_checks = [
        _make_check(
            "quality_reports_passing",
            _json_status_ok("outputs/reports/silver_data_quality_report.json")
            and _json_status_ok("outputs/reports/data_quality_report.json"),
            [
                "outputs/reports/silver_data_quality_report.json",
                "outputs/reports/data_quality_report.json",
            ],
        )
    ]
    milestones.append(
        {
            "milestone_id": "M6",
            "name": "Data Quality Layer",
            "status": _milestone_status(m6_checks),
            "checks": m6_checks,
        }
    )

    m7_checks = [
        _make_check(
            "graph_outputs_available",
            _parquet_nonempty("data/gold/gold_graph_nodes.parquet")
            and _parquet_nonempty("data/gold/gold_graph_edges.parquet")
            and _exists("outputs/graph_exports/neo4j/nodes.csv")
            and _exists("outputs/graph_exports/neo4j/edges.csv")
            and _exists("outputs/graph_exports/neo4j/import_bulk.cypher")
            and _exists("outputs/graph_exports/graphify/nodes.csv")
            and _exists("outputs/graph_exports/graphify/edges.csv"),
            [
                "data/gold/gold_graph_nodes.parquet",
                "data/gold/gold_graph_edges.parquet",
                "outputs/graph_exports/neo4j/nodes.csv",
                "outputs/graph_exports/neo4j/edges.csv",
                "outputs/graph_exports/neo4j/import_bulk.cypher",
                "outputs/graph_exports/graphify/nodes.csv",
                "outputs/graph_exports/graphify/edges.csv",
            ],
        )
    ]
    milestones.append(
        {
            "milestone_id": "M7",
            "name": "Knowledge Graph",
            "status": _milestone_status(m7_checks),
            "checks": m7_checks,
        }
    )

    m8_checks = [
        _make_check(
            "app_surfaces_and_demo_check",
            all(
                _exists(path)
                for path in [
                    "src/api/main.py",
                    "dashboard/app.py",
                    "dashboard/pages/1_Cohort_Explorer.py",
                    "dashboard/pages/2_Gene_Expression.py",
                    "dashboard/pages/3_Tumor_vs_Normal.py",
                    "dashboard/pages/4_Mutation_Landscape.py",
                    "dashboard/pages/5_Knowledge_Graph.py",
                    "dashboard/pages/6_Data_Quality.py",
                ]
            )
            and _json_status_ok("outputs/reports/demo_check_report.json", {"passed"}),
            [
                "src/api/main.py",
                "dashboard/app.py",
                "dashboard/pages/*.py",
                "outputs/reports/demo_check_report.json",
            ],
        )
    ]
    milestones.append(
        {
            "milestone_id": "M8",
            "name": "Dashboard And API",
            "status": _milestone_status(m8_checks),
            "checks": m8_checks,
        }
    )

    m9_checks = [
        _make_check(
            "documentation_and_release_assets",
            all(
                _exists(path)
                for path in [
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
                ]
            ),
            [
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
            ],
        )
    ]
    milestones.append(
        {
            "milestone_id": "M9",
            "name": "Final Packaging",
            "status": _milestone_status(m9_checks),
            "checks": m9_checks,
        }
    )

    completed = sum(1 for milestone in milestones if milestone["status"] == "done")
    advisory_failures = sum(
        1
        for milestone in milestones
        for check in milestone["checks"]
        if not check.get("required", True) and check["status"] == "failed"
    )
    if completed != len(milestones):
        status = "in_progress"
    elif advisory_failures > 0:
        status = "complete_with_warnings"
    else:
        status = "complete"
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "status": status,
        "completed_milestones": completed,
        "total_milestones": len(milestones),
        "warning_count": advisory_failures,
        "milestones": milestones,
    }


def write_project_completion_report(
    payload: dict[str, Any],
    output_path: str | Path = "outputs/reports/project_completion_report.json",
) -> Path:
    out = _repo_root() / Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return out
