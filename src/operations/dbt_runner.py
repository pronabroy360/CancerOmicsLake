from __future__ import annotations

from datetime import UTC, datetime
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
from typing import Any, Sequence


DBT_ACTIONS = {"run", "test"}
DBT_MODE_ENV = "CANCEROMICSLAKE_DBT_MODE"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _python_version_tuple(version_info: Any | None = None) -> tuple[int, int]:
    current = version_info if version_info is not None else sys.version_info
    return int(current[0]), int(current[1])


def local_dbt_supported(version_info: Any | None = None) -> bool:
    major, minor = _python_version_tuple(version_info)
    return (major, minor) < (3, 14)


def detect_docker_compose(runner: Any = subprocess.run) -> bool:
    try:
        version_result = runner(
            ["docker", "compose", "version"],
            cwd=str(_repo_root()),
            capture_output=True,
            text=True,
            check=False,
        )
        if int(getattr(version_result, "returncode", 1)) != 0:
            return False
        daemon_result = runner(
            ["docker", "info"],
            cwd=str(_repo_root()),
            capture_output=True,
            text=True,
            check=False,
        )
    except (FileNotFoundError, OSError):
        return False
    return int(getattr(daemon_result, "returncode", 1)) == 0


def resolve_dbt_mode(
    requested_mode: str | None = None,
    *,
    version_info: Any | None = None,
    docker_available: bool | None = None,
) -> str:
    requested = (requested_mode or os.getenv(DBT_MODE_ENV) or "auto").strip().lower()
    supported_local = local_dbt_supported(version_info)

    if requested == "local":
        if not supported_local:
            raise RuntimeError("Local dbt execution is unsupported on Python >= 3.14. Use Docker or Python 3.11.")
        return "local"

    if requested == "docker":
        docker_ok = detect_docker_compose() if docker_available is None else docker_available
        if not docker_ok:
            raise RuntimeError("Docker Compose is required for dbt docker mode, but it is unavailable.")
        return "docker"

    if requested != "auto":
        raise ValueError(f"Unsupported dbt mode: {requested}")

    if supported_local:
        return "local"

    docker_ok = detect_docker_compose() if docker_available is None else docker_available
    if docker_ok:
        return "docker"

    raise RuntimeError(
        "dbt cannot run in this environment: local Python is >= 3.14 and Docker Compose is unavailable. "
        "Use Python 3.11 or install Docker."
    )


def build_dbt_command(
    action: str,
    *,
    mode: str,
    project_dir: str = "dbt",
    profiles_dir: str = "dbt",
    python_executable: str | None = None,
) -> list[str]:
    normalized_action = action.strip().lower()
    if normalized_action not in DBT_ACTIONS:
        raise ValueError(f"Unsupported dbt action: {action}")

    if mode == "local":
        dbt_binary = Path(python_executable or sys.executable).with_name("dbt")
        return [
            str(dbt_binary),
            normalized_action,
            "--project-dir",
            project_dir,
            "--profiles-dir",
            profiles_dir,
        ]

    if mode == "docker":
        shell_command = f"dbt {normalized_action} --project-dir {shlex.quote(project_dir)} --profiles-dir {shlex.quote(profiles_dir)}"
        return [
            "docker",
            "compose",
            "run",
            "--rm",
            "dbt",
            "sh",
            "-lc",
            shell_command,
        ]

    raise ValueError(f"Unsupported dbt mode: {mode}")


def write_dbt_execution_report(payload: dict[str, Any], output_path: str | Path) -> Path:
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return out


def _report_payload(
    *,
    action: str,
    mode: str | None,
    command: Sequence[str] | None,
    status: str,
    returncode: int | None = None,
    error: str | None = None,
) -> dict[str, Any]:
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "action": action,
        "mode": mode,
        "status": status,
        "returncode": returncode,
        "python_version": ".".join(str(x) for x in _python_version_tuple()),
        "command": list(command) if command is not None else [],
        "error": error,
    }


def run_dbt_command(
    action: str,
    *,
    project_dir: str = "dbt",
    profiles_dir: str = "dbt",
    requested_mode: str | None = None,
    runner: Any = subprocess.run,
    report_path: str | Path = "outputs/reports/dbt_execution_report.json",
) -> dict[str, Any]:
    mode: str | None = None
    command: list[str] | None = None
    try:
        mode = resolve_dbt_mode(requested_mode=requested_mode)
        command = build_dbt_command(
            action,
            mode=mode,
            project_dir=project_dir,
            profiles_dir=profiles_dir,
        )
        result = runner(command, cwd=str(_repo_root()), check=False)
    except Exception as exc:
        payload = _report_payload(
            action=action,
            mode=mode,
            command=command,
            status="failed",
            error=str(exc),
        )
        write_dbt_execution_report(payload, report_path)
        raise

    payload = _report_payload(
        action=action,
        mode=mode,
        command=command,
        status="passed" if int(result.returncode) == 0 else "failed",
        returncode=int(result.returncode),
    )
    write_dbt_execution_report(payload, report_path)
    if int(result.returncode) != 0:
        raise RuntimeError(f"dbt {action} failed with exit code {int(result.returncode)}")
    return payload
