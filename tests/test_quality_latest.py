from pathlib import Path

import json

from src.analytics.quality_latest import quality_latest


def test_quality_latest_reads_report(tmp_path: Path) -> None:
    report = tmp_path / "silver_data_quality_report.json"
    report.write_text(
        json.dumps(
            {
                "pipeline_run_id": "run-1",
                "generated_at": "2026-05-28T00:00:00Z",
                "status": "passed",
                "checks": [{"check_name": "x", "status": "passed"}],
            }
        ),
        encoding="utf-8",
    )
    payload = quality_latest(report)
    assert payload["status"] == "passed"
    assert payload["pipeline_run_id"] == "run-1"
    assert len(payload["checks"]) == 1


def test_quality_latest_missing_report_fallback(tmp_path: Path) -> None:
    payload = quality_latest(tmp_path / "missing.json")
    assert payload["status"] == "unknown"
    assert isinstance(payload["checks"], list)
