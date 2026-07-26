from __future__ import annotations

from datetime import UTC, datetime
import hashlib
import json
import math
from pathlib import Path
import subprocess
import time
from typing import Any, Sequence

import numpy as np
import polars as pl
from scipy.stats import spearmanr

from src.analytics.consensus_candidates import CONSENSUS_COMPONENT_WEIGHTS


REFERENCE_COMPARISON_SCHEMA = {
    "cancer_type": pl.Utf8,
    "method_a": pl.Utf8,
    "method_b": pl.Utf8,
    "common_gene_count": pl.Int64,
    "top_k": pl.Int64,
    "top_k_a_count": pl.Int64,
    "top_k_b_count": pl.Int64,
    "top_k_overlap_count": pl.Int64,
    "top_k_jaccard": pl.Float64,
    "top_k_direction_concordance": pl.Float64,
    "universe_direction_concordance": pl.Float64,
    "regulated_union_gene_count": pl.Int64,
    "regulated_direction_concordance": pl.Float64,
    "spearman_abs_effect": pl.Float64,
    "median_abs_effect_delta": pl.Float64,
    "agreement_tier": pl.Utf8,
    "evaluation_caveat": pl.Utf8,
}

CONSENSUS_ABLATION_SCHEMA = {
    "cancer_type": pl.Utf8,
    "ablation_scenario": pl.Utf8,
    "omitted_components": pl.Utf8,
    "retained_weight": pl.Float64,
    "common_gene_count": pl.Int64,
    "top_k": pl.Int64,
    "top_k_overlap_count": pl.Int64,
    "top_k_jaccard": pl.Float64,
    "spearman_consensus_score": pl.Float64,
    "median_baseline_top_k_rank_shift": pl.Float64,
    "median_absolute_score_delta": pl.Float64,
    "max_absolute_score_delta": pl.Float64,
    "baseline_prioritized_count": pl.Int64,
    "fixed_threshold_retained_count": pl.Int64,
    "fixed_threshold_retention_rate": pl.Float64,
    "sensitivity_tier": pl.Utf8,
    "evaluation_caveat": pl.Utf8,
}

REFERENCE_METHODS = {
    "gtex_native": "log2_fc_tumor_vs_gtex",
    "tcga_adjacent": "log2_fc_tumor_vs_tcga_normal",
    "recount3_uniform": "recount3_log2_fold_change",
}
DEFAULT_TOP_K_VALUES = (25, 50, 100, 250)

ABLATION_SCENARIOS = {
    "without_reference_triangulation": ("reference_component",),
    "without_external_validation": ("external_component",),
    "without_paired_support": ("paired_component",),
    "without_explicit_reference_components": (
        "reference_component",
        "external_component",
        "paired_component",
    ),
}

REFERENCE_CAVEAT = (
    "Agreement compares effect rankings on a shared cancer-specific gene universe; it does not "
    "separate technical batch effects from biological tissue and cohort differences."
)
ABLATION_CAVEAT = (
    "Ablation removes explicit consensus score components and renormalizes retained weights; "
    "other components can retain upstream dependence on the same expression sources. Fixed-threshold "
    "retention uses the full-model cutoff descriptively and does not determine the sensitivity tier."
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _git_commit() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else "unknown"


def _empty_reference_comparison() -> pl.DataFrame:
    return pl.DataFrame(schema=REFERENCE_COMPARISON_SCHEMA)


def _empty_consensus_ablation() -> pl.DataFrame:
    return pl.DataFrame(schema=CONSENSUS_ABLATION_SCHEMA)


def _safe_spearman(left: np.ndarray, right: np.ndarray) -> float:
    if left.size < 2 or np.allclose(left, left[0]) or np.allclose(right, right[0]):
        return 0.0
    value = float(spearmanr(left, right).statistic)
    return value if math.isfinite(value) else 0.0


def _direction(value: float) -> str:
    if value >= 1.0:
        return "up"
    if value <= -1.0:
        return "down"
    return "stable"


def _ranked_genes(gene_values: dict[str, float]) -> list[str]:
    return sorted(gene_values, key=lambda gene: (-abs(gene_values[gene]), gene))


def _score_ranked_genes(gene_values: dict[str, float]) -> list[str]:
    return sorted(gene_values, key=lambda gene: (-gene_values[gene], gene))


def _agreement_tier(jaccard: float, direction: float, correlation: float) -> str:
    if jaccard >= 0.50 and direction >= 0.80 and correlation >= 0.50:
        return "high"
    if jaccard >= 0.25 and direction >= 0.65 and correlation >= 0.25:
        return "moderate"
    return "limited"


def _sensitivity_tier(jaccard: float, correlation: float) -> str:
    if jaccard >= 0.80 and correlation >= 0.90:
        return "robust"
    if jaccard >= 0.60 and correlation >= 0.75:
        return "moderate"
    return "sensitive"


def _validate_columns(
    frame: pl.DataFrame,
    required: set[str],
    resource_name: str,
) -> None:
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"{resource_name} missing required columns: {missing}")


def _build_common_reference_universe(
    reference: pl.DataFrame,
    external: pl.DataFrame,
) -> pl.DataFrame:
    _validate_columns(
        reference,
        {
            "cancer_type",
            "gene_symbol",
            "log2_fc_tumor_vs_gtex",
            "log2_fc_tumor_vs_tcga_normal",
        },
        "gold_reference_triangulation",
    )
    _validate_columns(
        external,
        {"cancer_type", "gene_symbol", "recount3_log2_fold_change"},
        "gold_external_expression_validation",
    )
    return (
        reference.select(
            [
                pl.col("cancer_type").cast(pl.Utf8),
                pl.col("gene_symbol").cast(pl.Utf8).str.to_uppercase(),
                pl.col("log2_fc_tumor_vs_gtex").cast(pl.Float64, strict=False),
                pl.col("log2_fc_tumor_vs_tcga_normal").cast(pl.Float64, strict=False),
            ]
        )
        .join(
            external.select(
                [
                    pl.col("cancer_type").cast(pl.Utf8),
                    pl.col("gene_symbol").cast(pl.Utf8).str.to_uppercase(),
                    pl.col("recount3_log2_fold_change").cast(pl.Float64, strict=False),
                ]
            ),
            on=["cancer_type", "gene_symbol"],
            how="inner",
        )
        .drop_nulls()
        .unique(["cancer_type", "gene_symbol"], keep="first")
        .sort(["cancer_type", "gene_symbol"])
    )


def build_reference_method_comparison(
    reference: pl.DataFrame,
    external: pl.DataFrame,
    top_k: int,
) -> pl.DataFrame:
    universe = _build_common_reference_universe(reference, external)
    if universe.is_empty():
        return _empty_reference_comparison()

    rows: list[dict[str, Any]] = []
    method_names = list(REFERENCE_METHODS)
    for cancer_type in sorted(universe.get_column("cancer_type").unique().to_list()):
        cancer = universe.filter(pl.col("cancer_type") == cancer_type)
        genes = cancer.get_column("gene_symbol").to_list()
        effects = {
            method: dict(zip(genes, cancer.get_column(column).to_list(), strict=True))
            for method, column in REFERENCE_METHODS.items()
        }
        effective_top_k = min(top_k, len(genes))
        top_sets = {
            method: set(_ranked_genes(values)[:effective_top_k])
            for method, values in effects.items()
        }
        for index, method_a in enumerate(method_names):
            for method_b in method_names[index + 1 :]:
                values_a = effects[method_a]
                values_b = effects[method_b]
                top_a = top_sets[method_a]
                top_b = top_sets[method_b]
                overlap = top_a & top_b
                union = top_a | top_b
                overlap_direction = (
                    sum(
                        _direction(float(values_a[gene]))
                        == _direction(float(values_b[gene]))
                        for gene in overlap
                    )
                    / len(overlap)
                    if overlap
                    else 0.0
                )
                universe_direction = sum(
                    _direction(float(values_a[gene]))
                    == _direction(float(values_b[gene]))
                    for gene in genes
                ) / len(genes)
                regulated_genes = [
                    gene
                    for gene in genes
                    if _direction(float(values_a[gene])) != "stable"
                    or _direction(float(values_b[gene])) != "stable"
                ]
                regulated_direction = (
                    sum(
                        _direction(float(values_a[gene]))
                        == _direction(float(values_b[gene]))
                        for gene in regulated_genes
                    )
                    / len(regulated_genes)
                    if regulated_genes
                    else 1.0
                )
                array_a = np.asarray([abs(float(values_a[gene])) for gene in genes])
                array_b = np.asarray([abs(float(values_b[gene])) for gene in genes])
                correlation = _safe_spearman(array_a, array_b)
                jaccard = len(overlap) / len(union) if union else 1.0
                rows.append(
                    {
                        "cancer_type": str(cancer_type),
                        "method_a": method_a,
                        "method_b": method_b,
                        "common_gene_count": len(genes),
                        "top_k": effective_top_k,
                        "top_k_a_count": len(top_a),
                        "top_k_b_count": len(top_b),
                        "top_k_overlap_count": len(overlap),
                        "top_k_jaccard": round(jaccard, 6),
                        "top_k_direction_concordance": round(overlap_direction, 6),
                        "universe_direction_concordance": round(universe_direction, 6),
                        "regulated_union_gene_count": len(regulated_genes),
                        "regulated_direction_concordance": round(
                            regulated_direction, 6
                        ),
                        "spearman_abs_effect": round(correlation, 6),
                        "median_abs_effect_delta": round(
                            float(np.median(np.abs(array_a - array_b))), 6
                        ),
                        "agreement_tier": _agreement_tier(
                            jaccard, regulated_direction, correlation
                        ),
                        "evaluation_caveat": REFERENCE_CAVEAT,
                    }
                )
    return pl.DataFrame(rows, schema=REFERENCE_COMPARISON_SCHEMA).sort(
        ["cancer_type", "method_a", "method_b"]
    )


def _validate_consensus(consensus: pl.DataFrame) -> None:
    required = {
        "cancer_type",
        "gene_symbol",
        "consensus_score",
        "consensus_decision",
        *CONSENSUS_COMPONENT_WEIGHTS,
    }
    _validate_columns(consensus, required, "gold_consensus_candidate_genes")


def build_consensus_component_ablation(
    consensus: pl.DataFrame,
    top_k: int,
) -> pl.DataFrame:
    _validate_consensus(consensus)
    if consensus.is_empty():
        return _empty_consensus_ablation()

    rows: list[dict[str, Any]] = []
    for cancer_type in sorted(consensus.get_column("cancer_type").unique().to_list()):
        cancer = consensus.filter(pl.col("cancer_type") == cancer_type).sort("gene_symbol")
        genes = cancer.get_column("gene_symbol").cast(pl.Utf8).to_list()
        baseline = dict(
            zip(
                genes,
                cancer.get_column("consensus_score").cast(pl.Float64).to_list(),
                strict=True,
            )
        )
        baseline_order = _score_ranked_genes(baseline)
        effective_top_k = min(top_k, len(genes))
        baseline_top = set(baseline_order[:effective_top_k])
        baseline_ranks = {gene: rank for rank, gene in enumerate(baseline_order, start=1)}
        prioritized = set(
            cancer.filter(pl.col("consensus_decision") == "prioritized")
            .get_column("gene_symbol")
            .cast(pl.Utf8)
            .to_list()
        )

        component_values = {
            component: dict(
                zip(
                    genes,
                    cancer.get_column(component).cast(pl.Float64).fill_null(0.0).to_list(),
                    strict=True,
                )
            )
            for component in CONSENSUS_COMPONENT_WEIGHTS
        }
        for scenario, omitted in ABLATION_SCENARIOS.items():
            retained = {
                component: weight
                for component, weight in CONSENSUS_COMPONENT_WEIGHTS.items()
                if component not in omitted
            }
            retained_weight = sum(retained.values())
            ablated = {
                gene: sum(
                    component_values[component][gene] * weight
                    for component, weight in retained.items()
                )
                / retained_weight
                for gene in genes
            }
            ablated_order = _score_ranked_genes(ablated)
            ablated_top = set(ablated_order[:effective_top_k])
            ablated_ranks = {gene: rank for rank, gene in enumerate(ablated_order, start=1)}
            overlap = baseline_top & ablated_top
            union = baseline_top | ablated_top
            jaccard = len(overlap) / len(union) if union else 1.0
            correlation = _safe_spearman(
                np.asarray([baseline[gene] for gene in genes]),
                np.asarray([ablated[gene] for gene in genes]),
            )
            rank_shifts = [
                abs(baseline_ranks[gene] - ablated_ranks[gene]) for gene in baseline_top
            ]
            score_deltas = np.asarray(
                [abs(baseline[gene] - ablated[gene]) for gene in genes]
            )
            retained_prioritized = sum(
                ablated[gene] >= 0.75 for gene in prioritized
            )
            retention_rate = (
                retained_prioritized / len(prioritized) if prioritized else None
            )
            rows.append(
                {
                    "cancer_type": str(cancer_type),
                    "ablation_scenario": scenario,
                    "omitted_components": ",".join(omitted),
                    "retained_weight": round(retained_weight, 6),
                    "common_gene_count": len(genes),
                    "top_k": effective_top_k,
                    "top_k_overlap_count": len(overlap),
                    "top_k_jaccard": round(jaccard, 6),
                    "spearman_consensus_score": round(correlation, 6),
                    "median_baseline_top_k_rank_shift": round(
                        float(np.median(rank_shifts)), 6
                    ),
                    "median_absolute_score_delta": round(
                        float(np.median(score_deltas)), 6
                    ),
                    "max_absolute_score_delta": round(float(np.max(score_deltas)), 6),
                    "baseline_prioritized_count": len(prioritized),
                    "fixed_threshold_retained_count": retained_prioritized,
                    "fixed_threshold_retention_rate": (
                        round(retention_rate, 6)
                        if retention_rate is not None
                        else None
                    ),
                    "sensitivity_tier": _sensitivity_tier(jaccard, correlation),
                    "evaluation_caveat": ABLATION_CAVEAT,
                }
            )
    return pl.DataFrame(rows, schema=CONSENSUS_ABLATION_SCHEMA).sort(
        ["cancer_type", "ablation_scenario"]
    )


def _validate_evaluation_metrics(
    comparison: pl.DataFrame,
    ablation: pl.DataFrame,
) -> None:
    comparison_unit_metrics = [
        "top_k_jaccard",
        "top_k_direction_concordance",
        "universe_direction_concordance",
        "regulated_direction_concordance",
    ]
    ablation_unit_metrics = [
        "top_k_jaccard",
        "fixed_threshold_retention_rate",
    ]
    invalid_comparison = comparison.filter(
        pl.any_horizontal(
            [
                ~pl.col(column).is_between(0.0, 1.0)
                for column in comparison_unit_metrics
            ]
            + [
                ~pl.col("spearman_abs_effect").is_between(-1.0, 1.0),
                pl.col("median_abs_effect_delta") < 0.0,
                pl.col("top_k_overlap_count") > pl.col("top_k"),
            ]
        )
    )
    invalid_ablation = ablation.filter(
        pl.any_horizontal(
            [
                ~pl.col(column).is_between(0.0, 1.0)
                for column in ablation_unit_metrics
            ]
            + [
                ~pl.col("spearman_consensus_score").is_between(-1.0, 1.0),
                ~pl.col("retained_weight").is_between(0.0, 1.0, closed="right"),
                pl.col("median_baseline_top_k_rank_shift") < 0.0,
                pl.col("median_absolute_score_delta") < 0.0,
                pl.col("max_absolute_score_delta") < 0.0,
                pl.col("top_k_overlap_count") > pl.col("top_k"),
            ]
        )
    )
    if invalid_comparison.height or invalid_ablation.height:
        raise RuntimeError(
            "Reference-ablation evaluation produced out-of-contract metrics: "
            f"comparison={invalid_comparison.height}, ablation={invalid_ablation.height}"
        )


def build_reference_ablation_evaluation(
    gold_dir: str | Path = "data/gold",
    comparison_output_path: str | Path = "data/gold/gold_reference_method_comparison.parquet",
    ablation_output_path: str | Path = "data/gold/gold_consensus_ablation_stability.parquet",
    report_path: str | Path = "outputs/reports/reference_ablation_report.json",
    top_k: int | None = None,
    top_k_values: Sequence[int] | None = None,
) -> dict[str, Any]:
    if top_k is not None and top_k_values is not None:
        raise ValueError("Provide either top_k or top_k_values, not both")
    resolved_top_k = sorted(
        set(
            top_k_values
            or ([top_k] if top_k is not None else DEFAULT_TOP_K_VALUES)
        )
    )
    if not resolved_top_k or any(value < 1 for value in resolved_top_k):
        raise ValueError("top_k values must be positive")
    started = time.monotonic()
    gold = Path(gold_dir)
    required_paths = {
        "reference": gold / "gold_reference_triangulation.parquet",
        "external": gold / "gold_external_expression_validation.parquet",
        "consensus": gold / "gold_consensus_candidate_genes.parquet",
    }
    comparison_output = Path(comparison_output_path)
    ablation_output = Path(ablation_output_path)
    report = Path(report_path)
    for path in (comparison_output, ablation_output, report):
        path.parent.mkdir(parents=True, exist_ok=True)

    missing_inputs = [
        name for name, path in required_paths.items() if not path.exists()
    ]
    if missing_inputs:
        comparison = _empty_reference_comparison()
        ablation = _empty_consensus_ablation()
        status = "skipped_missing_inputs"
    else:
        reference = pl.read_parquet(required_paths["reference"])
        external = pl.read_parquet(required_paths["external"])
        consensus = pl.read_parquet(required_paths["consensus"])
        comparison = pl.concat(
            [
                build_reference_method_comparison(reference, external, value)
                for value in resolved_top_k
            ],
            how="vertical",
        ).sort(["cancer_type", "top_k", "method_a", "method_b"])
        ablation = pl.concat(
            [
                build_consensus_component_ablation(consensus, value)
                for value in resolved_top_k
            ],
            how="vertical",
        ).sort(["cancer_type", "top_k", "ablation_scenario"])
        status = (
            "completed"
            if not comparison.is_empty() and not ablation.is_empty()
            else "skipped_no_overlap"
        )
        if status == "completed":
            _validate_evaluation_metrics(comparison, ablation)

    comparison.write_parquet(comparison_output)
    ablation.write_parquet(ablation_output)
    summary = {
        "status": status,
        "generated_at": datetime.now(UTC).isoformat(),
        "git_commit": _git_commit(),
        "top_k_values": resolved_top_k,
        "missing_inputs": missing_inputs,
        "input_resources": [
            {
                "name": name,
                "path": str(path),
                "bytes": path.stat().st_size,
                "row_count": pl.scan_parquet(path).select(pl.len()).collect().item(),
                "sha256": _sha256(path),
            }
            for name, path in required_paths.items()
            if path.exists()
        ],
        "evaluation_parameters": {
            "direction_threshold_absolute_log2_fc": 1.0,
            "reference_methods": REFERENCE_METHODS,
            "consensus_component_weights": CONSENSUS_COMPONENT_WEIGHTS,
            "ablation_scenarios": ABLATION_SCENARIOS,
            "agreement_tier_thresholds": {
                "high": {
                    "top_k_jaccard": 0.50,
                    "regulated_direction_concordance": 0.80,
                    "spearman_abs_effect": 0.50,
                },
                "moderate": {
                    "top_k_jaccard": 0.25,
                    "regulated_direction_concordance": 0.65,
                    "spearman_abs_effect": 0.25,
                },
            },
            "sensitivity_tier_thresholds": {
                "robust": {
                    "top_k_jaccard": 0.80,
                    "spearman_consensus_score": 0.90,
                },
                "moderate": {
                    "top_k_jaccard": 0.60,
                    "spearman_consensus_score": 0.75,
                },
            },
        },
        "reference_comparison_path": str(comparison_output),
        "consensus_ablation_path": str(ablation_output),
        "reference_comparison_rows": comparison.height,
        "consensus_ablation_rows": ablation.height,
        "agreement_tier_counts": (
            comparison.group_by("agreement_tier")
            .len()
            .sort("agreement_tier")
            .to_dicts()
            if not comparison.is_empty()
            else []
        ),
        "sensitivity_tier_counts": (
            ablation.group_by("sensitivity_tier")
            .len()
            .sort("sensitivity_tier")
            .to_dicts()
            if not ablation.is_empty()
            else []
        ),
        "reference_comparisons": comparison.to_dicts(),
        "consensus_ablations": ablation.to_dicts(),
        "interpretation": (
            "Quantifies reference and explicit score-component sensitivity for reproducibility "
            "evaluation; it is not biological, causal, or clinical validation."
        ),
        "elapsed_seconds": round(time.monotonic() - started, 3),
    }
    report.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary
