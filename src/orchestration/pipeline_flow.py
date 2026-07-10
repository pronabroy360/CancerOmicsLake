from __future__ import annotations

import csv
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
from typing import Any

from prefect import flow, task

from src.analytics.build_gold_tables import build_gold_cohort_summary
from src.analytics.evidence_confidence import build_evidence_confidence
from src.common.config import AppConfig, load_config
from src.common.reporting import append_run_history, inject_report_context
from src.ingestion.gdc_client import query_tcga_metadata_with_audit
from src.ingestion.gdc_manifest_builder import write_manifest
from src.ingestion.tcga_downloader import download_tcga_files
from src.graph.build_edges import build_graph_edges_table
from src.graph.build_nodes import build_graph_nodes_table
from src.graph.export_graphify import export_graphify_from_gold_graph_tables
from src.graph.export_neo4j import export_neo4j_from_gold_graph_tables
from src.graph.graph_metrics import build_graph_node_metrics
from src.processing.build_silver_tables import build_silver_tables_from_bronze
from src.quality.checks import build_quality_payload, run_silver_quality_checks
from src.quality.generate_quality_report import write_quality_json


def _config_hash(config_path: str) -> str:
    content = Path(config_path).read_bytes()
    return hashlib.sha256(content).hexdigest()


def _count_files(path: str | Path) -> int:
    root = Path(path)
    if not root.exists():
        return 0
    return sum(1 for p in root.rglob("*") if p.is_file())


def _write_run_metadata(payload: dict[str, Any], output_path: str | Path) -> Path:
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return out


def _write_tcga_metadata_csv(rows: list[dict[str, str]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        output_path.write_text("", encoding="utf-8")
        return
    with output_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _load_config_impl(config_path: str) -> AppConfig:
    return load_config(config_path)


def _metadata_impl(config_path: str, require_live_gdc: bool = False, run_mode: str = "manual") -> None:
    cfg = load_config(config_path)
    if require_live_gdc:
        cfg.tcga.require_live_gdc = True
    records, source_mode, audit = query_tcga_metadata_with_audit(cfg)
    rows = [
        {
            "project_id": r.project_id,
            "case_id": r.case_id,
            "submitter_id": r.submitter_id,
            "sample_id": r.sample_id,
            "sample_type": r.sample_type,
            "primary_site": r.primary_site,
            "disease_type": r.disease_type,
            "file_id": r.file_id,
            "file_name": r.file_name,
            "data_category": r.data_category,
            "data_type": r.data_type,
            "experimental_strategy": r.experimental_strategy,
            "workflow_type": r.workflow_type,
            "access": r.access,
            "file_size": str(r.file_size),
            "md5sum": r.md5sum,
        }
        for r in records
    ]
    metadata_out = Path(f"data/bronze/tcga/metadata/tcga_metadata_{source_mode}.csv")
    _write_tcga_metadata_csv(rows, metadata_out)
    write_manifest(records, Path(f"data/bronze/tcga/metadata/gdc_manifest_{source_mode}.tsv"))
    audit_out = Path(cfg.gdc_api.audit_output_path)
    audit_out.parent.mkdir(parents=True, exist_ok=True)
    audit_out.write_text(json.dumps(audit, indent=2), encoding="utf-8")
    inject_report_context(audit_out, {"run_mode": run_mode})


def _silver_impl(cfg: AppConfig) -> dict[str, object]:
    return build_silver_tables_from_bronze(config=cfg)


def _download_impl(cfg: AppConfig) -> dict[str, Any]:
    return download_tcga_files(config=cfg)


def _gold_impl() -> dict[str, object]:
    gold_summary = build_gold_cohort_summary()
    node_summary = build_graph_nodes_table()
    edge_summary = build_graph_edges_table()
    return {
        "gold": gold_summary,
        "graph_nodes": node_summary,
        "graph_edges": edge_summary,
    }


def _quality_impl() -> dict[str, Any]:
    checks = run_silver_quality_checks()
    run_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    payload = build_quality_payload(run_id, checks)
    output = write_quality_json(payload, "outputs/reports/silver_data_quality_report.json")
    return {"payload": payload, "output_path": output}


def _graph_export_impl() -> dict[str, object]:
    neo4j = export_neo4j_from_gold_graph_tables()
    graphify = export_graphify_from_gold_graph_tables()
    metrics = build_graph_node_metrics()
    confidence = build_evidence_confidence()
    return {"neo4j": neo4j, "graphify": graphify, "metrics": metrics, "confidence": confidence}


@task
def load_config_stage(config_path: str) -> AppConfig:
    return _load_config_impl(config_path)


@task
def metadata_stage(config_path: str, require_live_gdc: bool = False) -> None:
    _metadata_impl(config_path, require_live_gdc=require_live_gdc)


@task
def silver_stage(cfg: AppConfig) -> dict[str, object]:
    return _silver_impl(cfg)


@task
def download_stage(cfg: AppConfig) -> dict[str, Any]:
    return _download_impl(cfg)


@task
def gold_stage() -> dict[str, object]:
    return _gold_impl()


@task
def quality_stage() -> dict[str, Any]:
    return _quality_impl()


@task
def graph_export_stage() -> dict[str, object]:
    return _graph_export_impl()


def _execute_pipeline(
    config_path: str = "configs/project_config.yml",
    require_live_gdc: bool = False,
    output_metadata_path: str = "outputs/reports/pipeline_run_metadata.json",
    run_mode: str = "manual",
    force_download: bool = False,
    allowed_data_subdirs: set[str] | None = None,
    expression_cap_per_project: int | None = None,
    mutation_cap_per_project: int | None = None,
    download_workers: int = 1,
) -> dict[str, Any]:
    run_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    start = datetime.now(UTC)
    cfg = _load_config_impl(config_path)

    error_count = 0
    warning_count = 0
    status = "success"
    silver_summary: dict[str, object] = {}
    download_summary: dict[str, Any] = {}
    gold_summary: dict[str, object] = {}
    quality_summary: dict[str, Any] = {}

    caps = None
    if expression_cap_per_project is not None or mutation_cap_per_project is not None:
        caps = {
            project_id: {
                **({"expression": int(expression_cap_per_project)} if expression_cap_per_project is not None else {}),
                **({"mutations": int(mutation_cap_per_project)} if mutation_cap_per_project is not None else {}),
            }
            for project_id in cfg.tcga.projects
        }

    try:
        _metadata_impl(config_path=config_path, require_live_gdc=require_live_gdc, run_mode=run_mode)
        download_summary = download_tcga_files(
            config=cfg,
            force_download=force_download,
            allowed_data_subdirs=allowed_data_subdirs,
            project_modality_caps=caps,
            run_mode=run_mode,
            download_workers=download_workers,
        )
        silver_summary = _silver_impl(cfg)
        gold_summary = _gold_impl()
        quality_summary = _quality_impl()
        inject_report_context(
            "outputs/reports/silver_data_quality_report.json",
            {"run_mode": run_mode},
        )
        _graph_export_impl()
    except Exception:
        status = "failed"
        error_count += 1
        raise
    finally:
        checks = quality_summary.get("payload", {}).get("checks", [])
        warning_count = sum(1 for c in checks if c.get("status") == "warning")
        end = datetime.now(UTC)
        output_table_count = 0
        if silver_summary:
            output_table_count += 7
        if gold_summary:
            output_table_count += 7
        run_payload = {
            "pipeline_run_id": run_id,
            "run_mode": run_mode,
            "start_time": start.isoformat(),
            "end_time": end.isoformat(),
            "status": status,
            "config_hash": _config_hash(config_path),
            "input_file_count": _count_files("data/bronze"),
            "output_table_count": output_table_count,
            "error_count": error_count,
            "warning_count": warning_count,
            "force_download": force_download,
            "allowed_data_subdirs": sorted(list(allowed_data_subdirs)) if allowed_data_subdirs else [],
            "expression_cap_per_project": expression_cap_per_project,
            "mutation_cap_per_project": mutation_cap_per_project,
        }
        _write_run_metadata(run_payload, output_metadata_path)
        append_run_history(
            {
                "pipeline_run_id": run_id,
                "run_mode": run_mode,
                "status": status,
                "start_time": start.isoformat(),
                "end_time": end.isoformat(),
                "warning_count": warning_count,
                "error_count": error_count,
            },
            "outputs/reports/pipeline_run_history.json",
        )

    return {
        "pipeline_run_id": run_id,
        "status": status,
        "silver": silver_summary,
        "download": download_summary,
        "gold": gold_summary,
        "quality": quality_summary,
    }


@flow(name="canceromicslake_pipeline")
def canceromicslake_pipeline(
    config_path: str = "configs/project_config.yml",
    require_live_gdc: bool = False,
    output_metadata_path: str = "outputs/reports/pipeline_run_metadata.json",
    run_mode: str = "manual",
    force_download: bool = False,
    allowed_data_subdirs: set[str] | None = None,
    expression_cap_per_project: int | None = None,
    mutation_cap_per_project: int | None = None,
    download_workers: int = 1,
) -> dict[str, Any]:
    return _execute_pipeline(
        config_path=config_path,
        require_live_gdc=require_live_gdc,
        output_metadata_path=output_metadata_path,
        run_mode=run_mode,
        force_download=force_download,
        allowed_data_subdirs=allowed_data_subdirs,
        expression_cap_per_project=expression_cap_per_project,
        mutation_cap_per_project=mutation_cap_per_project,
        download_workers=download_workers,
    )


def run_pipeline_with_fallback(
    config_path: str = "configs/project_config.yml",
    require_live_gdc: bool = False,
    output_metadata_path: str = "outputs/reports/pipeline_run_metadata.json",
    run_mode: str = "manual",
    force_download: bool = False,
    allowed_data_subdirs: set[str] | None = None,
    expression_cap_per_project: int | None = None,
    mutation_cap_per_project: int | None = None,
    download_workers: int = 1,
) -> dict[str, Any]:
    try:
        return canceromicslake_pipeline(
            config_path=config_path,
            require_live_gdc=require_live_gdc,
            output_metadata_path=output_metadata_path,
            run_mode=run_mode,
            force_download=force_download,
            allowed_data_subdirs=allowed_data_subdirs,
            expression_cap_per_project=expression_cap_per_project,
            mutation_cap_per_project=mutation_cap_per_project,
            download_workers=download_workers,
        )
    except RuntimeError as exc:
        if "Unable to find an available port" not in str(exc):
            raise
        return _execute_pipeline(
            config_path=config_path,
            require_live_gdc=require_live_gdc,
            output_metadata_path=output_metadata_path,
            run_mode=run_mode,
            force_download=force_download,
            allowed_data_subdirs=allowed_data_subdirs,
            expression_cap_per_project=expression_cap_per_project,
            mutation_cap_per_project=mutation_cap_per_project,
            download_workers=download_workers,
        )
