from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


def resolve_run_mode(explicit: str | None = None) -> str:
    raw = explicit if explicit is not None else (os.getenv("RUN_MODE") or os.getenv("GITHUB_EVENT_NAME") or "manual")
    normalized = str(raw).strip().lower()
    if normalized == "schedule":
        return "scheduled"
    if normalized in {"push", "pull_request", "workflow_dispatch", "manual", "scheduled"}:
        return normalized
    return "manual"


def inject_report_context(path: str | Path, context: dict[str, Any]) -> None:
    target = Path(path)
    if not target.exists():
        return
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return
    if not isinstance(payload, dict):
        return
    payload.update(context)
    target.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def append_run_history(entry: dict[str, Any], history_path: str | Path, max_entries: int = 200) -> Path:
    out = Path(history_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    existing: list[dict[str, Any]] = []
    if out.exists():
        try:
            loaded = json.loads(out.read_text(encoding="utf-8"))
            if isinstance(loaded, list):
                existing = [x for x in loaded if isinstance(x, dict)]
        except json.JSONDecodeError:
            existing = []
    existing.append(entry)
    if len(existing) > max_entries:
        existing = existing[-max_entries:]
    out.write_text(json.dumps(existing, indent=2), encoding="utf-8")
    return out
