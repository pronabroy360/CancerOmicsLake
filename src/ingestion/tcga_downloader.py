from __future__ import annotations

import csv
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

from src.common.config import AppConfig


def _latest_tcga_metadata_csv(metadata_dir: str | Path) -> Path:
    path = Path(metadata_dir)
    candidates = sorted(path.glob("tcga_metadata_*.csv"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not candidates:
        raise FileNotFoundError(f"No TCGA metadata CSV found in {path}")
    return candidates[0]


def _infer_data_subdir(data_category: str) -> str:
    category = data_category.lower()
    if "transcriptome profiling" in category:
        return "expression"
    if "simple nucleotide variation" in category:
        return "mutations"
    if "clinical" in category:
        return "clinical"
    if "biospecimen" in category:
        return "biospecimen"
    return "other"


def _is_supported_modality_file(row: dict[str, str]) -> bool:
    subdir = _infer_data_subdir(row.get("data_category", ""))
    data_type = row.get("data_type", "").strip().lower()
    if subdir == "expression":
        return data_type == "gene expression quantification"
    if subdir == "mutations":
        return data_type == "masked somatic mutation"
    return True


def _md5_file(path: Path) -> str:
    hasher = hashlib.md5()
    with path.open("rb") as f:
        while True:
            chunk = f.read(8192)
            if not chunk:
                break
            hasher.update(chunk)
    return hasher.hexdigest()


def _fetch_to_path(url: str, destination: Path, timeout_sec: int) -> None:
    with urlopen(url, timeout=timeout_sec) as response:
        payload = response.read()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(payload)


def _download_with_retry(
    url: str,
    destination: Path,
    retry_count: int,
    retry_backoff_sec: float,
    timeout_sec: int,
) -> str | None:
    last_error: Exception | None = None
    for attempt in range(retry_count + 1):
        try:
            _fetch_to_path(url, destination, timeout_sec)
            return None
        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            last_error = exc
            if attempt >= retry_count:
                break
            time.sleep(retry_backoff_sec * (attempt + 1))
    return str(last_error) if last_error else "unknown_download_error"


def _write_json(path: str | Path, payload: dict[str, Any]) -> Path:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return out


def _canonicalize_caps(raw_caps: dict[str, dict[str, int]] | None) -> dict[str, dict[str, int]]:
    if not raw_caps:
        return {}
    normalized: dict[str, dict[str, int]] = {}
    for project_id, cap_map in raw_caps.items():
        if not isinstance(cap_map, dict):
            continue
        entry: dict[str, int] = {}
        for modality, cap in cap_map.items():
            key = str(modality).strip().lower()
            if key not in {"expression", "expression_normal", "mutations"}:
                continue
            try:
                parsed = int(cap)
            except (TypeError, ValueError):
                continue
            if parsed < 0:
                continue
            entry[key] = parsed
        if entry:
            normalized[str(project_id)] = entry
    return normalized


def _count_inc(store: dict[str, int], key: str) -> None:
    store[key] = store.get(key, 0) + 1


def _build_project_subdir_key(project_id: str, subdir: str) -> str:
    return f"{project_id}|{subdir}"


def _selection_bucket(row: dict[str, str], caps: dict[str, dict[str, int]]) -> str:
    subdir = _infer_data_subdir(row.get("data_category", ""))
    project_caps = caps.get(row.get("project_id", ""), {})
    sample_type = row.get("sample_type", "").strip().lower()
    if subdir == "expression" and "expression_normal" in project_caps and sample_type == "solid tissue normal":
        return "expression_normal"
    return subdir


def _download_one_row(
    row: dict[str, str],
    destination: Path,
    base_url: str,
    retry_count: int,
    retry_backoff_sec: float,
    timeout_sec: int,
) -> dict[str, Any]:
    project_id = row["project_id"]
    file_id = row["file_id"]
    file_name = row["file_name"]
    data_subdir = _infer_data_subdir(row.get("data_category", ""))
    key = _build_project_subdir_key(project_id, data_subdir)
    md5sum = row.get("md5sum", "").strip()
    url = f"{base_url.rstrip('/')}/data/{file_id}"

    error = _download_with_retry(
        url=url,
        destination=destination,
        retry_count=retry_count,
        retry_backoff_sec=retry_backoff_sec,
        timeout_sec=timeout_sec,
    )
    if error:
        return {
            "status": "failed",
            "key": key,
            "project_id": project_id,
            "file_id": file_id,
            "file_name": file_name,
            "error": error,
            "bytes": 0,
            "checksum_mismatch": False,
        }

    if not destination.exists():
        return {
            "status": "failed",
            "key": key,
            "project_id": project_id,
            "file_id": file_id,
            "file_name": file_name,
            "error": "download_completed_but_file_missing",
            "bytes": 0,
            "checksum_mismatch": False,
        }

    file_size = destination.stat().st_size
    if md5sum:
        downloaded_md5 = _md5_file(destination)
        if downloaded_md5 != md5sum:
            destination.unlink(missing_ok=True)
            return {
                "status": "failed",
                "key": key,
                "project_id": project_id,
                "file_id": file_id,
                "file_name": file_name,
                "error": "checksum_mismatch",
                "bytes": 0,
                "checksum_mismatch": True,
            }

    return {
        "status": "downloaded",
        "key": key,
        "project_id": project_id,
        "file_id": file_id,
        "file_name": file_name,
        "error": "",
        "bytes": file_size,
        "checksum_mismatch": False,
    }


def download_tcga_files(
    config: AppConfig,
    metadata_csv_path: str | Path | None = None,
    metadata_dir: str | Path = "data/bronze/tcga/metadata",
    bronze_tcga_root: str | Path = "data/bronze/tcga",
    report_path: str | Path = "outputs/reports/tcga_download_report.json",
    retry_log_path: str | Path = "outputs/reports/tcga_download_retry_log.json",
    force_download: bool = False,
    max_downloads: int | None = None,
    allowed_data_subdirs: set[str] | None = None,
    project_modality_caps: dict[str, dict[str, int]] | None = None,
    run_mode: str = "manual",
    download_workers: int = 1,
    paired_expression_case_ids_by_project: dict[str, set[str]] | None = None,
) -> dict[str, Any]:
    run_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    if config.tcga.metadata_only and not force_download:
        summary = {
            "pipeline_run_id": run_id,
            "run_mode": run_mode,
            "status": "skipped_metadata_only",
            "reason": "tcga.metadata_only=true",
            "total_candidates": 0,
            "attempted_downloads": 0,
            "downloaded_count": 0,
            "skipped_existing_count": 0,
            "failed_count": 0,
            "checksum_mismatch_count": 0,
            "total_bytes_downloaded": 0,
            "failures": [],
        }
        _write_json(report_path, summary)
        _write_json(retry_log_path, {"pipeline_run_id": run_id, "failures": []})
        return summary

    source_path = Path(metadata_csv_path) if metadata_csv_path else _latest_tcga_metadata_csv(metadata_dir)
    if not source_path.exists():
        raise FileNotFoundError(f"Metadata CSV not found: {source_path}")

    with source_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        rows = [row for row in reader]

    candidate_rows = [
        row
        for row in rows
        if row.get("access", "").lower() == "open"
        and row.get("project_id", "") in config.tcga.projects
        and bool(row.get("file_id"))
        and bool(row.get("file_name"))
        and _is_supported_modality_file(row)
    ]

    candidate_rows = sorted(
        candidate_rows,
        key=lambda row: (
            row.get("project_id", ""),
            _infer_data_subdir(row.get("data_category", "")),
            row.get("file_id", ""),
            row.get("file_name", ""),
        ),
    )
    if allowed_data_subdirs:
        normalized_allowed = {x.strip().lower() for x in allowed_data_subdirs if x.strip()}
        candidate_rows = [
            row for row in candidate_rows if _infer_data_subdir(row.get("data_category", "")) in normalized_allowed
        ]

    paired_targets = {
        str(project_id): {str(case_id) for case_id in case_ids if str(case_id).strip()}
        for project_id, case_ids in (paired_expression_case_ids_by_project or {}).items()
    }
    if paired_targets:
        candidate_rows = [
            row
            for row in candidate_rows
            if _infer_data_subdir(row.get("data_category", "")) == "expression"
            and row.get("sample_type", "").strip().lower() == "primary tumor"
            and row.get("case_id", "") in paired_targets.get(row.get("project_id", ""), set())
        ]

    effective_caps = _canonicalize_caps(project_modality_caps) if project_modality_caps is not None else _canonicalize_caps(
        config.tcga.download_caps_by_project
    )
    candidate_counts: dict[str, int] = {}
    selected_counts: dict[str, int] = {}
    selected_rows: list[dict[str, str]] = []
    for row in candidate_rows:
        project_id = row.get("project_id", "")
        bucket = _selection_bucket(row, effective_caps)
        key = _build_project_subdir_key(project_id, bucket)
        _count_inc(candidate_counts, key)

        cap_for_modality = effective_caps.get(project_id, {}).get(bucket)
        if cap_for_modality is not None and selected_counts.get(key, 0) >= cap_for_modality:
            continue
        _count_inc(selected_counts, key)
        selected_rows.append(row)

    downloaded_count = 0
    skipped_existing_count = 0
    failed_count = 0
    checksum_mismatch_count = 0
    attempted_downloads = 0
    total_bytes_downloaded = 0
    failures: list[dict[str, str]] = []
    downloaded_counts: dict[str, int] = {}
    skipped_counts: dict[str, int] = {}
    failed_counts: dict[str, int] = {}

    root = Path(bronze_tcga_root)
    tasks: list[tuple[dict[str, str], Path]] = []
    for row in selected_rows:
        if max_downloads is not None and attempted_downloads >= max_downloads:
            break
        project_id = row["project_id"]
        file_name = row["file_name"]
        md5sum = row.get("md5sum", "").strip()
        data_subdir = _infer_data_subdir(row.get("data_category", ""))
        key = _build_project_subdir_key(project_id, data_subdir)
        destination = root / project_id / data_subdir / file_name

        if destination.exists() and md5sum:
            existing_md5 = _md5_file(destination)
            if existing_md5 == md5sum:
                skipped_existing_count += 1
                _count_inc(skipped_counts, key)
                continue

        attempted_downloads += 1
        tasks.append((row, destination))

    worker_count = max(1, int(download_workers or 1))
    results: list[dict[str, Any]] = []
    if worker_count == 1:
        for row, destination in tasks:
            results.append(
                _download_one_row(
                    row=row,
                    destination=destination,
                    base_url=config.gdc_api.base_url,
                    retry_count=config.gdc_api.retry_count,
                    retry_backoff_sec=config.gdc_api.retry_backoff_sec,
                    timeout_sec=config.gdc_api.request_timeout_sec,
                )
            )
    else:
        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            future_map = {
                executor.submit(
                    _download_one_row,
                    row,
                    destination,
                    config.gdc_api.base_url,
                    config.gdc_api.retry_count,
                    config.gdc_api.retry_backoff_sec,
                    config.gdc_api.request_timeout_sec,
                ): row
                for row, destination in tasks
            }
            for future in as_completed(future_map):
                results.append(future.result())

    for result in results:
        key = str(result["key"])
        if result["status"] == "failed":
            failed_count += 1
            _count_inc(failed_counts, key)
            if result.get("checksum_mismatch"):
                checksum_mismatch_count += 1
            failures.append(
                {
                    "project_id": str(result["project_id"]),
                    "file_id": str(result["file_id"]),
                    "file_name": str(result["file_name"]),
                    "error": str(result["error"]),
                }
            )
            continue
        downloaded_count += 1
        total_bytes_downloaded += int(result.get("bytes") or 0)
        _count_inc(downloaded_counts, key)

    status = "completed_with_failures" if failures else "completed"
    cap_applied = len(selected_rows) < len(candidate_rows)
    selected_files = [
        {
            "project_id": row.get("project_id", ""),
            "file_id": row.get("file_id", ""),
            "file_name": row.get("file_name", ""),
            "data_subdir": _infer_data_subdir(row.get("data_category", "")),
            "selection_bucket": _selection_bucket(row, effective_caps),
            "sample_type": row.get("sample_type", ""),
            "case_id": row.get("case_id", ""),
            "data_category": row.get("data_category", ""),
            "data_type": row.get("data_type", ""),
            "md5sum": row.get("md5sum", ""),
        }
        for row in selected_rows
    ]
    summary = {
        "pipeline_run_id": run_id,
        "run_mode": run_mode,
        "status": status,
        "source_metadata_file": str(source_path),
        "total_candidates": len(candidate_rows),
        "selected_candidates": len(selected_rows),
        "max_downloads": max_downloads,
        "download_workers": worker_count,
        "allowed_data_subdirs": sorted(list(allowed_data_subdirs)) if allowed_data_subdirs else [],
        "project_modality_caps": effective_caps,
        "selection_policy": "paired_primary_tumor" if paired_targets else "deterministic_cap",
        "paired_expression_target_case_counts": {
            project_id: len(case_ids) for project_id, case_ids in sorted(paired_targets.items())
        },
        "paired_expression_candidate_case_counts": {
            project_id: len(
                {
                    row.get("case_id", "")
                    for row in candidate_rows
                    if row.get("project_id", "") == project_id and row.get("case_id", "")
                }
            )
            for project_id in sorted(paired_targets)
        },
        "cap_applied": cap_applied,
        "selected_files": selected_files,
        "candidate_counts_by_project_subdir": candidate_counts,
        "selected_counts_by_project_subdir": selected_counts,
        "downloaded_counts_by_project_subdir": downloaded_counts,
        "skipped_counts_by_project_subdir": skipped_counts,
        "failed_counts_by_project_subdir": failed_counts,
        "attempted_downloads": attempted_downloads,
        "downloaded_count": downloaded_count,
        "skipped_existing_count": skipped_existing_count,
        "failed_count": failed_count,
        "checksum_mismatch_count": checksum_mismatch_count,
        "total_bytes_downloaded": total_bytes_downloaded,
        "failures": failures,
    }
    _write_json(report_path, summary)
    _write_json(retry_log_path, {"pipeline_run_id": run_id, "failures": failures})
    return summary
