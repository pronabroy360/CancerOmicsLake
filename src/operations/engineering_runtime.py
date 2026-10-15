"""Private workers for numerical replay and the shared cached-expression task."""
from __future__ import annotations

import argparse
from contextlib import redirect_stdout
import hashlib
import importlib.util
from importlib.metadata import version
import io
import json
import os
from pathlib import Path
import platform
import sys

import numpy as np
import polars as pl


def load_source(path: Path):
    spec = importlib.util.spec_from_file_location("frozen_engineering_source", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def runtime() -> dict:
    text = io.StringIO()
    with redirect_stdout(text):
        np.show_config()
    return {"python": platform.python_version(), "system": platform.system(),
            "machine": platform.machine(), "platform": platform.platform(),
            "dependencies": {n: version(n) for n in ("numpy", "polars", "scipy", "PyYAML")},
            "threads": {n: os.environ.get(n, "unset") for n in
                        ("POLARS_MAX_THREADS", "OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS")},
            "numerical_libraries": text.getvalue()}


def array_hash(array: np.ndarray) -> str:
    if array.dtype.kind in "UOS":
        data = json.dumps(array.tolist(), ensure_ascii=True, separators=(",", ":")).encode()
    else:
        data = array.dtype.str.encode() + str(array.shape).encode() + np.ascontiguousarray(array).tobytes()
    return hashlib.sha256(data).hexdigest()


def diagnose(source: Path, plan_path: Path, manifest_path: Path, output: Path) -> dict:
    from scipy.stats import rankdata, spearmanr
    module = load_source(source)
    plan = json.loads(plan_path.read_text())
    config = module.StudyConfig(**{k: tuple(v) if k in ("top_k", "expression_thresholds", "pseudocounts", "scale_factors")
                                   else v for k, v in plan["config"].items()})
    sources = {Path(r["path"]).stem.removeprefix("silver_expression_"): pl.scan_parquet(r["path"])
               for r in plan["input_resources"]}
    manifest = pl.read_parquet(manifest_path)
    selected = manifest.filter((pl.col("cancer_type") == "TCGA-LUAD") & pl.col("selected"))
    frames = {"tcga": module._matrix(sources["tcga"], selected.filter(pl.col("source") == "TCGA"), "sample_id"),
              "gtex": module._matrix(sources["gtex"], selected.filter(pl.col("source") == "GTEX"), "gtex_sample_id")}
    train_ids = selected.filter(pl.col("partition") == "development")["sample_id"].to_list()
    genes = sorted(set.intersection(*[set(f.filter(~pl.any_horizontal(pl.col(
        [c for c in f.columns if c in train_ids]).is_null()))["gene_id"].to_list()) for f in frames.values()]))
    arrays = {"gene_order": np.asarray(genes)}
    matrices = {}
    for group in ("tumor", "adjacent", "gtex"):
        block = selected.filter((pl.col("partition") == "development") & (pl.col("group") == group)).sort("sample_id")
        frame = frames["gtex" if group == "gtex" else "tcga"]
        matrices[group] = pl.DataFrame({"gene_id": genes}).join(frame, on="gene_id", how="left").select(
            block["sample_id"].to_list()).to_numpy()
        arrays[f"samples_{group}"] = np.asarray(block["sample_id"].to_list())
        arrays[f"input_{group}"] = matrices[group]
    if any(not np.isfinite(a).all() for a in matrices.values()):
        raise ValueError("Missing or nonfinite original diagnostic measurements")
    seed = config.seed + sorted(config.projects).index("TCGA-LUAD") * 1000 + 3
    rng = np.random.default_rng(seed)
    n = min(max(2, int(min(m.shape[1] for m in matrices.values()) * .8)), config.max_units_per_group)
    for _ in range(3):
        indices = {g: np.sort(rng.choice(m.shape[1], n, replace=False)) for g, m in matrices.items()}
    subset = {g: m[:, indices[g]] for g, m in matrices.items()}
    keep = module.expression_mask(subset, 1., config.minimum_prevalence)
    arrays["filter_mask"] = keep
    for group in subset:
        arrays[f"indices_{group}"] = indices[group]
        arrays[f"median_{group}"] = np.median(subset[group][keep], axis=1)
    for group in ("adjacent", "gtex"):
        ratio = (arrays["median_tumor"] + 1.) / (arrays[f"median_{group}"] + 1.)
        arrays[f"ratio_{group}"] = ratio
        arrays[f"effect_{group}"] = module.fold_change(subset["tumor"][keep], subset[group][keep], 1., 1.)
        arrays[f"ranks_{group}"] = rankdata(np.abs(arrays[f"effect_{group}"]), method="average")
    rho = float(spearmanr(np.abs(arrays["effect_adjacent"]), np.abs(arrays["effect_gtex"])).statistic)
    output.mkdir(parents=True, exist_ok=True)
    np.savez(output / "intermediates.npz", **arrays)
    result = {"runtime": runtime(), "spearman": rho, "gene_count": len(genes), "filtered_gene_count": int(keep.sum()),
              "original_subsampling_seed": seed, "repeat": 2,
              "stages": {k: {"sha256": array_hash(v), "shape": list(v.shape), "dtype": str(v.dtype)}
                         for k, v in arrays.items()},
              "effect_ties": {g: int(len(arrays[f"effect_{g}"]) - len(np.unique(arrays[f"effect_{g}"])))
                              for g in ("adjacent", "gtex")}}
    (output / "diagnostic.json").write_text(json.dumps(result, indent=2, allow_nan=False))
    return result


def replay(source: Path, plan_path: Path, output: Path) -> None:
    import yaml
    plan = json.loads(plan_path.read_text())
    output.mkdir(parents=True, exist_ok=True)
    config = output / "replay_config.yml"
    config.write_text(yaml.safe_dump(plan["config"]))
    module = load_source(source)
    module.run_controlled_reference_study(config, "data/silver", output / "public", output / "private")


def filter_expression(normalized: np.ndarray, threshold: float = 1., prevalence: float = .2) -> tuple[np.ndarray, np.ndarray]:
    values = np.asarray(normalized, dtype=np.float64)
    if values.ndim != 2 or not np.isfinite(values).all() or (values < 0).any():
        raise ValueError("Expression must be a finite nonnegative matrix")
    if not np.isfinite(threshold) or threshold <= 0 or not 0 < prevalence < 1 or values.shape[1] == 0:
        raise ValueError("Invalid filtering settings")
    keep = (values >= threshold).sum(axis=1) >= values.shape[1] * prevalence
    return values[keep], keep


def cpm_task(source: Path, target: Path) -> None:
    frame = pl.read_csv(source, separator="\t")
    genes, samples = frame["gene_id"].to_list(), frame.columns[1:]
    if len(genes) != len(set(genes)) or not samples:
        raise ValueError("Duplicate genes or missing samples")
    values, keep = filter_expression(frame.select(samples).to_numpy())
    pl.DataFrame({"gene_id": np.asarray(genes)[keep], **{s: values[:, i] for i, s in enumerate(samples)}}).write_csv(
        target, separator="\t", float_precision=17)


def main() -> None:
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("runtime")
    for name in ("diagnose", "replay"):
        x = sub.add_parser(name)
        x.add_argument("--source", type=Path, required=True)
        x.add_argument("--plan", type=Path, required=True)
        x.add_argument("--output", type=Path, required=True)
        if name == "diagnose":
            x.add_argument("--manifest", type=Path, required=True)
    x = sub.add_parser("cpm")
    x.add_argument("--input", type=Path, required=True)
    x.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    if args.command == "runtime":
        print(json.dumps(runtime()))
    elif args.command == "diagnose":
        diagnose(args.source, args.plan, args.manifest, args.output)
    elif args.command == "replay":
        replay(args.source, args.plan, args.output)
    else:
        cpm_task(args.input, args.output)


if __name__ == "__main__":
    main()
