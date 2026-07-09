from __future__ import annotations

from pathlib import Path

import pytest

from src.operations import dbt_runner


class _Result:
    def __init__(self, returncode: int) -> None:
        self.returncode = returncode


def test_resolve_dbt_mode_prefers_local_when_supported() -> None:
    mode = dbt_runner.resolve_dbt_mode(version_info=(3, 13, 0), docker_available=False)
    assert mode == "local"


def test_resolve_dbt_mode_falls_back_to_docker_when_local_is_unsupported() -> None:
    mode = dbt_runner.resolve_dbt_mode(version_info=(3, 14, 0), docker_available=True)
    assert mode == "docker"


def test_build_dbt_command_for_docker_contains_expected_invocation() -> None:
    command = dbt_runner.build_dbt_command("test", mode="docker")

    assert command[:5] == ["docker", "compose", "run", "--rm", "dbt"]
    assert "dbt test --project-dir dbt --profiles-dir dbt" in command[-1]


def test_run_dbt_command_writes_report(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(dbt_runner, "_repo_root", lambda: tmp_path)
    monkeypatch.setattr(dbt_runner, "resolve_dbt_mode", lambda requested_mode=None: "docker")

    def fake_runner(command: list[str], cwd: str, check: bool) -> _Result:
        assert cwd == str(tmp_path)
        assert command[0] == "docker"
        assert check is False
        return _Result(returncode=0)

    report_path = tmp_path / "outputs/reports/dbt_execution_report.json"
    payload = dbt_runner.run_dbt_command("run", runner=fake_runner, report_path=report_path)

    assert payload["status"] == "passed"
    assert payload["mode"] == "docker"
    assert report_path.exists()


def test_run_dbt_command_raises_and_persists_failure(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(dbt_runner, "_repo_root", lambda: tmp_path)
    monkeypatch.setattr(dbt_runner, "resolve_dbt_mode", lambda requested_mode=None: "local")

    def fake_runner(command: list[str], cwd: str, check: bool) -> _Result:
        assert Path(command[0]).name == "dbt"
        return _Result(returncode=2)

    report_path = tmp_path / "outputs/reports/dbt_execution_report.json"
    with pytest.raises(RuntimeError, match="dbt test failed"):
        dbt_runner.run_dbt_command("test", runner=fake_runner, report_path=report_path)

    assert report_path.exists()
