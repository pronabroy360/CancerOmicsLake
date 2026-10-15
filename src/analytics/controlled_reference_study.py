"""Frozen, patient/donor-held-out reference experiments over native TPM data."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
import hashlib
from importlib.metadata import version
import json
from pathlib import Path
import re
import subprocess
from typing import Any

import numpy as np
import polars as pl
from scipy.special import betainc
from scipy.stats import rankdata, spearmanr
import yaml


@dataclass(frozen=True)
class StudyConfig:
    study_id: str = "native_reference_v2"
    seed: int = 20261004
    projects: dict[str, str] = field(default_factory=lambda: {
        "TCGA-BRCA": "Breast - Mammary Tissue", "TCGA-LUAD": "Lung",
        "TCGA-COAD": "Colon - Transverse",
    })
    holdout_fraction: float = 0.5
    min_units_per_group: int = 8
    max_units_per_group: int = 40
    development_repeats: int = 50
    training_bootstraps: int = 200
    holdout_bootstraps: int = 200
    lower_quantile: float = 0.1
    replication_effect_threshold: float = 0.3
    top_k: tuple[int, ...] = (25, 50, 100)
    expression_thresholds: tuple[float, ...] = (0.0, 1.0)
    minimum_prevalence: float = 0.2
    pseudocounts: tuple[float, ...] = (0.1, 1.0, 10.0)
    scale_factors: tuple[float, ...] = (0.1, 1.0, 10.0)
    primary_expression_threshold: float = 1.0
    primary_pseudocount: float = 1.0
    pilot: bool = False
    paired_only: bool = False

    def __post_init__(self) -> None:
        if not re.fullmatch(r"[A-Za-z0-9_-]+", self.study_id):
            raise ValueError("study_id must contain only letters, numbers, underscore or hyphen")
        integers = (self.seed, self.min_units_per_group, self.max_units_per_group,
                    self.development_repeats, self.training_bootstraps, self.holdout_bootstraps)
        if any(isinstance(v, bool) or not isinstance(v, int) for v in integers):
            raise ValueError("study counts and seed must be integers")
        if not self.projects or any(p not in {"TCGA-BRCA", "TCGA-LUAD", "TCGA-COAD"}
                                    or not isinstance(t, str) or not t for p, t in self.projects.items()):
            raise ValueError("projects must map supported TCGA projects to one GTEx tissue each")
        if not 0.2 <= self.holdout_fraction <= 0.8 or self.seed < 0:
            raise ValueError("invalid split fraction or seed")
        if self.min_units_per_group < 4 or self.max_units_per_group < self.min_units_per_group:
            raise ValueError("invalid group size bounds")
        if self.development_repeats < 2 or min(self.training_bootstraps, self.holdout_bootstraps) < 20:
            raise ValueError("at least 2 development repeats and 20 bootstrap draws are required")
        if not 0 < self.lower_quantile < 0.5 or not 0 < self.minimum_prevalence <= 1:
            raise ValueError("invalid quantile or prevalence")
        if (not 0 < self.replication_effect_threshold <= 1 or not isinstance(self.pilot, bool)
                or not isinstance(self.paired_only, bool)):
            raise ValueError("invalid replication threshold or pilot flag")
        if not self.top_k or any(isinstance(k, bool) or not isinstance(k, int) or k < 1 for k in self.top_k):
            raise ValueError("top_k must contain positive integers")
        for values, allow_zero in [(self.expression_thresholds, True), (self.pseudocounts, False),
                                   (self.scale_factors, False)]:
            if not values or any(not np.isfinite(v) or v < 0 or (not allow_zero and v == 0)
                                 for v in values):
                raise ValueError("thresholds and scales must be finite with valid ranges")
        if self.primary_expression_threshold not in self.expression_thresholds:
            raise ValueError("primary expression threshold must be in sensitivity grid")
        if self.primary_pseudocount not in self.pseudocounts:
            raise ValueError("primary pseudocount must be in sensitivity grid")


def load_study_config(path: str | Path) -> StudyConfig:
    payload = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("study configuration must be a mapping")
    for key in ("top_k", "expression_thresholds", "pseudocounts", "scale_factors"):
        if key in payload:
            payload[key] = tuple(payload[key])
    return StudyConfig(**payload)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)


def lock_plan(path: Path, plan: dict[str, Any]) -> str:
    """A changed protocol or input snapshot requires a new study identifier."""
    serialized = _canonical(plan)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if _canonical(json.loads(path.read_text())) != serialized:
            raise RuntimeError("Frozen study plan differs; use a new study_id for changed inputs or parameters")
    else:
        with path.open("x", encoding="utf-8") as handle:
            handle.write(json.dumps(plan, indent=2))
    return hashlib.sha256(serialized.encode()).hexdigest()


def grouped_partition(index: pl.DataFrame, fraction: float, seed: int) -> pl.DataFrame:
    """Partition complete TCGA cases and GTEx donors, stratified by group availability."""
    units = (index.group_by(["source", "unit_id"])
             .agg(pl.col("group").unique().sort().str.join("|").alias("stratum"))
             .sort(["source", "stratum", "unit_id"]))
    rng = np.random.default_rng(seed)
    assignments = []
    for block in units.partition_by(["source", "stratum"], maintain_order=True):
        rows = block.to_dicts()
        order = rng.permutation(len(rows))
        holdout_n = min(len(rows) - 1, max(1, int(round(len(rows) * fraction)))) if len(rows) > 1 else 0
        holdout = set(order[:holdout_n].tolist())
        for i, row in enumerate(rows):
            assignments.append({"source": row["source"], "unit_id": row["unit_id"],
                                "partition": "holdout" if i in holdout else "development"})
    return index.join(pl.DataFrame(assignments), on=["source", "unit_id"], how="left")


def global_partition(index: pl.DataFrame, fraction: float, seed: int) -> pl.DataFrame:
    """Keep shared donors in one fold, stratifying by project/group availability."""
    qualified = index.rename({"group": "biological_group"}).with_columns(
        pl.concat_str("cancer_type", "biological_group", separator=":").alias("group"))
    split = grouped_partition(qualified, fraction, seed).drop("group").rename(
        {"biological_group": "group"})
    assert_no_global_leakage(split)
    return split


def assert_no_global_leakage(split: pl.DataFrame) -> None:
    crossing = split.group_by("source", "unit_id").agg(pl.col("partition").n_unique())
    if crossing.filter(pl.col("partition") > 1).height:
        raise RuntimeError("Global patient/donor leakage across development and holdout partitions")


def select_balanced_units(split: pl.DataFrame, maximum: int, seed: int,
                          paired_only: bool = False) -> pl.DataFrame:
    rng = np.random.default_rng(seed)
    blocks = []
    for partition in ("development", "holdout"):
        subset = split.filter(pl.col("partition") == partition)
        groups = {g: subset.filter(pl.col("group") == g).sort("unit_id")
                  for g in ("tumor", "adjacent", "gtex")}
        shared = sorted(set(groups["tumor"]["unit_id"]) & set(groups["adjacent"]["unit_id"]))
        n = min(maximum, *(frame.height for frame in groups.values()))
        if paired_only:
            n = min(n, len(shared))
            if n == 0:
                raise ValueError("No paired cases in a study partition")
            case_ids = rng.choice(shared, n, replace=False).tolist()
            for group in ("tumor", "adjacent"):
                blocks.append(groups[group].filter(pl.col("unit_id").is_in(case_ids)))
            blocks.append(groups["gtex"][rng.choice(groups["gtex"].height, n, replace=False).tolist()])
        else:
            for frame in groups.values():
                blocks.append(frame[rng.choice(frame.height, n, replace=False).tolist()])
    return pl.concat(blocks).sort(["partition", "group", "sample_id"])


def rank_biserial(tumor: np.ndarray, normal: np.ndarray) -> np.ndarray:
    """Signed U effect: positive means tumor values tend to exceed normal values."""
    n, m = tumor.shape[1], normal.shape[1]
    if not n or not m:
        raise ValueError("effect requires nonempty groups")
    ranks = rankdata(np.concatenate([tumor, normal], axis=1), axis=1, method="average")
    u = ranks[:, :n].sum(axis=1) - n * (n + 1) / 2
    return 2 * u / (n * m) - 1


def fold_change(tumor: np.ndarray, normal: np.ndarray, pseudocount: float,
                scale: float = 1.0, scale_pseudocount: bool = False) -> np.ndarray:
    offset = pseudocount * scale if scale_pseudocount else pseudocount
    return np.log2((np.median(tumor, axis=1) * scale + offset) /
                   (np.median(normal, axis=1) * scale + offset))


def expression_mask(matrices: dict[str, np.ndarray], threshold: float,
                    prevalence: float) -> np.ndarray:
    return np.maximum.reduce([(value >= threshold).mean(axis=1)
                              for value in matrices.values()]) >= prevalence


def _top(score: np.ndarray, k: int) -> np.ndarray:
    # Arrays are ordered by canonical Ensembl ID, providing deterministic tie breaking.
    return np.argsort(-np.round(score, 12), kind="stable")[:min(k, len(score))]


def _jaccard(a: np.ndarray, b: np.ndarray) -> float:
    left, right = set(a.tolist()), set(b.tolist())
    return len(left & right) / len(left | right) if left | right else 0.0


def _correlation(a: np.ndarray, b: np.ndarray) -> float | None:
    if len(a) < 2 or np.ptp(a) == 0 or np.ptp(b) == 0:
        return None
    return float(spearmanr(a, b).statistic)


def _effects(matrices: dict[str, np.ndarray]) -> tuple[np.ndarray, np.ndarray]:
    return (rank_biserial(matrices["tumor"], matrices["adjacent"]),
            rank_biserial(matrices["tumor"], matrices["gtex"]))


def ranking_scores(matrices: dict[str, np.ndarray], pseudocount: float) -> tuple[dict[str, np.ndarray], dict[str, np.ndarray]]:
    adjacent, gtex = _effects(matrices)
    orientation = np.sign(adjacent + gtex)
    minimum = np.minimum(orientation * adjacent, orientation * gtex)
    percentile = np.stack([rankdata(-np.abs(v), method="average") / len(v)
                           for v in (adjacent, gtex)])
    ordered = np.sort(percentile, axis=0)
    # RRA-style order-statistic score only; shared tumor samples violate its independent-list null.
    rra_score = 1 - np.minimum(1, 2 * np.minimum(betainc(1, 2, ordered[0]),
                                               betainc(2, 1, ordered[1])))
    scores = {
        "gtex_log2_fc": np.abs(fold_change(matrices["tumor"], matrices["gtex"], pseudocount)),
        "adjacent_log2_fc": np.abs(fold_change(matrices["tumor"], matrices["adjacent"], pseudocount)),
        "gtex_rank_biserial": np.abs(gtex),
        "adjacent_rank_biserial": np.abs(adjacent),
        "mean_rank": 1 - percentile.mean(axis=0),
        "rra_style": rra_score,
        "reference_maximin": np.maximum(0, minimum),
    }
    directions = {name: orientation for name in scores}
    for name in ("gtex_log2_fc", "gtex_rank_biserial"):
        directions[name] = np.sign(gtex)
    for name in ("adjacent_log2_fc", "adjacent_rank_biserial"):
        directions[name] = np.sign(adjacent)
    return scores, directions


def cluster_bootstrap(matrices: dict[str, np.ndarray], units: dict[str, list[str]],
                      rng: np.random.Generator) -> dict[str, np.ndarray]:
    case_units = sorted(set(units["tumor"]) | set(units["adjacent"]))
    for _ in range(100):
        draws = rng.choice(case_units, len(case_units), replace=True).tolist()
        indices = {g: [i for unit in draws for i, value in enumerate(units[g]) if value == unit]
                   for g in ("tumor", "adjacent")}
        if all(len(value) >= 2 for value in indices.values()):
            break
    else:
        raise RuntimeError("Insufficient TCGA groups for cluster bootstrap")
    donors = sorted(set(units["gtex"]))
    donor_draws = rng.choice(donors, len(donors), replace=True).tolist()
    indices["gtex"] = [i for donor in donor_draws for i, value in enumerate(units["gtex"]) if value == donor]
    return {group: matrix[:, indices[group]] for group, matrix in matrices.items()}


def _metrics(selected: np.ndarray, orientation: np.ndarray, effects: tuple[np.ndarray, np.ndarray],
             threshold: float) -> dict[str, float]:
    worst = np.minimum(effects[0][selected] * orientation[selected],
                       effects[1][selected] * orientation[selected])
    return {"replication_fraction": float(np.mean(worst >= threshold)),
            "mean_worst_reference_effect": float(worst.mean())}


def evaluate_ranking(train: dict[str, np.ndarray], test: dict[str, np.ndarray],
                     train_units: dict[str, list[str]], test_units: dict[str, list[str]],
                     config: StudyConfig, seed: int) -> tuple[list[dict], dict[str, np.ndarray], dict[str, np.ndarray]]:
    scores, directions = ranking_scores(train, config.primary_pseudocount)
    orientation = directions["reference_maximin"]
    rng = np.random.default_rng(seed)
    draws = []
    for _ in range(config.training_bootstraps):
        adjacent, gtex = _effects(cluster_bootstrap(train, train_units, rng))
        draws.append(np.minimum(adjacent * orientation, gtex * orientation))
    scores["reference_stability_lower_quantile"] = np.maximum(
        0, np.quantile(draws, config.lower_quantile, axis=0))
    directions["reference_stability_lower_quantile"] = orientation
    selections = {(name, k): _top(values, k) for name, values in scores.items() for k in config.top_k}
    heldout_effects = _effects(test)
    estimates = {key: _metrics(selection, directions[key[0]], heldout_effects,
                              config.replication_effect_threshold) for key, selection in selections.items()}
    bootstrap = {key: [] for key in selections}
    for _ in range(config.holdout_bootstraps):
        effects = _effects(cluster_bootstrap(test, test_units, rng))
        for key, selection in selections.items():
            bootstrap[key].append(_metrics(selection, directions[key[0]], effects, config.replication_effect_threshold))
    rows = []
    proposed = "reference_stability_lower_quantile"
    for (name, k), estimate in estimates.items():
        row = {"method": name, "top_k": k, "selected_count": len(selections[name, k]),
               "positive_score_count": int(np.sum(scores[name][selections[name, k]] > 0)),
               "gene_count": len(orientation), **estimate}
        row["heldout_adjacent_jaccard"] = _jaccard(selections[name, k], _top(np.abs(heldout_effects[0]), k))
        row["heldout_gtex_jaccard"] = _jaccard(selections[name, k], _top(np.abs(heldout_effects[1]), k))
        for metric in estimate:
            values = np.array([d[metric] for d in bootstrap[name, k]])
            delta = np.array([d[metric] for d in bootstrap[proposed, k]]) - values
            row[f"{metric}_ci_low"], row[f"{metric}_ci_high"] = np.quantile(values, [0.025, 0.975]).tolist()
            row[f"proposed_minus_baseline_{metric}"] = estimates[proposed, k][metric] - estimate[metric]
            row[f"proposed_minus_baseline_{metric}_ci_low"], row[f"proposed_minus_baseline_{metric}_ci_high"] = np.quantile(delta, [0.025, 0.975]).tolist()
        rows.append(row)
    return rows, scores, directions


def development_sensitivity(matrices: dict[str, np.ndarray], units: dict[str, list[str]],
                            config: StudyConfig, seed: int) -> list[dict]:
    rng = np.random.default_rng(seed)
    n = min(max(2, int(min(m.shape[1] for m in matrices.values()) * 0.8)), config.max_units_per_group)
    rows = []
    for repeat in range(config.development_repeats):
        if config.paired_only:
            selected = paired_subsample_indices(units, n, rng)
        else:
            selected = {g: np.sort(rng.choice(m.shape[1], n, replace=False)) for g, m in matrices.items()}
        subset = {g: m[:, selected[g]] for g, m in matrices.items()}
        for threshold in config.expression_thresholds:
            mask = expression_mask(subset, threshold, config.minimum_prevalence)
            if mask.sum() < max(config.top_k):
                continue
            filtered = {g: m[mask] for g, m in subset.items()}
            adjacent_rb, gtex_rb = _effects(filtered)
            for pseudo in config.pseudocounts:
                baseline = [fold_change(filtered["tumor"], filtered[g], pseudo) for g in ("adjacent", "gtex")]
                for scale in config.scale_factors:
                    effects = [fold_change(filtered["tumor"], filtered[g], pseudo, scale) for g in ("adjacent", "gtex")]
                    adjusted = [fold_change(filtered["tumor"], filtered[g], pseudo, scale, True) for g in ("adjacent", "gtex")]
                    for k in config.top_k:
                        rows.append({"repeat": repeat, "expression_threshold": threshold,
                                     "pseudocount": pseudo, "scale": scale, "top_k": k,
                                     "group_size": n, "gene_count": int(mask.sum()),
                                     "reference_jaccard": _jaccard(_top(np.abs(effects[0]), k), _top(np.abs(effects[1]), k)),
                                     "rank_biserial_reference_jaccard": _jaccard(_top(np.abs(adjacent_rb), k), _top(np.abs(gtex_rb), k)),
                                     "abs_effect_spearman": _correlation(np.abs(effects[0]), np.abs(effects[1])),
                                     "fixed_pseudocount_scale_jaccard": _jaccard(_top(np.abs(baseline[1]), k), _top(np.abs(effects[1]), k)),
                                     "scaled_pseudocount_scale_jaccard": _jaccard(_top(np.abs(baseline[1]), k), _top(np.abs(adjusted[1]), k))})
    return rows


def paired_subsample_indices(units: dict[str, list[str]], n: int,
                             rng: np.random.Generator) -> dict[str, np.ndarray]:
    cases = sorted(set(units["tumor"]))
    if set(cases) != set(units["adjacent"]) or any(len(set(units[g])) != len(units[g]) for g in units):
        raise ValueError("Paired subsampling requires one measurement per matched case and GTEx donor")
    selected_cases = set(rng.choice(cases, n, replace=False).tolist())
    indices = {g: np.array([i for i, unit in enumerate(units[g]) if unit in selected_cases])
               for g in ("tumor", "adjacent")}
    indices["gtex"] = np.sort(rng.choice(len(units["gtex"]), n, replace=False))
    return indices


def _sample_index(tcga: pl.LazyFrame, gtex: pl.LazyFrame, project: str, tissue: str) -> pl.DataFrame:
    tumor = (tcga.filter((pl.col("project_id") == project) & (pl.col("expression_unit") == "TPM") &
                        pl.col("sample_type").is_in(["Primary Tumor", "Solid Tissue Normal"]))
             .select("sample_id", pl.col("case_id").alias("unit_id"),
                     pl.when(pl.col("sample_type") == "Primary Tumor").then(pl.lit("tumor"))
                     .otherwise(pl.lit("adjacent")).alias("group")).unique().collect())
    normal = (gtex.filter((pl.col("tissue_site") == tissue) & (pl.col("expression_unit") == "TPM"))
              .select(pl.col("gtex_sample_id").alias("sample_id"), pl.col("donor_id").alias("unit_id"))
              .unique().collect().with_columns(pl.lit("gtex").alias("group")))
    for frame in (tumor, normal):
        if frame.filter(pl.col("sample_id").is_null() | pl.col("unit_id").is_null() |
                        (pl.col("sample_id") == "") | (pl.col("unit_id") == "")).height:
            raise ValueError("Missing sample or patient/donor identity; split would not be verifiable")
    index = pl.concat([tumor.with_columns(pl.lit("TCGA").alias("source")),
                       normal.with_columns(pl.lit("GTEX").alias("source"))])
    if index.group_by(["source", "sample_id"]).len().filter(pl.col("len") > 1).height:
        raise ValueError("Sample mapped to multiple biological units or groups")
    return index.sort("sample_id").unique(["source", "unit_id", "group"], keep="first", maintain_order=True)


def _matrix(source: pl.LazyFrame, selected: pl.DataFrame, sample_column: str) -> pl.DataFrame:
    identifiers = selected["sample_id"].to_list()
    frame = (source.filter(pl.col(sample_column).is_in(identifiers) & (pl.col("expression_unit") == "TPM"))
             .select(pl.col("gene_id").str.replace(r"\.\d+(_PAR_Y)?$", "${1}"), pl.col(sample_column).alias("sample_id"),
                     "expression_value").collect())
    if frame.filter(pl.col("gene_id").is_null() | ~pl.col("gene_id").str.contains(r"^ENSG[0-9]+(?:_PAR_Y)?$") |
                    pl.col("expression_value").is_null() | ~pl.col("expression_value").is_finite() |
                    (pl.col("expression_value") < 0)).height:
        raise ValueError("Invalid Ensembl identifiers or nonfinite/negative expression")
    if frame.group_by(["gene_id", "sample_id"]).len().filter(pl.col("len") > 1).height:
        raise ValueError("Duplicate gene/sample measurements; resolve upstream before the study")
    return frame.pivot(on="sample_id", index="gene_id", values="expression_value")


def run_controlled_reference_study(config_path: str | Path, silver_dir: str | Path = "data/silver",
                                   output_root: str | Path = "outputs/research",
                                   private_root: str | Path = "data/research") -> dict[str, Any]:
    config = load_study_config(config_path)
    root = Path(output_root) / config.study_id
    inputs = {name: Path(silver_dir) / f"silver_expression_{name}.parquet" for name in ("tcga", "gtex")}
    resources = [{"path": str(path), "bytes": path.stat().st_size, "sha256": sha256_file(path)}
                 for path in inputs.values()]
    try:
        revision = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=False).stdout.strip()
    except OSError:
        revision = "unavailable"
    plan = {"protocol_version": "1.1", "config": asdict(config), "input_resources": resources,
            "code_revision": revision, "implementation_sha256": sha256_file(Path(__file__)),
            "dependencies": {name: version(name) for name in ("numpy", "polars", "scipy", "PyYAML")}}
    plan_hash = lock_plan(root / "study_plan.json", plan)
    sources = {name: pl.scan_parquet(path) for name, path in inputs.items()}
    splits, audit, sensitivity, evaluations, candidates = [], [], [], [], []
    indexes = []
    for project, tissue in sorted(config.projects.items()):
        index = _sample_index(sources["tcga"], sources["gtex"], project, tissue)
        if config.paired_only:
            paired = sorted(set(index.filter(pl.col("group") == "tumor")["unit_id"]) &
                            set(index.filter(pl.col("group") == "adjacent")["unit_id"]))
            index = index.filter((pl.col("source") == "GTEX") | pl.col("unit_id").is_in(paired))
        indexes.append(index.with_columns(pl.lit(project).alias("cancer_type")))
    global_split = global_partition(pl.concat(indexes), config.holdout_fraction, config.seed)
    for project_number, (project, tissue) in enumerate(sorted(config.projects.items())):
        seed = config.seed + project_number * 1000
        index = indexes[project_number]
        split = global_split.filter(pl.col("cancer_type") == project)
        counts = split.group_by(["partition", "group"]).len().to_dicts()
        if any(split.filter((pl.col("partition") == p) & (pl.col("group") == g)).height < config.min_units_per_group
               for p in ("development", "holdout") for g in ("tumor", "adjacent", "gtex")):
            audit.append({"cancer_type": project, "tissue": tissue, "status": "insufficient_groups", "counts": counts})
            continue
        selected = select_balanced_units(split, config.max_units_per_group, seed + 1, config.paired_only)
        development_units = set(selected.filter(pl.col("partition") == "development").select("source", "unit_id").iter_rows())
        holdout_units = set(selected.filter(pl.col("partition") == "holdout").select("source", "unit_id").iter_rows())
        if development_units & holdout_units:
            raise RuntimeError("Patient/donor leakage across development and holdout partitions")
        splits.append(split.with_columns(pl.lit(project).alias("cancer_type"),
                                        pl.col("sample_id").is_in(selected["sample_id"].to_list()).alias("selected")))
        frames = {"tcga": _matrix(sources["tcga"], selected.filter(pl.col("source") == "TCGA"), "sample_id"),
                  "gtex": _matrix(sources["gtex"], selected.filter(pl.col("source") == "GTEX"), "gtex_sample_id")}
        matrices, units, genes = {}, {}, None
        train_ids = selected.filter(pl.col("partition") == "development")
        train_sets = [set(frame.filter(~pl.any_horizontal(pl.col([c for c in frame.columns if c in train_ids["sample_id"]]).is_null()))["gene_id"].to_list())
                      for frame in frames.values()]
        gene_ids = sorted(set.intersection(*train_sets))
        for partition in ("development", "holdout"):
            matrices[partition], units[partition] = {}, {}
            for group in ("tumor", "adjacent", "gtex"):
                block = selected.filter((pl.col("partition") == partition) & (pl.col("group") == group)).sort("sample_id")
                frame = frames["gtex" if group == "gtex" else "tcga"]
                ordered = pl.DataFrame({"gene_id": gene_ids}).join(frame, on="gene_id", how="left")
                array = ordered.select(block["sample_id"].to_list()).to_numpy()
                if not np.isfinite(array).all():
                    raise ValueError("Missing held-out measurements on development-defined gene universe")
                matrices[partition][group] = array
                units[partition][group] = block["unit_id"].to_list()
        keep = expression_mask(matrices["development"], config.primary_expression_threshold, config.minimum_prevalence)
        if keep.sum() < max(config.top_k):
            raise ValueError("Filtered development universe is smaller than requested top_k")
        filtered = {p: {g: a[keep] for g, a in m.items()} for p, m in matrices.items()}
        genes = np.array(gene_ids)[keep]
        evaluation_rows, scores, directions = evaluate_ranking(filtered["development"], filtered["holdout"],
                                                              units["development"], units["holdout"], config, seed + 2)
        evaluations.extend({"cancer_type": project, "tissue": tissue, **row} for row in evaluation_rows)
        sensitivity.extend({"cancer_type": project, "tissue": tissue, **row} for row in
                           development_sensitivity(matrices["development"], units["development"], config, seed + 3))
        for method, score in scores.items():
            for rank, i in enumerate(_top(score, max(config.top_k)), start=1):
                candidates.append({"cancer_type": project, "tissue": tissue, "method": method,
                                   "gene_id": genes[i], "rank": rank, "training_score": float(score[i]),
                                   "training_direction": int(directions[method][i])})
        shared_cases = set(index.filter(pl.col("group") == "tumor")["unit_id"]) & set(index.filter(pl.col("group") == "adjacent")["unit_id"])
        audit.append({"cancer_type": project, "tissue": tissue, "status": "evaluated",
                      "available_counts": counts, "selected_counts": selected.group_by(["partition", "group"]).len().to_dicts(),
                      "matched_tcga_cases_available": len(shared_cases), "gene_count_before_filter": len(gene_ids),
                      "gene_count_after_training_filter": len(genes), "group_leakage_count": 0,
                      "paired_only": config.paired_only,
                      "reference_control": "identical tumor sample set and equal reference sizes within each partition"})
    if not evaluations:
        raise RuntimeError("No cancer has sufficient donor/case-separated development and holdout groups")
    private = Path(private_root) / config.study_id
    private.mkdir(parents=True, exist_ok=True)
    split_path = private / "sample_split_manifest.parquet"
    manifest = pl.concat(splits)
    assert_no_global_leakage(manifest)
    manifest.write_parquet(split_path)
    result_paths = []
    for name, rows in [("sensitivity", sensitivity), ("heldout_evaluation", evaluations), ("training_candidates", candidates)]:
        path = root / f"{name}.parquet"
        pl.DataFrame(rows).write_parquet(path)
        result_paths.append({"name": name, "path": str(path), "sha256": sha256_file(path), "rows": len(rows)})
    report = {"status": "completed" if len(audit) == len(config.projects) and all(a["status"] == "evaluated" for a in audit) else "partial",
              "generated_at": datetime.now(UTC).isoformat(), "study_id": config.study_id,
              "pilot": config.pilot, "plan_sha256": plan_hash, "git_commit": revision,
              "cohort_audit": audit, "outputs": result_paths,
              "partition_scope": "global_across_all_configured_projects",
              "global_group_leakage_count": 0,
              "private_split_manifest_sha256": sha256_file(split_path),
              "claim_boundary": "Patient/donor-held-out reproducibility within native cohorts; no independent-cohort, causal, driver or clinical validation.",
              "limitations": ["GTEx and TCGA collection and composition differences remain.",
                              "Held-out bootstrap intervals are conditional on the fixed development selection and gene universe.",
                              "Sensitivity repeats share samples; their quantiles are descriptive, not independent confidence intervals.",
                              "RRA-style scores are ranking heuristics, not valid null p-values for dependent reference lists.",
                              "The lower-quantile maximin score is experimental; no theoretical error control or novelty is asserted.",
                              "Matched native/recount3 processing comparisons and external-cohort evaluation require a separate study."]}
    (root / "report.json").write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
    return report
