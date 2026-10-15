import hashlib
import json

import polars as pl
import pytest

from src.operations.environment_reproduction import compare_environment_runs


def fixture(root, score=1.0, input_sha="a"):
    root.mkdir()
    plan = {"config": {"seed": 1}, "implementation_sha256": "same",
            "input_resources": [{"sha256": input_sha, "bytes": 1}], "dependencies": {"polars": "fixture"}}
    (root / "study_plan.json").write_text(json.dumps(plan))
    outputs = []
    for name in ("heldout_evaluation", "training_candidates", "sensitivity"):
        frame = pl.DataFrame({"cancer_type": ["TCGA-BRCA"], "method": ["method"], "top_k": [1],
                              "rank": [1], "repeat": [1], "expression_threshold": [1.],
                              "pseudocount": [1.], "scale": [1.], "score": [score]})
        path = root / f"{name}.parquet"
        frame.write_parquet(path)
        outputs.append({"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    report = {"status": "completed", "outputs": outputs,
              "plan_sha256": hashlib.sha256(json.dumps(plan, sort_keys=True, separators=(",", ":")).encode()).hexdigest()}
    (root / "report.json").write_text(json.dumps(report))


def test_environment_comparison_tolerance_and_failure(tmp_path):
    fixture(tmp_path / "host")
    fixture(tmp_path / "near", 1 + 5e-12)
    fixture(tmp_path / "changed", 2.)
    output = tmp_path / "result.json"
    passed = compare_environment_runs(tmp_path / "host", tmp_path / "near", output)
    assert passed["status"] == "passed"
    assert passed["independent_human_reproduction"] == "not performed"
    assert compare_environment_runs(tmp_path / "host", tmp_path / "changed", output)["status"] == "failed"


def test_environment_comparison_rejects_changed_input(tmp_path):
    fixture(tmp_path / "host")
    fixture(tmp_path / "changed", input_sha="b")
    with pytest.raises(ValueError, match="input snapshots"):
        compare_environment_runs(tmp_path / "host", tmp_path / "changed", tmp_path / "result.json")
