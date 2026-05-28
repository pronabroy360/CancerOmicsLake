from __future__ import annotations

import json
from pathlib import Path

from src.analytics.cohort_summary import cohort_summary_from_gold


def quality_latest(
    report_path: str | Path = "outputs/reports/silver_data_quality_report.json",
) -> dict[str, object]:
    path = Path(report_path)
    if not path.exists():
        return {
            "status": "unknown",
            "checks": [],
            "summary": cohort_summary_from_gold(),
        }

    payload = json.loads(path.read_text(encoding="utf-8"))
    checks = payload.get("checks", [])
    return {
        "status": payload.get("status", "unknown"),
        "checks": checks if isinstance(checks, list) else [],
        "summary": cohort_summary_from_gold(),
        "pipeline_run_id": payload.get("pipeline_run_id", ""),
        "generated_at": payload.get("generated_at", ""),
    }
