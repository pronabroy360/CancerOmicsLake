from pathlib import Path

from src.orchestration import pipeline_flow
from src.orchestration.pipeline_flow import _config_hash, _count_files, _write_run_metadata


def test_config_hash_is_stable(tmp_path: Path) -> None:
    cfg = tmp_path / "config.yml"
    cfg.write_text("project:\n  name: test\n", encoding="utf-8")
    h1 = _config_hash(str(cfg))
    h2 = _config_hash(str(cfg))
    assert h1 == h2
    assert len(h1) == 64


def test_count_files_counts_nested_files(tmp_path: Path) -> None:
    root = tmp_path / "data"
    (root / "a").mkdir(parents=True, exist_ok=True)
    (root / "a" / "one.txt").write_text("1", encoding="utf-8")
    (root / "a" / "two.txt").write_text("2", encoding="utf-8")
    assert _count_files(root) == 2


def test_write_run_metadata_persists_json(tmp_path: Path) -> None:
    payload = {"pipeline_run_id": "x", "status": "success"}
    out = _write_run_metadata(payload, tmp_path / "report.json")
    assert out.exists()
    assert "pipeline_run_id" in out.read_text(encoding="utf-8")


def test_run_pipeline_with_fallback_uses_inline_when_prefect_port_unavailable(monkeypatch) -> None:
    monkeypatch.setattr(
        pipeline_flow,
        "canceromicslake_pipeline",
        lambda **_: (_ for _ in ()).throw(RuntimeError("Unable to find an available port after multiple attempts")),
    )
    monkeypatch.setattr(
        pipeline_flow,
        "_execute_pipeline",
        lambda **_: {"pipeline_run_id": "fallback-run", "status": "success"},
    )
    payload = pipeline_flow.run_pipeline_with_fallback(config_path="configs/project_config.yml")
    assert payload["pipeline_run_id"] == "fallback-run"
