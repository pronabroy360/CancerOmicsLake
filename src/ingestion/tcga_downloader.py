from __future__ import annotations

import csv
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
) -> dict[str, Any]:
    run_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    if config.tcga.metadata_only and not force_download:
        summary = {
            "pipeline_run_id": run_id,
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
    ]
    if allowed_data_subdirs:
        normalized_allowed = {x.strip().lower() for x in allowed_data_subdirs if x.strip()}
        candidate_rows = [
            row for row in candidate_rows if _infer_data_subdir(row.get("data_category", "")) in normalized_allowed
        ]

    downloaded_count = 0
    skipped_existing_count = 0
    failed_count = 0
    checksum_mismatch_count = 0
    attempted_downloads = 0
    total_bytes_downloaded = 0
    failures: list[dict[str, str]] = []

    root = Path(bronze_tcga_root)
    for row in candidate_rows:
        if max_downloads is not None and attempted_downloads >= max_downloads:
            break
        project_id = row["project_id"]
        file_id = row["file_id"]
        file_name = row["file_name"]
        md5sum = row.get("md5sum", "").strip()
        data_subdir = _infer_data_subdir(row.get("data_category", ""))
        destination = root / project_id / data_subdir / file_name

        if destination.exists() and md5sum:
            existing_md5 = _md5_file(destination)
            if existing_md5 == md5sum:
                skipped_existing_count += 1
                continue

        attempted_downloads += 1
        url = f"{config.gdc_api.base_url.rstrip('/')}/data/{file_id}"
        error = _download_with_retry(
            url=url,
            destination=destination,
            retry_count=config.gdc_api.retry_count,
            retry_backoff_sec=config.gdc_api.retry_backoff_sec,
            timeout_sec=config.gdc_api.request_timeout_sec,
        )
        if error:
            failed_count += 1
            failures.append(
                {
                    "project_id": project_id,
                    "file_id": file_id,
                    "file_name": file_name,
                    "error": error,
                }
            )
            continue

        if not destination.exists():
            failed_count += 1
            failures.append(
                {
                    "project_id": project_id,
                    "file_id": file_id,
                    "file_name": file_name,
                    "error": "download_completed_but_file_missing",
                }
            )
            continue

        file_size = destination.stat().st_size
        total_bytes_downloaded += file_size
        if md5sum:
            downloaded_md5 = _md5_file(destination)
            if downloaded_md5 != md5sum:
                checksum_mismatch_count += 1
                failed_count += 1
                failures.append(
                    {
                        "project_id": project_id,
                        "file_id": file_id,
                        "file_name": file_name,
                        "error": "checksum_mismatch",
                    }
                )
                destination.unlink(missing_ok=True)
                continue
        downloaded_count += 1

    status = "completed_with_failures" if failures else "completed"
    summary = {
        "pipeline_run_id": run_id,
        "status": status,
        "source_metadata_file": str(source_path),
        "total_candidates": len(candidate_rows),
        "max_downloads": max_downloads,
        "allowed_data_subdirs": sorted(list(allowed_data_subdirs)) if allowed_data_subdirs else [],
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
