import json
from pathlib import Path

import numpy as np
import pytest

from src.operations.engineering_evidence import compare_arrays, resource, verify, write_once
from src.operations.engineering_runtime import array_hash, filter_expression


def test_filter_boundaries_match_published_inclusive_semantics():
    values = np.array([[1., 0., 0., 0., 0.], [.999, 0., 0., 0., 0.], [2., 3., 0., 0., 0.]])
    result, keep = filter_expression(values)
    assert keep.tolist() == [True, False, True]
    assert np.array_equal(result, values[[0, 2]])
    for invalid in (np.array([[float("nan")]]), np.array([[-1.]]), np.empty((2, 0))):
        with pytest.raises(ValueError):
            filter_expression(invalid)


def test_array_diagnostic_reports_earliest_stage_and_keeps_tolerance(tmp_path):
    a, b = tmp_path / "a.npz", tmp_path / "b.npz"
    np.savez(a, gene_order=np.array(["ENSG1"]), ratio=np.array([1.]), effect=np.array([0.]))
    np.savez(b, gene_order=np.array(["ENSG1"]), ratio=np.array([1. + 1e-12]), effect=np.array([.1]))
    result = compare_arrays(a, b)
    assert result["earliest_bitwise_difference"] == "ratio"
    assert result["stages"][1]["outside_tolerance"] == 0
    assert result["stages"][2]["outside_tolerance"] == 1


def test_resource_and_frozen_output_reject_drift(tmp_path):
    path = tmp_path / "evidence.json"
    write_once(path, {"metric": 1.})
    evidence = resource(path)
    verify([evidence])
    write_once(path, {"metric": 1.})
    with pytest.raises(RuntimeError, match="Frozen"):
        write_once(path, {"metric": 2.})
    path.write_text(json.dumps({"metric": 3.}))
    with pytest.raises(ValueError, match="drift"):
        verify([evidence])


def test_private_array_hash_tracks_order():
    assert array_hash(np.array(["a", "b"])) != array_hash(np.array(["b", "a"]))
