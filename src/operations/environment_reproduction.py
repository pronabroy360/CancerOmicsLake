"""Compare independent-environment executions, not independent scientific reproduction."""
from datetime import UTC, datetime
import json
from pathlib import Path

import numpy as np
import polars as pl

from src.operations.research_review import _load_study


def compare_environment_runs(reference_root: str | Path, reproduced_root: str | Path,
                             output_path: str | Path) -> dict:
    reference, reference_plan, reference_resources = _load_study(Path(reference_root))
    reproduced, reproduced_plan, reproduced_resources = _load_study(Path(reproduced_root))
    if reference["status"] != "completed" or reproduced["status"] != "completed":
        raise ValueError("Both environment runs must complete")
    for key in ("config", "implementation_sha256"):
        if reference_plan[key] != reproduced_plan[key]:
            raise ValueError(f"Environment runs have different {key}")
    snapshots = lambda plan: sorted((item["sha256"], item["bytes"]) for item in plan["input_resources"])
    if snapshots(reference_plan) != snapshots(reproduced_plan):
        raise ValueError("Environment runs have different input snapshots")
    keys = {
        "heldout_evaluation": ["cancer_type", "method", "top_k"],
        "training_candidates": ["cancer_type", "method", "rank"],
        "sensitivity": ["cancer_type", "repeat", "expression_threshold", "pseudocount", "scale", "top_k"],
    }
    checks = []
    for name, order in keys.items():
        first = pl.read_parquet(Path(reference_root) / f"{name}.parquet").sort(order)
        second = pl.read_parquet(Path(reproduced_root) / f"{name}.parquet").sort(order)
        passed = first.schema == second.schema and first.shape == second.shape
        diagnostics = []
        if passed:
            for column, dtype in first.schema.items():
                if dtype.is_float():
                    left, right = first[column].to_numpy(), second[column].to_numpy()
                    close = np.isclose(left, right, rtol=1e-8, atol=1e-10, equal_nan=True)
                    difference = np.abs(left - right)
                    finite = difference[np.isfinite(difference)]
                    maximum = float(finite.max()) if finite.size else 0.
                    if maximum > 0 or not close.all():
                        diagnostics.append({"column": column, "max_absolute_finite_difference": maximum,
                                            "cells_outside_fixed_tolerance": int((~close).sum())})
                    passed = passed and bool(close.all())
                else:
                    passed = passed and first[column].equals(second[column])
        checks.append({"artifact": name, "passed": bool(passed), "reference_rows": first.height,
                       "reproduced_rows": second.height, "numeric_diagnostics": diagnostics})
    result = {"generated_at": datetime.now(UTC).isoformat(),
              "status": "passed" if all(c["passed"] for c in checks) else "failed",
              "reproduction_type": "Same-author execution in a separate software environment",
              "independent_human_reproduction": "not performed", "checks": checks,
              "reference_dependencies": reference_plan["dependencies"],
              "reproduced_dependencies": reproduced_plan["dependencies"],
              "resources": reference_resources + reproduced_resources,
              "tolerance": {"relative": 1e-8, "absolute": 1e-10},
              "claim_boundary": "Checks portable deterministic computation; not biological validation or an independent investigator's reproduction"}
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2) + "\n")
    return result
