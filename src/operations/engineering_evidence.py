"""Frozen engineering studies: isolated numerical diagnosis and verified evidence I/O."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import numpy as np
import polars as pl

from src.analytics.controlled_reference_study import lock_plan, sha256_file
from src.operations.environment_reproduction import compare_environment_runs

THREADS = {"POLARS_MAX_THREADS": "4", "OPENBLAS_NUM_THREADS": "1", "OMP_NUM_THREADS": "1"}
WORKER = Path("src/operations/engineering_runtime.py")
PILOT = Path("outputs/research/native_reference_pilot_v2")
PILOT_SOURCE = Path("outputs/research/protocol_sources/73429ce3b64c08e29850cac110a140ae230208ef3da518de71f27a2d3a939dcb/controlled_reference_study.py")
GLOBAL_SOURCE = Path("outputs/research/protocol_sources/dcb5d1c0a62aa3a465eea8c987ef42e84b44464eb6849a3f0ace3254dc42a0e1/controlled_reference_study.py")


def resource(path: Path) -> dict:
    return {"path": str(path), "sha256": sha256_file(path), "bytes": path.stat().st_size}


def verify(items: list[dict]) -> None:
    for item in items:
        p = Path(item["path"])
        if not p.is_file() or sha256_file(p) != item["sha256"]:
            raise ValueError(f"Evidence hash drift: {p}")


def write_once(path: Path, payload: dict) -> None:
    text = json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and json.loads(path.read_text()) != payload:
        raise RuntimeError(f"Frozen output differs: {path}")
    if not path.exists():
        path.write_text(text)


def image_id(name: str) -> str:
    return subprocess.check_output(["docker", "image", "inspect", name, "--format", "{{.Id}}"], text=True).strip()


def environment_command(name: str, image: str | None = None) -> list[str]:
    if image:
        return ["docker", "run", "--rm", "--cpus", "4", "--memory", "12g", "--network", "none",
                *[item for k, v in THREADS.items() for item in ("-e", f"{k}={v}")],
                "-v", f"{Path.cwd()}:/app", "-w", "/app", image, "python"]
    python = sys.executable if name == "macos142" else "data/research/engineering_runtimes/macos_144_fixed/bin/python"
    return [python]


def run_worker(command: list[str], arguments: list[str]) -> None:
    subprocess.run(command + [str(WORKER), *arguments], env={**os.environ, **THREADS}, check=True)


def compare_arrays(left: Path, right: Path) -> dict:
    with np.load(left, allow_pickle=False) as a, np.load(right, allow_pickle=False) as b:
        if a.files != b.files:
            raise ValueError("Diagnostic stage keys differ")
        diagnostics = []
        for key in a.files:
            x, y = a[key], b[key]
            same = x.shape == y.shape and np.array_equal(x, y)
            row = {"stage": key, "identical": same, "same_shape": x.shape == y.shape}
            if x.dtype.kind in "fi" and y.dtype.kind in "fi" and x.shape == y.shape:
                row.update(max_absolute_difference=float(np.max(np.abs(x - y))) if x.size else 0.,
                           outside_tolerance=int(np.sum(~np.isclose(x, y, rtol=1e-8, atol=1e-10))))
            diagnostics.append(row)
    return {"earliest_bitwise_difference": next((r["stage"] for r in diagnostics if not r["identical"]), None),
            "stages": diagnostics}


def numerical_study(prepare_only: bool = False) -> dict:
    root = Path("outputs/research/engineering_numerical_v1")
    private = Path("data/research/engineering_numerical_v1")
    globals_ = [Path("outputs/research") / n for n in ("native_reference_global_v1", "native_reference_paired_global_v1")]
    original = json.loads((PILOT / "study_plan.json").read_text())
    verify(original["input_resources"])
    if sha256_file(PILOT_SOURCE) != original["implementation_sha256"]:
        raise ValueError("Archived pilot source differs")
    manifest = Path("data/research/native_reference_pilot_v2/sample_split_manifest.parquet")
    report = json.loads((PILOT / "report.json").read_text())
    if sha256_file(manifest) != report["private_split_manifest_sha256"]:
        raise ValueError("Original pilot manifest differs")
    images = {"linux142": image_id("canceromicslake-replay:polars142"),
              "linux144": image_id("canceromicslake-dbt:latest")}
    environments = {n: environment_command(n, images.get(n)) for n in ("macos142", "macos144", "linux142", "linux144")}
    runtimes = {n: json.loads(subprocess.check_output(cmd + [str(WORKER), "runtime"],
                              env={**os.environ, **THREADS}, text=True)) for n, cmd in environments.items()}
    for n, details in runtimes.items():
        expected = {"numpy": "2.4.6", "scipy": "1.17.1", "PyYAML": "6.0.3",
                    "polars": "1.42.1" if n.endswith("142") else "1.44.2"}
        if details["dependencies"] != expected or details["python"] != "3.11.15":
            raise ValueError(f"Pinned runtime differs: {n}")
    resources = [resource(p) for p in (Path(__file__), WORKER, PILOT_SOURCE, GLOBAL_SOURCE, manifest,
                                     Path("research/Dockerfile.reproduction"),
                                     Path("src/operations/environment_reproduction.py"),
                                     PILOT / "study_plan.json", PILOT / "report.json", PILOT / "sensitivity.parquet",
                                     Path("outputs/research/environment_reproduction.json"))]
    resources += original["input_resources"]
    for p in globals_:
        global_plan = json.loads((p / "study_plan.json").read_text())
        if global_plan["implementation_sha256"] != sha256_file(GLOBAL_SOURCE):
            raise ValueError("Corrected global archived source differs")
        verify(global_plan["input_resources"])
        resources += [resource(p / f) for f in ("study_plan.json", "report.json", "heldout_evaluation.parquet",
                                               "training_candidates.parquet", "sensitivity.parquet")]
        resources.append(resource(Path("data/research") / p.name / "sample_split_manifest.parquet"))
    plan = {"study_id": root.name, "seed": 20261015, "tolerance": {"rtol": 1e-8, "atol": 1e-10},
            "images": images, "runtimes": runtimes, "resources": resources,
            "primary_diagnostic": {"cancer": "TCGA-LUAD", "repeat": 2, "expression_threshold": 1.,
                                   "pseudocount": 1., "scale": 1., "original_seed_preserved": True},
            "independent_human_reproduction": False}
    plan_hash = lock_plan(root / "study_plan.json", plan)
    if (root / "report.json").exists():
        previous = json.loads((root / "report.json").read_text())
        if previous["plan_sha256"] != plan_hash:
            raise RuntimeError("Numerical study plan differs")
        verify(previous["resources"])
        return previous
    if prepare_only:
        return {"status": "prepared", "plan_sha256": plan_hash}
    for name, cmd in environments.items():
        target = private / name
        run_worker(cmd, ["diagnose", "--source", str(PILOT_SOURCE), "--plan", str(PILOT / "study_plan.json"),
                         "--manifest", str(manifest), "--output", str(target)])
        print(f"diagnosed {name}", flush=True)
    comparisons = []
    for first, second in (("macos142", "linux142"), ("macos144", "linux144"),
                          ("macos142", "macos144"), ("linux142", "linux144")):
        result = compare_arrays(private / first / "intermediates.npz", private / second / "intermediates.npz")
        result.update(first=first, second=second)
        comparisons.append(result)
    original_values = pl.read_parquet(PILOT / "sensitivity.parquet").filter(
        (pl.col("cancer_type") == "TCGA-LUAD") & (pl.col("repeat") == 2) &
        (pl.col("expression_threshold") == 1.) & (pl.col("pseudocount") == 1.) & (pl.col("scale") == 1.))
    diagnostics = {n: json.loads((private / n / "diagnostic.json").read_text()) for n in environments}
    replay_checks = []
    for original_root in globals_:
        target = private / "corrected_global_linux" / original_root.name
        run_worker(environments["linux142"], ["replay", "--source", str(GLOBAL_SOURCE),
                   "--plan", str(original_root / "study_plan.json"), "--output", str(target)])
        reproduced = target / "public" / original_root.name
        result_path = root / f"{original_root.name}_comparison.json"
        check = compare_environment_runs(original_root, reproduced, result_path)
        old_manifest = pl.read_parquet(Path("data/research") / original_root.name / "sample_split_manifest.parquet")
        new_manifest = pl.read_parquet(target / "private" / original_root.name / "sample_split_manifest.parquet")
        keys = ["cancer_type", "source", "sample_id"]
        same_manifest = old_manifest.sort(keys).equals(new_manifest.sort(keys))
        replay_checks.append({"study_id": original_root.name, "status": check["status"],
                              "manifests_identical": same_manifest, "checks": check["checks"]})
        print(f"replayed {original_root.name}: {check['status']} manifest={same_manifest}", flush=True)
    verify(resources)
    payload = {"study_id": root.name, "plan_sha256": plan_hash, "execution_status": "completed",
               "historical_failure_preserved": True, "historical_failed_rows": original_values.height,
               "distinct_historical_statistics": original_values["abs_effect_spearman"].n_unique(),
               "historical_statistic": float(original_values["abs_effect_spearman"][0]),
               "diagnostics": diagnostics, "array_comparisons": comparisons, "corrected_global_replays": replay_checks,
               "numerical_acceptance": "passed" if all(c["status"] == "passed" and c["manifests_identical"]
                                                          for c in replay_checks) else "failed",
               "interpretation": "Earliest divergent intermediates locate numeric sensitivity; OS/library differences alone do not establish a cause.",
               "independent_human_reproduction": False, "publication_enabled": False,
               "resources": resources + [resource(p) for p in private.glob("*/diagnostic.json")] +
                   [resource(p) for p in private.glob("*/intermediates.npz")] +
                   [resource(p) for p in root.glob("*_comparison.json")]}
    write_once(root / "report.json", payload)
    return payload


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--prepare-only", action="store_true")
    args = p.parse_args()
    print(numerical_study(args.prepare_only).get("execution_status", "prepared"))
