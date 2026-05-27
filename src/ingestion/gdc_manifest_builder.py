from __future__ import annotations

import csv
from pathlib import Path

from src.ingestion.gdc_client import GdcFileRecord


def write_manifest(records: list[GdcFileRecord], output_path: str | Path) -> Path:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, delimiter="\t")
        writer.writerow(["id", "filename", "md5", "size", "state"])
        for record in records:
            writer.writerow([record.file_id, record.file_name, record.md5sum, record.file_size, "submitted"])
    return output
