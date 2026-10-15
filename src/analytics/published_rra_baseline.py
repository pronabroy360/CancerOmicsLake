"""Frozen, post-hoc published RRA ranking comparison on existing global splits."""
from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
import subprocess
from typing import Callable

import numpy as np
import polars as pl

from src.analytics.controlled_reference_study import (
    _effects, _matrix, _metrics, _sample_index, _top, assert_no_global_leakage,
    cluster_bootstrap, evaluate_ranking, expression_mask, load_study_config,
    lock_plan, sha256_file,
)


STUDIES = ("native_reference_global_v1", "native_reference_paired_global_v1")
STUDY_ID = "published_rra_baseline_v1"
SEED = 20261015
PACKAGE_VERSION = "1.2.1"
IMAGE = "canceromicslake-rra:1.2.1"


def _resource(path: Path) -> dict:
    return {"path": str(path), "bytes": path.stat().st_size, "sha256": sha256_file(path)}


def _check(path: Path, expected: str) -> None:
    if sha256_file(path) != expected:
        raise RuntimeError(f"Frozen resource hash drift: {path}")


def _load_frozen(root: Path, private_root: Path) -> tuple[dict, dict, pl.DataFrame, pl.DataFrame, pl.DataFrame]:
    plan_path, report_path = root / "study_plan.json", root / "report.json"
    plan, report = json.loads(plan_path.read_text()), json.loads(report_path.read_text())
    from src.analytics.controlled_reference_study import _canonical
    if (hashlib.sha256(_canonical(plan).encode()).hexdigest() != report["plan_sha256"]
            or report["status"] != "completed" or report["partition_scope"] != "global_across_all_configured_projects"
            or report["global_group_leakage_count"] != 0):
        raise RuntimeError(f"Frozen global study invalid: {root}")
    if plan["implementation_sha256"] != sha256_file(Path(__file__).with_name("controlled_reference_study.py")):
        raise RuntimeError("Frozen ranking implementation differs; use archived source, not changed code")
    for item in plan["input_resources"] + report["outputs"]:
        _check(Path(item["path"]), item["sha256"])
    manifest_path = private_root / root.name / "sample_split_manifest.parquet"
    _check(manifest_path, report["private_split_manifest_sha256"])
    manifest = pl.read_parquet(manifest_path)
    assert_no_global_leakage(manifest)
    if manifest.group_by("cancer_type", "source", "sample_id").len().filter(pl.col("len") > 1).height:
        raise RuntimeError("Duplicate source/specimen in frozen manifest")
    candidates = pl.read_parquet(root / "training_candidates.parquet")
    evaluation = pl.read_parquet(root / "heldout_evaluation.parquet")
    return plan, report, manifest, candidates, evaluation


def _image_identity() -> dict:
    try:
        result = subprocess.run(["docker", "image", "inspect", IMAGE, "--format", "{{json .}}"],
                                text=True, capture_output=True, check=True)
    except (OSError, subprocess.CalledProcessError) as exc:
        raise RuntimeError("RRA image unavailable; start Docker and run make build-published-rra") from exc
    data = json.loads(result.stdout)
    if not data.get("Id"):
        raise RuntimeError("RRA container image has no identity")
    return {"name": IMAGE, "id": data["Id"], "repo_digests": sorted(data.get("RepoDigests") or [])}


def _rank_inputs(genes: np.ndarray, matrices: dict[str, np.ndarray]) -> pl.DataFrame:
    adjacent, gtex = _effects(matrices)
    if len(genes) != len(set(genes.tolist())) or not np.isfinite(adjacent).all() or not np.isfinite(gtex).all():
        raise ValueError("RRA requires unique genes and finite effects")
    n = len(genes)
    # Canonical Ensembl order breaks equal absolute-effect ties in both lists.
    if genes.tolist() != sorted(genes.tolist()):
        raise ValueError("Genes must be in canonical Ensembl order")
    ranks = [np.empty(n, dtype=np.int64), np.empty(n, dtype=np.int64)]
    for i, effects in enumerate((adjacent, gtex)):
        ranks[i][np.argsort(-np.round(np.abs(effects), 12), kind="stable")] = np.arange(1, n + 1)
    return pl.DataFrame({"gene_id": genes, "adjacent_rank": ranks[0], "gtex_rank": ranks[1]})


def _validate_r_scores(frame: pl.DataFrame, genes: np.ndarray) -> np.ndarray:
    if frame.columns != ["gene_id", "score"] or frame.height != len(genes):
        raise ValueError("RRA score schema/row count mismatch")
    if frame["gene_id"].to_list() != genes.tolist():
        raise ValueError("RRA gene ordering or identity mismatch")
    scores = frame["score"].to_numpy().astype(float)
    if not np.isfinite(scores).all() or (scores < 0).any() or (scores > 1).any():
        raise ValueError("Invalid RRA score")
    return 1 - scores


def _verify_frozen(project: str, rows: list[dict], scores: dict, genes: np.ndarray,
                   candidates: pl.DataFrame, evaluation: pl.DataFrame, top_k: tuple[int, ...]) -> None:
    old = evaluation.filter(pl.col("cancer_type") == project)
    if old.height != len(rows):
        raise RuntimeError("Frozen evaluation method count differs")
    for row in rows:
        matching = old.filter((pl.col("method") == row["method"]) & (pl.col("top_k") == row["top_k"]))
        if matching.height != 1:
            raise RuntimeError("Frozen evaluation key mismatch")
        for metric in ("replication_fraction", "mean_worst_reference_effect"):
            if not np.isclose(row[metric], matching[metric][0], atol=1e-12):
                raise RuntimeError("Frozen evaluation metrics do not reproduce")
    for method, score in scores.items():
        saved = (candidates.filter((pl.col("cancer_type") == project) & (pl.col("method") == method))
                 .sort("rank"))
        expected = genes[_top(score, max(top_k))].tolist()
        if saved["gene_id"].to_list() != expected:
            raise RuntimeError(f"Frozen top-k candidates do not reproduce: {project}/{method}")


def _matrices(manifest: pl.DataFrame, project: str, config, sources: dict) -> tuple[np.ndarray, dict, dict]:
    selected = manifest.filter((pl.col("cancer_type") == project) & pl.col("selected"))
    index = _sample_index(sources["tcga"], sources["gtex"], project, config.projects[project])
    if selected.height != selected.join(index.select("source", "sample_id"),
                                        on=["source", "sample_id"], how="inner").height:
        raise RuntimeError("Frozen specimen is missing from current silver source")
    frames = {"tcga": _matrix(sources["tcga"], selected.filter(pl.col("source") == "TCGA"), "sample_id"),
              "gtex": _matrix(sources["gtex"], selected.filter(pl.col("source") == "GTEX"), "gtex_sample_id")}
    train_ids = selected.filter(pl.col("partition") == "development")["sample_id"].to_list()
    gene_sets = [set(frame.filter(~pl.any_horizontal(pl.col([c for c in frame.columns if c in train_ids]).is_null()))
                     ["gene_id"].to_list()) for frame in frames.values()]
    genes = sorted(set.intersection(*gene_sets))
    matrices, units = {}, {}
    for partition in ("development", "holdout"):
        matrices[partition], units[partition] = {}, {}
        for group in ("tumor", "adjacent", "gtex"):
            block = selected.filter((pl.col("partition") == partition) & (pl.col("group") == group)).sort("sample_id")
            frame = frames["gtex" if group == "gtex" else "tcga"]
            array = pl.DataFrame({"gene_id": genes}).join(frame, on="gene_id", how="left").select(
                block["sample_id"].to_list()).to_numpy()
            if not np.isfinite(array).all():
                raise RuntimeError("Frozen development universe has missing holdout measurements")
            matrices[partition][group] = array
            units[partition][group] = block["unit_id"].to_list()
    keep = expression_mask(matrices["development"], config.primary_expression_threshold,
                           config.minimum_prevalence)
    return np.asarray(genes)[keep], {p: {g: a[keep] for g, a in m.items()} for p, m in matrices.items()}, units


def _rra_rows(genes: np.ndarray, train: dict, test: dict, train_units: dict, test_units: dict,
              config, seed: int, score: np.ndarray, existing: list[dict],
              rra_style_score: np.ndarray) -> list[dict]:
    orientation = np.sign(sum(_effects(train)))
    selected = {k: _top(score, k) for k in config.top_k}
    heldout = _effects(test)
    rng = np.random.default_rng(seed)
    train_draws = []
    for _ in range(config.training_bootstraps):
        a, b = _effects(cluster_bootstrap(train, train_units, rng))
        train_draws.append(np.minimum(a * orientation, b * orientation))
    proposed = {(r["top_k"]): r for r in existing if r["method"] == "reference_stability_lower_quantile"}
    if len(proposed) != len(config.top_k):
        raise RuntimeError("Missing frozen proposed-method rows")
    draws = {k: [] for k in config.top_k}
    proposed_draws = {k: [] for k in config.top_k}
    proposed_score = np.maximum(0, np.quantile(train_draws, config.lower_quantile, axis=0))
    for _ in range(config.holdout_bootstraps):
        effects = _effects(cluster_bootstrap(test, test_units, rng))
        for k in config.top_k:
            draws[k].append(_metrics(selected[k], orientation, effects, config.replication_effect_threshold))
            proposed_draws[k].append(_metrics(_top(proposed_score, k), orientation, effects,
                                              config.replication_effect_threshold))
    a, b = _effects(train)
    rows = []
    for k, indices in selected.items():
        estimate = _metrics(indices, orientation, heldout, config.replication_effect_threshold)
        row = {"method": "published_rra", "top_k": k, "selected_count": len(indices), "gene_count": len(genes),
               "positive_score_count": int(np.sum(score[indices] > 0)),
               "discordant_reference_direction_count": int(np.sum(a[indices] * b[indices] < 0)),
               **estimate}
        row["discordant_reference_direction_fraction"] = row["discordant_reference_direction_count"] / k
        heuristic = set(_top(rra_style_score, k).tolist())
        published = set(indices.tolist())
        row["rra_style_topk_jaccard"] = len(heuristic & published) / len(heuristic | published)
        for metric in estimate:
            values = np.array([d[metric] for d in draws[k]])
            delta = np.array([p[metric] - d[metric] for p, d in zip(proposed_draws[k], draws[k])])
            row[f"{metric}_ci_low"], row[f"{metric}_ci_high"] = np.quantile(values, [.025, .975]).tolist()
            row[f"proposed_minus_baseline_{metric}"] = proposed[k][metric] - estimate[metric]
            row[f"proposed_minus_baseline_{metric}_ci_low"], row[f"proposed_minus_baseline_{metric}_ci_high"] = np.quantile(delta, [.025, .975]).tolist()
        rows.append(row)
    return rows


def run_study(output_root: Path = Path("outputs/research"), private_root: Path = Path("data/research"),
              silver_root: Path = Path("data/silver"), prepare_only: bool = False,
              runner: Callable[[Path, Path], None] | None = None,
              image_identity: dict | None = None) -> dict:
    root, private = output_root / STUDY_ID, private_root / STUDY_ID
    frozen = {}
    for name in STUDIES:
        frozen[name] = _load_frozen(output_root / name, private_root)
    image_identity = image_identity or _image_identity()
    if not image_identity.get("id"):
        raise RuntimeError("RRA image identity is required")
    implementation = [Path(__file__), Path(__file__).with_name("controlled_reference_study.py"),
                      Path("research/rra_runner.R"), Path("research/Dockerfile.rra")]
    resources = [_resource(path) for path in implementation]
    inputs = [_resource(silver_root / f"silver_expression_{name}.parquet") for name in ("tcga", "gtex")]
    ancestors = [_resource(output_root / name / filename) for name in STUDIES
                 for filename in ("study_plan.json", "report.json", "training_candidates.parquet", "heldout_evaluation.parquet")]
    ancestors += [_resource(private_root / name / "sample_split_manifest.parquet") for name in STUDIES]
    plan = {"study_id": STUDY_ID, "seed": SEED, "status": "frozen_before_metrics",
            "r_package": {"name": "RobustRankAggreg", "version": PACKAGE_VERSION,
                          "method": "RRA", "exact": False}, "r_image": image_identity,
            "studies": list(STUDIES), "implementation_resources": resources,
            "input_resources": inputs, "frozen_resources": ancestors,
            "interpretation": "Dependent input lists: RRA scores used only for ranking, never significance"}
    plan_hash = lock_plan(root / "study_plan.json", plan)
    if prepare_only:
        return {"status": "prepared", "study_id": STUDY_ID, "plan_sha256": plan_hash}
    private.mkdir(parents=True, exist_ok=True)
    def docker_runner(source: Path, target: Path) -> None:
        subprocess.run(["docker", "compose", "run", "--rm", "-T", "rra", "Rscript", "/app/research/rra_runner.R",
                        f"/app/{source}", f"/app/{target}"], check=True)
    runner = runner or docker_runner
    sources = {name: pl.scan_parquet(silver_root / f"silver_expression_{name}.parquet")
               for name in ("tcga", "gtex")}
    all_rows, audit = [], []
    for name in STUDIES:
        frozen_plan, _, manifest, candidates, evaluation = frozen[name]
        config = load_study_config(Path("configs") / ("controlled_reference_paired_study.yml" if
                                                frozen_plan["config"]["paired_only"] else "controlled_reference_study.yml"))
        if json.loads(json.dumps(asdict(config))) != frozen_plan["config"]:
            raise RuntimeError("Current config differs from frozen study")
        for number, project in enumerate(sorted(config.projects)):
            genes, matrices, units = _matrices(manifest, project, config, sources)
            seed = config.seed + number * 1000 + 2
            existing, scores, _ = evaluate_ranking(matrices["development"], matrices["holdout"],
                                                    units["development"], units["holdout"], config, seed)
            _verify_frozen(project, existing, scores, genes, candidates, evaluation, config.top_k)
            source = private / f"{name}_{project}_ranks.tsv"
            target = private / f"{name}_{project}_scores.tsv"
            _rank_inputs(genes, matrices["development"]).write_csv(source, separator="\t")
            runner(source, target)
            score = _validate_r_scores(pl.read_csv(target, separator="\t"), genes)
            rows = _rra_rows(genes, matrices["development"], matrices["holdout"],
                             units["development"], units["holdout"], config, seed, score, existing,
                             scores["rra_style"])
            all_rows.extend({"study_id": name, "cancer_type": project, **row} for row in rows)
            audit.append({"study_id": name, "cancer_type": project, "gene_count": len(genes),
                          "development_group_counts": {g: len(u) for g, u in units["development"].items()},
                          "holdout_group_counts": {g: len(u) for g, u in units["holdout"].items()},
                          "rra_input_sha256": sha256_file(source), "rra_output_sha256": sha256_file(target)})
    output = root / "comparison.csv"
    rows = pl.DataFrame(all_rows).sort("study_id", "cancer_type", "top_k")
    csv_text = rows.write_csv()
    if output.exists() and output.read_text() != csv_text:
        raise RuntimeError("Frozen RRA comparison differs on rerun; use a new study ID")
    if not output.exists():
        output.write_text(csv_text)
    report = {"status": "completed", "study_id": STUDY_ID, "generated_at": datetime.now(UTC).isoformat(),
              "plan_sha256": plan_hash, "r_image": image_identity, "r_package": plan["r_package"],
              "audits": audit, "comparisons": rows.to_dicts(), "outputs": [_resource(output)],
              "publication_enabled": False, "individual_identifiers_exported": False,
              "limitations": ["Post-v2 exploratory comparator, not independent confirmation",
                              "Shared tumor specimens violate independence assumptions for RRA p-values",
                              "No external workflow, independent reviewer, or biological validation"]}
    report_path = root / "report.json"
    if report_path.exists():
        prior = json.loads(report_path.read_text())
        if {k: v for k, v in prior.items() if k != "generated_at"} != {
                k: v for k, v in report.items() if k != "generated_at"}:
            raise RuntimeError("Frozen RRA report differs on rerun; use a new study ID")
        return prior
    report_path.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prepare-only", action="store_true")
    args = parser.parse_args()
    try:
        print(run_study(prepare_only=args.prepare_only)["status"])
    except (RuntimeError, subprocess.CalledProcessError) as exc:
        parser.exit(2, f"Published RRA study failed: {exc}\n")


if __name__ == "__main__":
    main()
