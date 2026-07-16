from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any

import polars as pl

from src.analytics.dashboard_data import (
    cohort_distribution_data,
    graph_explorer_data,
    mutation_landscape_data,
    overview_metrics,
    quality_report_data,
)


PASSING_QUALITY_STATUSES = {"passed", "passed_with_warnings"}


def _check(
    name: str,
    passed: bool,
    message: str,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "check_name": name,
        "status": "passed" if passed else "failed",
        "message": message,
        "details": details or {},
    }


def _read_parquet(path: Path) -> pl.DataFrame:
    if not path.exists():
        return pl.DataFrame()
    return pl.read_parquet(path)


def _parquet_rows_check(path: Path, name: str, min_rows: int = 1) -> dict[str, Any]:
    if not path.exists():
        return _check(name, False, f"Missing parquet file: {path}")
    try:
        df = pl.read_parquet(path)
    except Exception as exc:
        return _check(name, False, f"Unable to read parquet file: {path}", {"error": str(exc)})
    rows = df.height
    return _check(
        name,
        rows >= min_rows,
        f"{path} has {rows} rows; expected at least {min_rows}.",
        {"path": str(path), "row_count": rows, "min_rows": min_rows},
    )


def _csv_rows_check(path: Path, name: str, min_data_rows: int = 1) -> dict[str, Any]:
    if not path.exists():
        return _check(name, False, f"Missing CSV file: {path}")
    try:
        with path.open("r", encoding="utf-8") as fh:
            line_count = sum(1 for _ in fh)
    except Exception as exc:
        return _check(name, False, f"Unable to read CSV file: {path}", {"error": str(exc)})
    data_rows = max(line_count - 1, 0)
    return _check(
        name,
        data_rows >= min_data_rows,
        f"{path} has {data_rows} data rows; expected at least {min_data_rows}.",
        {"path": str(path), "data_rows": data_rows, "min_data_rows": min_data_rows},
    )


def _public_graph_export_check(nodes_path: Path, edges_path: Path) -> dict[str, Any]:
    try:
        nodes = pl.read_csv(nodes_path)
        edges = pl.read_csv(edges_path)
    except Exception as exc:
        return _check(
            "public_graph_exports_exclude_individual_entities",
            False,
            "Public graph exports should be readable.",
            {"error": str(exc)},
        )

    disallowed_nodes = nodes.filter(
        pl.col("node_label").is_in(["Patient", "Sample"])
        | pl.col("node_id").cast(pl.Utf8).str.starts_with("PATIENT:")
        | pl.col("node_id").cast(pl.Utf8).str.starts_with("SAMPLE:")
    ).height
    disallowed_edges = edges.filter(
        pl.col("source_node_id").cast(pl.Utf8).str.starts_with("PATIENT:")
        | pl.col("source_node_id").cast(pl.Utf8).str.starts_with("SAMPLE:")
        | pl.col("target_node_id").cast(pl.Utf8).str.starts_with("PATIENT:")
        | pl.col("target_node_id").cast(pl.Utf8).str.starts_with("SAMPLE:")
    ).height
    failed_rows = disallowed_nodes + disallowed_edges
    return _check(
        "public_graph_exports_exclude_individual_entities",
        failed_rows == 0,
        "Public graph exports must exclude Patient and Sample identifiers.",
        {"failed_rows": failed_rows},
    )


def _json_report_check(path: Path, name: str, allowed_statuses: set[str] | None = None) -> dict[str, Any]:
    if not path.exists():
        return _check(name, False, f"Missing JSON report: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return _check(name, False, f"Unable to parse JSON report: {path}", {"error": str(exc)})
    status = str(payload.get("status", "unknown"))
    statuses = allowed_statuses or PASSING_QUALITY_STATUSES
    return _check(
        name,
        status in statuses,
        f"{path} status is {status}; expected one of {sorted(statuses)}.",
        {"path": str(path), "status": status},
    )


def _strict_no_stub_origin_check(path: Path, name: str) -> dict[str, Any]:
    if not path.exists():
        return _check(name, False, f"Missing parquet file for strict no-stub check: {path}")
    df = _read_parquet(path)
    if df.is_empty():
        return _check(name, False, f"{path} is empty in strict no-stub mode.")
    if "data_origin" not in df.columns:
        return _check(name, False, f"{path} does not expose data_origin for strict no-stub mode.")
    bad = df.filter(
        pl.col("data_origin")
        .cast(pl.Utf8, strict=False)
        .fill_null("")
        .str.to_lowercase()
        .str.contains("stub|placeholder|demo")
    )
    return _check(
        name,
        bad.is_empty(),
        f"{path} contains {bad.height} stub/demo-origin rows.",
        {"path": str(path), "stub_like_rows": bad.height, "row_count": df.height},
    )


def _strict_live_audit_check(path: Path) -> dict[str, Any]:
    if not path.exists():
        return _check("strict_live_gdc_audit", False, f"Missing GDC audit report: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    source_mode = str(payload.get("source_mode", "unknown"))
    return _check(
        "strict_live_gdc_audit",
        source_mode == "live",
        f"GDC audit source_mode is {source_mode}; expected live in strict no-stub mode.",
        {"path": str(path), "source_mode": source_mode},
    )


def _api_health_check() -> dict[str, Any]:
    try:
        from fastapi.testclient import TestClient

        from src.api.main import app

        response = TestClient(app).get("/health")
        payload = response.json()
        passed = response.status_code == 200 and payload.get("status") == "ok"
        return _check(
            "api_health_endpoint",
            passed,
            f"/health returned status_code={response.status_code}, payload={payload}.",
            {"status_code": response.status_code, "payload": payload},
        )
    except Exception as exc:
        return _check("api_health_endpoint", False, "FastAPI health check failed.", {"error": str(exc)})


def _dashboard_contract_checks() -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []

    try:
        overview = overview_metrics()
        checks.append(
            _check(
                "dashboard_overview_metrics",
                int(overview.get("tcga_samples", 0)) > 0,
                "Dashboard overview loaded cohort metrics.",
                overview,
            )
        )
    except Exception as exc:
        checks.append(_check("dashboard_overview_metrics", False, "Dashboard overview failed.", {"error": str(exc)}))

    try:
        cohort = cohort_distribution_data()
        checks.append(
            _check(
                "dashboard_cohort_distribution",
                int(cohort.get("total_samples", 0)) > 0,
                "Dashboard cohort distribution loaded sample counts.",
                {
                    "total_samples": cohort.get("total_samples", 0),
                    "total_cases": cohort.get("total_cases", 0),
                },
            )
        )
    except Exception as exc:
        checks.append(_check("dashboard_cohort_distribution", False, "Dashboard cohort distribution failed.", {"error": str(exc)}))

    try:
        mutations = mutation_landscape_data(limit=10)
        checks.append(
            _check(
                "dashboard_mutation_landscape",
                mutations.height > 0,
                "Dashboard mutation landscape loaded mutation rows.",
                {"row_count": mutations.height},
            )
        )
    except Exception as exc:
        checks.append(_check("dashboard_mutation_landscape", False, "Dashboard mutation landscape failed.", {"error": str(exc)}))

    try:
        graph = graph_explorer_data(max_rows=50)
        checks.append(
            _check(
                "dashboard_graph_explorer",
                graph["nodes"].height > 0 and graph["edges"].height > 0,
                "Dashboard graph explorer loaded graph nodes and edges.",
                {"node_count": graph["nodes"].height, "edge_count": graph["edges"].height},
            )
        )
    except Exception as exc:
        checks.append(_check("dashboard_graph_explorer", False, "Dashboard graph explorer failed.", {"error": str(exc)}))

    try:
        quality = quality_report_data()
        checks.append(
            _check(
                "dashboard_quality_report",
                quality.get("status") in PASSING_QUALITY_STATUSES and quality["checks"].height > 0,
                "Dashboard quality report loaded latest quality checks.",
                {"status": quality.get("status"), "check_count": quality["checks"].height},
            )
        )
    except Exception as exc:
        checks.append(_check("dashboard_quality_report", False, "Dashboard quality report failed.", {"error": str(exc)}))

    return checks


def run_demo_check(
    *,
    strict_no_stub: bool = False,
    include_api: bool = True,
    include_dashboard: bool = True,
) -> dict[str, Any]:
    checks: list[dict[str, Any]] = [
        _parquet_rows_check(Path("data/silver/silver_samples.parquet"), "silver_samples_nonzero"),
        _parquet_rows_check(Path("data/silver/silver_expression_tcga.parquet"), "silver_expression_tcga_nonzero"),
        _parquet_rows_check(Path("data/silver/silver_expression_gtex.parquet"), "silver_expression_gtex_nonzero"),
        _parquet_rows_check(Path("data/silver/silver_mutations.parquet"), "silver_mutations_nonzero"),
        _parquet_rows_check(
            Path("data/silver/silver_mutation_profile.parquet"),
            "silver_mutation_profile_nonzero",
        ),
        _parquet_rows_check(Path("data/gold/gold_cohort_summary.parquet"), "gold_cohort_summary_nonzero"),
        _parquet_rows_check(Path("data/gold/gold_mutation_frequency_by_gene.parquet"), "gold_mutation_frequency_by_gene_nonzero"),
        _parquet_rows_check(Path("data/gold/gold_graph_nodes.parquet"), "gold_graph_nodes_nonzero"),
        _parquet_rows_check(Path("data/gold/gold_graph_edges.parquet"), "gold_graph_edges_nonzero"),
        _parquet_rows_check(Path("data/gold/gold_graph_node_metrics.parquet"), "gold_graph_node_metrics_nonzero"),
        _parquet_rows_check(
            Path("data/gold/gold_cancer_gene_evidence_confidence.parquet"),
            "gold_evidence_confidence_nonzero",
        ),
        _json_report_check(Path("outputs/reports/silver_data_quality_report.json"), "silver_quality_report_passing"),
        _json_report_check(Path("outputs/reports/graph_metrics_report.json"), "graph_metrics_report_passing", {"passed"}),
        _csv_rows_check(Path("outputs/graph_exports/neo4j/nodes.csv"), "neo4j_nodes_export_nonzero"),
        _csv_rows_check(Path("outputs/graph_exports/neo4j/edges.csv"), "neo4j_edges_export_nonzero"),
        _csv_rows_check(Path("outputs/graph_exports/graphify/nodes.csv"), "graphify_nodes_export_nonzero"),
        _csv_rows_check(Path("outputs/graph_exports/graphify/edges.csv"), "graphify_edges_export_nonzero"),
        _public_graph_export_check(
            Path("outputs/graph_exports/neo4j/nodes.csv"),
            Path("outputs/graph_exports/neo4j/edges.csv"),
        ),
        _check(
            "neo4j_bulk_import_script_exists",
            Path("outputs/graph_exports/neo4j/import_bulk.cypher").exists(),
            "Neo4j bulk import script should exist after graph export.",
            {"path": "outputs/graph_exports/neo4j/import_bulk.cypher"},
        ),
    ]

    if include_api:
        checks.append(_api_health_check())

    if include_dashboard:
        checks.extend(_dashboard_contract_checks())

    if strict_no_stub:
        checks.extend(
            [
                _strict_no_stub_origin_check(Path("data/silver/silver_expression_tcga.parquet"), "strict_tcga_expression_no_stub"),
                _strict_no_stub_origin_check(Path("data/silver/silver_expression_gtex.parquet"), "strict_gtex_expression_no_stub"),
                _strict_no_stub_origin_check(Path("data/silver/silver_mutations.parquet"), "strict_mutations_no_stub"),
                _strict_live_audit_check(Path("outputs/reports/gdc_ingestion_audit.json")),
            ]
        )

    failed = [c for c in checks if c["status"] == "failed"]
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "status": "failed" if failed else "passed",
        "strict_no_stub": strict_no_stub,
        "check_count": len(checks),
        "failed_count": len(failed),
        "checks": checks,
    }


def write_demo_check_report(payload: dict[str, Any], output_path: str | Path = "outputs/reports/demo_check_report.json") -> Path:
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return out
