from dataclasses import replace

import numpy as np
import pytest

from src.analytics.reference_truth_simulation import (
    SimulationConfig, average_precision, generate_cohort, run_truth_simulation,
)


def test_simulation_is_deterministic_and_null_has_no_true_genes():
    config = SimulationConfig(genes=20, true_genes=4, nuisance_genes=4, samples=4)
    first, units, truth = generate_cohort(config, "clean", 1)
    again, _, _ = generate_cohort(config, "clean", 1)
    assert all(np.array_equal(first[g], again[g]) for g in first)
    assert units["tumor"] == units["adjacent"]
    assert truth.sum() == 4
    _, _, null = generate_cohort(config, "null", 1)
    assert not null.any()
    assert average_precision(null, np.arange(20)) is None


def test_truth_simulation_executes_and_rejects_changed_plan(tmp_path):
    config = SimulationConfig(repetitions=2, genes=20, true_genes=4, nuisance_genes=4,
                              samples=4, bootstraps=20, top_k=(3,))
    result = run_truth_simulation(tmp_path, config)
    assert result["status"] == "completed"
    assert result["metric_rows"] == 5 * 2 * 8
    assert len(result["paired_precision_comparisons"]) == 5 * 7
    with pytest.raises(RuntimeError, match="Frozen"):
        run_truth_simulation(tmp_path, replace(config, effect=2.0))
