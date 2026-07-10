from __future__ import annotations

import base64
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from src.common.config import AppConfig


def gtex_metadata_stub(config: AppConfig) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for idx, tissue in enumerate(config.gtex.tissues, start=1):
        token = tissue.replace(" ", "").replace("-", "")[:6].upper()
        rows.append(
            {
                "gtex_sample_id": f"GTEX-{token}-{idx:04d}",
                "donor_id": "OPEN-ACCESS",
                "tissue_site": tissue,
                "tissue_detail": tissue,
                "gene_id": "ENSG00000141510",
                "gene_symbol": "TP53",
                "expression_value": "0.0",
                "expression_unit": "TPM",
                "source_version": config.gtex.version,
            }
        )
    return rows


def build_gtex_download_plan(config: AppConfig) -> list[dict[str, str]]:
    missing = [tissue for tissue in config.gtex.tissues if tissue not in config.gtex.tissue_files]
    if missing:
        raise ValueError(f"Missing GTEx tissue file mapping for: {', '.join(missing)}")
    base = config.gtex.download_base_url.rstrip("/")
    plan = [
        {
            "kind": "sample_attributes",
            "tissue": "all",
            "file_name": Path(config.gtex.sample_attributes_url).name,
            "url": config.gtex.sample_attributes_url,
        }
    ]
    plan.extend(
        {
            "kind": "expression",
            "tissue": tissue,
            "file_name": config.gtex.tissue_files[tissue],
            "url": f"{base}/{config.gtex.tissue_files[tissue]}",
        }
        for tissue in config.gtex.tissues
    )
    return plan


def _md5_file(path: Path) -> str:
    digest = hashlib.md5()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _remote_metadata(url: str, timeout_sec: int) -> dict[str, object]:
    request = Request(url, method="HEAD")
    with urlopen(request, timeout=timeout_sec) as response:
        headers = response.headers
    md5_hex = ""
    for value in headers.get_all("x-goog-hash", []):
        for token in value.split(","):
            if token.strip().startswith("md5="):
                md5_hex = base64.b64decode(token.strip()[4:]).hex()
    return {
        "content_length": int(headers.get("content-length", "0") or 0),
        "md5": md5_hex,
        "etag": headers.get("etag", "").strip('"'),
        "last_modified": headers.get("last-modified", ""),
    }


def _stream_download(url: str, destination: Path, timeout_sec: int) -> int:
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_suffix(destination.suffix + ".part")
    existing = partial.stat().st_size if partial.exists() else 0
    headers = {"Range": f"bytes={existing}-"} if existing else {}
    request = Request(url, headers=headers)
    with urlopen(request, timeout=timeout_sec) as response:
        status = getattr(response, "status", 200)
        mode = "ab" if existing and status == 206 else "wb"
        with partial.open(mode) as output:
            for chunk in iter(lambda: response.read(1024 * 1024), b""):
                output.write(chunk)
    partial.replace(destination)
    return destination.stat().st_size


def download_gtex_files(
    config: AppConfig,
    output_dir: str | Path = "data/bronze/gtex/expression",
    report_path: str | Path = "outputs/reports/gtex_download_report.json",
    force_download: bool = False,
    timeout_sec: int = 120,
    retry_count: int = 2,
    retry_backoff_sec: float = 2.0,
    run_mode: str = "manual",
) -> dict[str, Any]:
    run_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    if config.gtex.metadata_only and not force_download:
        payload: dict[str, Any] = {
            "pipeline_run_id": run_id,
            "run_mode": run_mode,
            "status": "skipped_metadata_only",
            "selected_tissues": config.gtex.tissues,
            "downloaded_count": 0,
            "skipped_existing_count": 0,
            "failed_count": 0,
            "files": [],
        }
        out = Path(report_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return payload

    root = Path(output_dir)
    files: list[dict[str, object]] = []
    downloaded = 0
    skipped = 0
    failed = 0
    total_bytes = 0

    for item in build_gtex_download_plan(config):
        destination = root / item["file_name"]
        record: dict[str, object] = {**item, "destination": str(destination)}
        try:
            remote = _remote_metadata(item["url"], timeout_sec)
            record.update(remote)
            expected_size = int(remote["content_length"])
            expected_md5 = str(remote["md5"])
            if destination.exists() and destination.stat().st_size == expected_size:
                actual_md5 = _md5_file(destination)
                if not expected_md5 or actual_md5 == expected_md5:
                    record.update({"status": "skipped_existing", "actual_md5": actual_md5})
                    skipped += 1
                    total_bytes += destination.stat().st_size
                    files.append(record)
                    continue

            error: Exception | None = None
            for attempt in range(retry_count + 1):
                try:
                    _stream_download(item["url"], destination, timeout_sec)
                    error = None
                    break
                except (HTTPError, URLError, TimeoutError, OSError) as exc:
                    error = exc
                    if attempt < retry_count:
                        time.sleep(retry_backoff_sec * (attempt + 1))
            if error is not None:
                raise error

            actual_size = destination.stat().st_size
            actual_md5 = _md5_file(destination)
            if expected_size and actual_size != expected_size:
                raise ValueError(f"size mismatch: expected {expected_size}, got {actual_size}")
            if expected_md5 and actual_md5 != expected_md5:
                raise ValueError(f"checksum mismatch: expected {expected_md5}, got {actual_md5}")
            record.update({"status": "downloaded", "actual_size": actual_size, "actual_md5": actual_md5})
            downloaded += 1
            total_bytes += actual_size
        except Exception as exc:
            failed += 1
            record.update({"status": "failed", "error": str(exc)})
        files.append(record)

    payload = {
        "pipeline_run_id": run_id,
        "run_mode": run_mode,
        "status": "completed" if failed == 0 else "completed_with_failures",
        "source": "GTEx Portal open-access V8",
        "source_version": config.gtex.version,
        "selected_tissues": config.gtex.tissues,
        "sample_cap_per_tissue": config.gtex.sample_cap_per_tissue,
        "downloaded_count": downloaded,
        "skipped_existing_count": skipped,
        "failed_count": failed,
        "total_bytes_available": total_bytes,
        "files": files,
    }
    out = Path(report_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload
