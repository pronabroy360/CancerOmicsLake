from __future__ import annotations

import json
from pathlib import Path

from src.common.reporting import append_run_history, inject_report_context, resolve_run_mode


def test_resolve_run_mode_schedule_maps_to_scheduled() -> None:
    assert resolve_run_mode("schedule") == "scheduled"
    assert resolve_run_mode("push") == "push"


def test_inject_report_context_updates_json_file(tmp_path: Path) -> None:
    report = tmp_path / "report.json"
    report.write_text(json.dumps({"status": "ok"}), encoding="utf-8")
    inject_report_context(report, {"run_mode": "scheduled"})
    payload = json.loads(report.read_text(encoding="utf-8"))
    assert payload["run_mode"] == "scheduled"
    assert payload["status"] == "ok"


def test_append_run_history_appends_entries(tmp_path: Path) -> None:
    history = tmp_path / "history.json"
    append_run_history({"pipeline_run_id": "r1", "status": "success"}, history)
    append_run_history({"pipeline_run_id": "r2", "status": "failed"}, history)
    payload = json.loads(history.read_text(encoding="utf-8"))
    assert isinstance(payload, list)
    assert len(payload) == 2
    assert payload[-1]["pipeline_run_id"] == "r2"
