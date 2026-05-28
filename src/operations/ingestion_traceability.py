from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any

import polars as pl


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _read_parquet(path: Path) -> pl.DataFrame:
    if not path.exists():
        return pl.DataFrame()
    return pl.read_parquet(path)


def _decode_project_subdir_counts(raw: dict[str, Any] | None) -> dict[tuple[str, str], int]:
    out: dict[tuple[str, str], int] = {}
    if not isinstance(raw, dict):
        return out
    for key, value in raw.items():
        if not isinstance(key, str) or "|" not in key:
            continue
        project_id, subdir = key.split("|", 1)
        try:
            out[(project_id, subdir)] = int(value)
        except (TypeError, ValueError):
            continue
    return out


def _count_rows_by_project_and_modality(
    df: pl.DataFrame, project_col: str, origin_col: str
) -> tuple[dict[str, int], dict[str, int], dict[str, int]]:
    if df.is_empty() or project_col not in df.columns:
        return {}, {}, {}

    if origin_col not in df.columns:
        rows = (
            df.group_by(project_col)
            .agg(pl.len().alias("row_count"))
            .iter_rows(named=True)
        )
        return (
            {str(r[project_col]): int(r["row_count"]) for r in rows},
            {},
            {},
        )

    subset = df

    by_project = (
        subset.group_by(project_col)
        .agg(pl.len().alias("row_count"))
        .iter_rows(named=True)
    )
    by_project_rows = {str(r[project_col]): int(r["row_count"]) for r in by_project}

    by_project_files = (
        subset.group_by(project_col)
        .agg(pl.col(origin_col).n_unique().alias("file_count"))
        .iter_rows(named=True)
    )
    file_counts = {str(r[project_col]): int(r["file_count"]) for r in by_project_files}

    stub_rows = (
        subset.filter(
            pl.col(origin_col)
            .cast(pl.Utf8, strict=False)
            .fill_null("")
            .str.to_lowercase()
            .str.contains("stub|placeholder|demo")
        )
        .group_by(project_col)
        .agg(pl.len().alias("stub_count"))
        .iter_rows(named=True)
    )
    stub_counts = {str(r[project_col]): int(r["stub_count"]) for r in stub_rows}

    return by_project_rows, file_counts, stub_counts


def build_ingestion_traceability_report(
    *,
    download_report_path: str | Path = "outputs/reports/tcga_download_report.json",
    gdc_audit_path: str | Path = "outputs/reports/gdc_ingestion_audit.json",
    silver_expression_tcga_path: str | Path = "data/silver/silver_expression_tcga.parquet",
    silver_mutations_path: str | Path = "data/silver/silver_mutations.parquet",
) -> dict[str, Any]:
    download_path = Path(download_report_path)
    audit_path = Path(gdc_audit_path)
    expr_path = Path(silver_expression_tcga_path)
    mut_path = Path(silver_mutations_path)

    download = _read_json(download_path)
    audit = _read_json(audit_path)
    expr = _read_parquet(expr_path)
    muts = _read_parquet(mut_path)

    candidate_counts = _decode_project_subdir_counts(download.get("candidate_counts_by_project_subdir"))
    selected_counts = _decode_project_subdir_counts(download.get("selected_counts_by_project_subdir"))
    downloaded_counts = _decode_project_subdir_counts(download.get("downloaded_counts_by_project_subdir"))
    skipped_counts = _decode_project_subdir_counts(download.get("skipped_counts_by_project_subdir"))
    failed_counts = _decode_project_subdir_counts(download.get("failed_counts_by_project_subdir"))

    expr_rows, expr_files, expr_stub = _count_rows_by_project_and_modality(
        expr, "project_id", "data_origin"
    )
    mut_rows, mut_files, mut_stub = _count_rows_by_project_and_modality(
        muts, "project_id", "data_origin"
    )

    project_ids = sorted(
        {
            p
            for p, _ in (
                set(candidate_counts)
                | set(selected_counts)
                | set(downloaded_counts)
                | set(skipped_counts)
                | set(failed_counts)
            )
        }
        | set(expr_rows)
        | set(mut_rows)
    )

    modalities = ("expression", "mutations")
    rows: list[dict[str, Any]] = []
    warnings: list[str] = []
    for project_id in project_ids:
        for modality in modalities:
            candidate = candidate_counts.get((project_id, modality), 0)
            selected = selected_counts.get((project_id, modality), 0)
            downloaded_file_count = downloaded_counts.get((project_id, modality), 0)
            skipped_file_count = skipped_counts.get((project_id, modality), 0)
            failed_file_count = failed_counts.get((project_id, modality), 0)
            expected_locally = downloaded_file_count + skipped_file_count
            silver_row_count = expr_rows.get(project_id, 0) if modality == "expression" else mut_rows.get(project_id, 0)
            silver_file_count = expr_files.get(project_id, 0) if modality == "expression" else mut_files.get(project_id, 0)
            stub_row_count = expr_stub.get(project_id, 0) if modality == "expression" else mut_stub.get(project_id, 0)
            parsed_vs_local_ratio = (
                round(silver_file_count / expected_locally, 4) if expected_locally > 0 else None
            )

            if expected_locally > 0 and silver_row_count == 0:
                warnings.append(
                    f"{project_id}/{modality}: local files exist but silver has zero parsed rows."
                )
            if stub_row_count > 0:
                warnings.append(
                    f"{project_id}/{modality}: detected {stub_row_count} stub/demo-origin rows in silver."
                )

            rows.append(
                {
                    "project_id": project_id,
                    "modality": modality,
                    "candidate_files": candidate,
                    "selected_files": selected,
                    "downloaded_files": downloaded_file_count,
                    "skipped_existing_files": skipped_file_count,
                    "failed_files": failed_file_count,
                    "local_available_files": expected_locally,
                    "silver_parsed_rows": silver_row_count,
                    "silver_unique_source_files": silver_file_count,
                    "silver_stub_rows": stub_row_count,
                    "parsed_vs_local_file_ratio": parsed_vs_local_ratio,
                }
            )

    download_status = str(download.get("status", "missing"))
    status = "passed"
    if download_status == "skipped_metadata_only":
        status = "skipped"
    elif warnings:
        status = "passed_with_warnings"

    summary = {
        "projects_covered": len(project_ids),
        "rows_reported": len(rows),
        "total_candidates": int(download.get("total_candidates", 0) or 0),
        "total_selected_candidates": int(download.get("selected_candidates", 0) or 0),
        "total_downloaded_files": int(download.get("downloaded_count", 0) or 0),
        "total_skipped_existing_files": int(download.get("skipped_existing_count", 0) or 0),
        "total_failed_files": int(download.get("failed_count", 0) or 0),
        "silver_expression_rows": int(expr.height),
        "silver_mutation_rows": int(muts.height),
        "silver_expression_unique_files": int(sum(expr_files.values())),
        "silver_mutation_unique_files": int(sum(mut_files.values())),
        "silver_expression_stub_rows": int(sum(expr_stub.values())),
        "silver_mutation_stub_rows": int(sum(mut_stub.values())),
        "warning_count": len(warnings),
    }

    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "status": status,
        "pipeline_run_id": str(download.get("pipeline_run_id", "")),
        "run_mode": str(download.get("run_mode", "unknown")),
        "download_status": download_status,
        "gdc_source_mode": str(audit.get("source_mode", "unknown")),
        "source_paths": {
            "download_report": str(download_path),
            "gdc_audit": str(audit_path),
            "silver_expression_tcga": str(expr_path),
            "silver_mutations": str(mut_path),
        },
        "summary": summary,
        "project_modality_traceability": rows,
        "warnings": warnings,
    }


def write_ingestion_traceability_report(
    payload: dict[str, Any],
    output_path: str | Path = "outputs/reports/ingestion_traceability_report.json",
) -> Path:
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return out
