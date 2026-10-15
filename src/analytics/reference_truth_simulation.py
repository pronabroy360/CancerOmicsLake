"""Prespecified synthetic truth tests; these do not validate real cancer genes."""
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
import json
from pathlib import Path

import numpy as np
import polars as pl
from scipy.stats import t

from src.analytics.controlled_reference_study import (
    StudyConfig, _top, evaluate_ranking, lock_plan, sha256_file,
)


@dataclass(frozen=True)
class SimulationConfig:
    seed: int = 20261004
    repetitions: int = 20
    genes: int = 400
    true_genes: int = 40
    nuisance_genes: int = 40
    samples: int = 24
    bootstraps: int = 30
    top_k: tuple[int, ...] = (25, 50)
    effect: float = 1.0
    study_id: str = "reference_truth_simulation_v1"


SCENARIOS = ("clean", "gtex_specific_bias", "adjacent_specific_bias", "shared_normal_bias", "null")


def generate_cohort(config: SimulationConfig, scenario: str, seed: int) -> tuple[dict, dict, np.ndarray]:
    if scenario not in SCENARIOS:
        raise ValueError("Unknown simulation scenario")
    rng = np.random.default_rng(seed)
    base = rng.uniform(0, 4, (config.genes, 1))
    # Shared patient variation preserves tumor/adjacent correlation; GTEx donors are independent.
    patient = rng.normal(0, .5, (config.genes, config.samples))
    log_values = {
        "tumor": base + patient + rng.normal(0, .4, patient.shape),
        "adjacent": base + patient + rng.normal(0, .4, patient.shape),
        "gtex": base + rng.normal(0, np.sqrt(.5**2 + .4**2), patient.shape),
    }
    truth = np.zeros(config.genes, dtype=bool)
    if scenario != "null":
        truth[:config.true_genes] = True
        log_values["tumor"][:config.true_genes] += config.effect
    nuisance = slice(config.true_genes, config.true_genes + config.nuisance_genes)
    if scenario in ("gtex_specific_bias", "shared_normal_bias"):
        log_values["gtex"][nuisance] -= config.effect * 1.5
    if scenario in ("adjacent_specific_bias", "shared_normal_bias"):
        log_values["adjacent"][nuisance] -= config.effect * 1.5
    # Randomize gene labels independently of expression draws so tie-breaking cannot favor truth.
    permutation = np.random.default_rng(config.seed).permutation(config.genes)
    matrices = {g: np.exp(value)[permutation] for g, value in log_values.items()}
    truth = truth[permutation]
    units = {g: [f"{'donor' if g == 'gtex' else 'case'}-{seed}-{i}" for i in range(config.samples)]
             for g in matrices}
    return matrices, units, truth


def average_precision(truth: np.ndarray, score: np.ndarray) -> float | None:
    if not truth.any():
        return None
    ordered = truth[_top(score, len(score))]
    precision = np.cumsum(ordered) / np.arange(1, len(ordered) + 1)
    return float(precision[ordered].mean())


def run_truth_simulation(output_root: str | Path = "outputs/research",
                         config: SimulationConfig | None = None) -> dict:
    config = config or SimulationConfig()
    if config.repetitions < 2 or config.samples < 4 or config.bootstraps < 20:
        raise ValueError("At least two repetitions, four samples, and twenty bootstrap draws required")
    if not 0 < config.true_genes < config.genes or config.true_genes + config.nuisance_genes > config.genes:
        raise ValueError("Invalid gene counts")
    if not config.top_k or min(config.top_k) < 1 or max(config.top_k) > config.genes:
        raise ValueError("Invalid top_k")
    if not np.isfinite(config.effect) or config.effect <= 0:
        raise ValueError("Effect must be finite and positive")
    # Reuse StudyConfig validation for the output identifier as well as ranking parameters.
    ranking = StudyConfig(study_id=config.study_id, training_bootstraps=config.bootstraps,
                          holdout_bootstraps=config.bootstraps, top_k=config.top_k)
    root = Path(output_root) / config.study_id
    plan = {"config": asdict(config), "scenarios": list(SCENARIOS),
            "implementation_sha256": sha256_file(Path(__file__)),
            "ranking_implementation_sha256": sha256_file(Path(__file__).with_name("controlled_reference_study.py")),
            "interpretation": "Synthetic truth recovery, not independent biological validation"}
    plan_hash = lock_plan(root / "study_plan.json", plan)
    rows = []
    for scenario_number, scenario in enumerate(SCENARIOS):
        for repetition in range(config.repetitions):
            seed = config.seed + scenario_number * 100000 + repetition * 100
            train, train_units, truth = generate_cohort(config, scenario, seed)
            holdout, holdout_units, heldout_truth = generate_cohort(config, scenario, seed + 1)
            assert np.array_equal(truth, heldout_truth)
            metrics, scores, _ = evaluate_ranking(train, holdout, train_units, holdout_units, ranking, seed + 2)
            for result in metrics:
                method, k = result["method"], result["top_k"]
                selected = _top(scores[method], k)
                row = {"scenario": scenario, "repetition": repetition, "method": method, "top_k": k,
                       "precision_at_k": float(truth[selected].mean()),
                       "recall_at_k": float(truth[selected].sum() / truth.sum()) if truth.any() else None,
                       "average_precision": average_precision(truth, scores[method]),
                       "positive_score_count": result["positive_score_count"],
                       "heldout_reference_replication_fraction": result["replication_fraction"]}
                rows.append(row)
    frame = pl.DataFrame(rows)
    path = root / "truth_metrics.parquet"
    frame.write_parquet(path)
    comparisons = []
    proposed = "reference_stability_lower_quantile"
    for scenario in SCENARIOS:
        for k in config.top_k:
            subset = frame.filter((pl.col("scenario") == scenario) & (pl.col("top_k") == k))
            target = subset.filter(pl.col("method") == proposed).sort("repetition")["precision_at_k"].to_numpy()
            for method in sorted(set(subset["method"]) - {proposed}):
                baseline = subset.filter(pl.col("method") == method).sort("repetition")["precision_at_k"].to_numpy()
                delta = target - baseline
                margin = float(t.ppf(.975, len(delta) - 1) * delta.std(ddof=1) / np.sqrt(len(delta)))
                comparisons.append({"scenario": scenario, "top_k": k, "baseline": method,
                                    "mean_precision_difference": float(delta.mean()),
                                    "monte_carlo_mean_ci_low": float(delta.mean() - margin),
                                    "monte_carlo_mean_ci_high": float(delta.mean() + margin)})
    report = {"status": "completed", "generated_at": datetime.now(UTC).isoformat(),
              "study_id": config.study_id, "plan_sha256": plan_hash, "metric_rows": frame.height,
              "output_sha256": sha256_file(path), "paired_precision_comparisons": comparisons,
              "claim_boundary": "Evidence conditional on this constructed simulation model; no real-gene validation or novelty guarantee",
              "limitations": ["Scenarios deliberately include method-aligned and shared-bias counterexamples",
                              "Shared normal bias is observationally indistinguishable from tumor biology here",
                              "Null top-k selection is forced; precision is zero, not a calibrated discovery probability",
                              "Monte Carlo intervals concern mean precision across simulated datasets; no multiplicity correction applied",
                              "Native study RRA-style baseline is a heuristic, not the full published RRA implementation"]}
    (root / "report.json").write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    return report
