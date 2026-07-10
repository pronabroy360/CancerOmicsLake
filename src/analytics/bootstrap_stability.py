from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path
import time

import numpy as np
import polars as pl


BOOTSTRAP_STABILITY_SCHEMA = {
    "cancer_type": pl.Utf8,
    "gene_symbol": pl.Utf8,
    "candidate_priority_rank": pl.Int64,
    "priority_score": pl.Float64,
    "evidence_confidence_tier": pl.Utf8,
    "candidate_selection_reason": pl.Utf8,
    "bootstrap_iterations": pl.Int64,
    "top_k": pl.Int64,
    "tcga_direction_stability": pl.Float64,
    "gtex_direction_stability": pl.Float64,
    "reference_concordance_rate": pl.Float64,
    "opposite_direction_rate": pl.Float64,
    "tcga_top_k_selection_rate": pl.Float64,
    "gtex_top_k_selection_rate": pl.Float64,
    "tcga_median_rank": pl.Float64,
    "tcga_rank_ci_low": pl.Float64,
    "tcga_rank_ci_high": pl.Float64,
    "gtex_median_rank": pl.Float64,
    "gtex_rank_ci_low": pl.Float64,
    "gtex_rank_ci_high": pl.Float64,
    "tcga_median_log2_fc": pl.Float64,
    "tcga_log2_fc_ci_low": pl.Float64,
    "tcga_log2_fc_ci_high": pl.Float64,
    "gtex_median_log2_fc": pl.Float64,
    "gtex_log2_fc_ci_low": pl.Float64,
    "gtex_log2_fc_ci_high": pl.Float64,
    "rank_precision": pl.Float64,
    "bootstrap_stability_score": pl.Float64,
    "bootstrap_stability_tier": pl.Utf8,
    "random_seed": pl.Int64,
    "bootstrap_caveat": pl.Utf8,
}


PROJECT_TISSUES = {
    "TCGA-BRCA": ["Breast - Mammary Tissue", "Breast"],
    "TCGA-LUAD": ["Lung"],
    "TCGA-COAD": ["Colon - Transverse", "Colon - Sigmoid", "Colon"],
}

PROJECT_SEED_OFFSETS = {"TCGA-BRCA": 11, "TCGA-LUAD": 23, "TCGA-COAD": 37}


def _empty_bootstrap_stability() -> pl.DataFrame:
    return pl.DataFrame(schema=BOOTSTRAP_STABILITY_SCHEMA)


def _expression_matrix(df: pl.DataFrame, sample_column: str, ordered_genes: list[str]) -> tuple[list[str], np.ndarray]:
    if df.is_empty():
        return [], np.empty((0, 0), dtype=np.float64)
    pivoted = (
        df.group_by(["gene_symbol", sample_column])
        .agg(pl.col("expression_value").median())
        .pivot(on=sample_column, index="gene_symbol", values="expression_value")
    )
    sample_columns = sorted(column for column in pivoted.columns if column != "gene_symbol")
    ordered = pl.DataFrame({"gene_symbol": ordered_genes}).join(pivoted, on="gene_symbol", how="inner")
    if not sample_columns or ordered.is_empty():
        return [], np.empty((0, 0), dtype=np.float64)
    complete = ordered.filter(~pl.any_horizontal(pl.col(sample_columns).is_null()))
    return complete.get_column("gene_symbol").to_list(), complete.select(sample_columns).to_numpy()


def _directions(values: np.ndarray) -> np.ndarray:
    return np.where(values >= 1.0, 1, np.where(values <= -1.0, -1, 0))


def _ranks(values: np.ndarray) -> np.ndarray:
    order = np.argsort(-np.abs(values), kind="stable")
    ranks = np.empty(values.shape[0], dtype=np.int64)
    ranks[order] = np.arange(1, values.shape[0] + 1)
    return ranks


def _bootstrap_project(
    cancer_type: str,
    candidate: pl.DataFrame,
    tcga: pl.DataFrame,
    gtex: pl.DataFrame,
    iterations: int,
    top_k: int,
    random_seed: int,
) -> pl.DataFrame:
    ordered_genes = candidate.get_column("gene_symbol").to_list()
    tumor = tcga.filter(pl.col("sample_type").str.to_lowercase() == "primary tumor")
    adjacent = tcga.filter(pl.col("sample_type").str.to_lowercase() == "solid tissue normal")
    tumor_genes, tumor_matrix = _expression_matrix(tumor, "sample_id", ordered_genes)
    adjacent_genes, adjacent_matrix = _expression_matrix(adjacent, "sample_id", ordered_genes)
    gtex_genes, gtex_matrix = _expression_matrix(gtex, "gtex_sample_id", ordered_genes)
    common = [gene for gene in ordered_genes if gene in set(tumor_genes) & set(adjacent_genes) & set(gtex_genes)]
    if not common:
        return _empty_bootstrap_stability()

    def reorder(genes: list[str], matrix: np.ndarray) -> np.ndarray:
        positions = {gene: index for index, gene in enumerate(genes)}
        return matrix[[positions[gene] for gene in common], :]

    tumor_matrix = reorder(tumor_genes, tumor_matrix)
    adjacent_matrix = reorder(adjacent_genes, adjacent_matrix)
    gtex_matrix = reorder(gtex_genes, gtex_matrix)
    candidate_lookup = candidate.select(
        [
            "gene_symbol",
            "priority_score",
            "candidate_priority_rank",
            "evidence_confidence_tier",
            "candidate_selection_reason",
        ]
    )

    baseline_tumor = np.median(tumor_matrix, axis=1)
    baseline_adjacent = np.median(adjacent_matrix, axis=1)
    baseline_gtex = np.median(gtex_matrix, axis=1)
    baseline_tcga_fc = np.log2((baseline_tumor + 1.0) / (baseline_adjacent + 1.0))
    baseline_gtex_fc = np.log2((baseline_tumor + 1.0) / (baseline_gtex + 1.0))
    baseline_tcga_direction = _directions(baseline_tcga_fc)
    baseline_gtex_direction = _directions(baseline_gtex_fc)

    gene_count = len(common)
    effective_top_k = min(max(int(top_k), 1), gene_count)
    tcga_fcs = np.empty((iterations, gene_count), dtype=np.float64)
    gtex_fcs = np.empty((iterations, gene_count), dtype=np.float64)
    tcga_ranks = np.empty((iterations, gene_count), dtype=np.int64)
    gtex_ranks = np.empty((iterations, gene_count), dtype=np.int64)
    rng = np.random.default_rng(random_seed)

    for iteration in range(iterations):
        tumor_median = np.median(
            tumor_matrix[:, rng.integers(0, tumor_matrix.shape[1], tumor_matrix.shape[1])],
            axis=1,
        )
        adjacent_median = np.median(
            adjacent_matrix[:, rng.integers(0, adjacent_matrix.shape[1], adjacent_matrix.shape[1])],
            axis=1,
        )
        gtex_median = np.median(
            gtex_matrix[:, rng.integers(0, gtex_matrix.shape[1], gtex_matrix.shape[1])],
            axis=1,
        )
        tcga_fcs[iteration] = np.log2((tumor_median + 1.0) / (adjacent_median + 1.0))
        gtex_fcs[iteration] = np.log2((tumor_median + 1.0) / (gtex_median + 1.0))
        tcga_ranks[iteration] = _ranks(tcga_fcs[iteration])
        gtex_ranks[iteration] = _ranks(gtex_fcs[iteration])

    tcga_directions = _directions(tcga_fcs)
    gtex_directions = _directions(gtex_fcs)
    tcga_rank_low, tcga_rank_median, tcga_rank_high = np.quantile(tcga_ranks, [0.025, 0.5, 0.975], axis=0)
    gtex_rank_low, gtex_rank_median, gtex_rank_high = np.quantile(gtex_ranks, [0.025, 0.5, 0.975], axis=0)
    tcga_fc_low, tcga_fc_median, tcga_fc_high = np.quantile(tcga_fcs, [0.025, 0.5, 0.975], axis=0)
    gtex_fc_low, gtex_fc_median, gtex_fc_high = np.quantile(gtex_fcs, [0.025, 0.5, 0.975], axis=0)
    tcga_direction_stability = np.mean(tcga_directions == baseline_tcga_direction, axis=0)
    gtex_direction_stability = np.mean(gtex_directions == baseline_gtex_direction, axis=0)
    concordance_rate = np.mean(tcga_directions == gtex_directions, axis=0)
    opposite_rate = np.mean(tcga_directions * gtex_directions == -1, axis=0)
    rank_precision = 1.0 - (
        ((tcga_rank_high - tcga_rank_low) + (gtex_rank_high - gtex_rank_low)) / 2.0
    ) / max(gene_count - 1, 1)
    stability_score = (
        0.25 * tcga_direction_stability
        + 0.25 * gtex_direction_stability
        + 0.25 * concordance_rate
        + 0.25 * np.clip(rank_precision, 0.0, 1.0)
    )

    result = pl.DataFrame(
        {
            "cancer_type": [cancer_type] * gene_count,
            "gene_symbol": common,
            "bootstrap_iterations": [iterations] * gene_count,
            "top_k": [effective_top_k] * gene_count,
            "tcga_direction_stability": tcga_direction_stability,
            "gtex_direction_stability": gtex_direction_stability,
            "reference_concordance_rate": concordance_rate,
            "opposite_direction_rate": opposite_rate,
            "tcga_top_k_selection_rate": np.mean(tcga_ranks <= effective_top_k, axis=0),
            "gtex_top_k_selection_rate": np.mean(gtex_ranks <= effective_top_k, axis=0),
            "tcga_median_rank": tcga_rank_median,
            "tcga_rank_ci_low": tcga_rank_low,
            "tcga_rank_ci_high": tcga_rank_high,
            "gtex_median_rank": gtex_rank_median,
            "gtex_rank_ci_low": gtex_rank_low,
            "gtex_rank_ci_high": gtex_rank_high,
            "tcga_median_log2_fc": tcga_fc_median,
            "tcga_log2_fc_ci_low": tcga_fc_low,
            "tcga_log2_fc_ci_high": tcga_fc_high,
            "gtex_median_log2_fc": gtex_fc_median,
            "gtex_log2_fc_ci_low": gtex_fc_low,
            "gtex_log2_fc_ci_high": gtex_fc_high,
            "rank_precision": np.clip(rank_precision, 0.0, 1.0),
            "bootstrap_stability_score": np.clip(stability_score, 0.0, 1.0),
            "random_seed": [random_seed] * gene_count,
        }
    ).join(candidate_lookup, on="gene_symbol", how="left")
    return (
        result.with_columns(
            [
                pl.when(pl.col("bootstrap_stability_score") >= 0.8)
                .then(pl.lit("high"))
                .when(pl.col("bootstrap_stability_score") >= 0.6)
                .then(pl.lit("moderate"))
                .when(pl.col("bootstrap_stability_score") >= 0.4)
                .then(pl.lit("limited"))
                .otherwise(pl.lit("unstable"))
                .alias("bootstrap_stability_tier"),
                pl.lit(
                    "Candidate-restricted nonparametric bootstrap; stability measures sampling robustness, not external biological validity."
                ).alias("bootstrap_caveat"),
            ]
        )
        .select(list(BOOTSTRAP_STABILITY_SCHEMA))
        .with_columns(pl.col(pl.Float64).round(6))
    )


def build_bootstrap_stability(
    silver_dir: str | Path = "data/silver",
    gold_dir: str | Path = "data/gold",
    output_path: str | Path = "data/gold/gold_candidate_bootstrap_stability.parquet",
    report_path: str | Path = "outputs/reports/bootstrap_stability_report.json",
    candidates_per_cancer: int = 500,
    iterations: int = 200,
    top_k: int = 50,
    random_seed: int = 20260710,
) -> dict[str, object]:
    if iterations < 20:
        raise ValueError("iterations must be at least 20")
    if candidates_per_cancer < 1:
        raise ValueError("candidates_per_cancer must be positive")
    started = time.monotonic()
    silver_root = Path(silver_dir)
    gold_root = Path(gold_dir)
    candidate_path = gold_root / "gold_candidate_gene_priority.parquet"
    tcga_path = silver_root / "silver_expression_tcga.parquet"
    gtex_path = silver_root / "silver_expression_gtex.parquet"
    if not candidate_path.exists() or not tcga_path.exists() or not gtex_path.exists():
        result = _empty_bootstrap_stability()
        forced_high_confidence_count = 0
    else:
        candidate_all = pl.read_parquet(candidate_path)
        confidence_path = gold_root / "gold_cancer_gene_evidence_confidence.parquet"
        high_confidence = (
            pl.read_parquet(confidence_path)
            .filter(pl.col("confidence_tier") == "high")
            .select(["cancer_type", "gene_symbol", pl.col("confidence_tier").alias("evidence_confidence_tier")])
            if confidence_path.exists()
            else pl.DataFrame(
                schema={"cancer_type": pl.Utf8, "gene_symbol": pl.Utf8, "evidence_confidence_tier": pl.Utf8}
            )
        )
        forced_high_confidence_count = int(high_confidence.height)
        outputs: list[pl.DataFrame] = []
        for cancer_type, tissues in PROJECT_TISSUES.items():
            project_candidates = (
                candidate_all.filter(pl.col("cancer_type") == cancer_type)
                .sort("priority_score", descending=True)
                .with_row_index("candidate_priority_rank", offset=1)
                .select(["gene_symbol", "priority_score", "candidate_priority_rank"])
                .join(
                    high_confidence.filter(pl.col("cancer_type") == cancer_type).drop("cancer_type"),
                    on="gene_symbol",
                    how="left",
                )
            )
            candidate = (
                project_candidates.filter(
                    (pl.col("candidate_priority_rank") <= candidates_per_cancer)
                    | pl.col("evidence_confidence_tier").is_not_null()
                )
                .with_columns(
                    pl.when(
                        (pl.col("candidate_priority_rank") <= candidates_per_cancer)
                        & pl.col("evidence_confidence_tier").is_not_null()
                    )
                    .then(pl.lit("top_priority_and_high_confidence"))
                    .when(pl.col("evidence_confidence_tier").is_not_null())
                    .then(pl.lit("high_confidence"))
                    .otherwise(pl.lit("top_priority"))
                    .alias("candidate_selection_reason"),
                    pl.col("evidence_confidence_tier").fill_null("not_high"),
                )
            )
            genes = candidate.get_column("gene_symbol").drop_nulls().unique().to_list()
            if not genes:
                continue
            tcga = (
                pl.scan_parquet(tcga_path)
                .filter(
                    (pl.col("project_id") == cancer_type)
                    & pl.col("gene_symbol").is_in(genes)
                    & pl.col("sample_type").is_in(["Primary Tumor", "Solid Tissue Normal"])
                    & (pl.col("expression_unit").str.to_uppercase() == "TPM")
                )
                .select(["sample_id", "sample_type", "gene_symbol", "expression_value"])
                .collect()
            )
            gtex = (
                pl.scan_parquet(gtex_path)
                .filter(pl.col("tissue_site").is_in(tissues) & pl.col("gene_symbol").is_in(genes))
                .select(["gtex_sample_id", "gene_symbol", "expression_value"])
                .collect()
            )
            outputs.append(
                _bootstrap_project(
                    cancer_type=cancer_type,
                    candidate=candidate,
                    tcga=tcga,
                    gtex=gtex,
                    iterations=iterations,
                    top_k=top_k,
                    random_seed=random_seed + PROJECT_SEED_OFFSETS[cancer_type],
                )
            )
        non_empty = [frame for frame in outputs if not frame.is_empty()]
        result = pl.concat(non_empty, how="vertical") if non_empty else _empty_bootstrap_stability()
        if not result.is_empty():
            result = result.sort(
                ["bootstrap_stability_score", "priority_score"],
                descending=[True, True],
            )

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    temporary = out.with_suffix(".tmp.parquet")
    result.write_parquet(temporary)
    temporary.replace(out)
    tier_counts = (
        {str(row[0]): int(row[1]) for row in result.group_by("bootstrap_stability_tier").len().rows()}
        if not result.is_empty()
        else {}
    )
    report = {
        "generated_at": datetime.now(UTC).isoformat(),
        "status": "completed" if not result.is_empty() else "empty",
        "output_path": str(out),
        "row_count": result.height,
        "candidates_per_cancer": candidates_per_cancer,
        "iterations": iterations,
        "top_k": top_k,
        "random_seed": random_seed,
        "tier_counts": tier_counts,
        "forced_high_confidence_count": forced_high_confidence_count,
        "elapsed_seconds": round(time.monotonic() - started, 3),
    }
    report_out = Path(report_path)
    report_out.parent.mkdir(parents=True, exist_ok=True)
    report_out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def bootstrap_stability(
    cancer_type: str | None = None,
    gene_query: str | None = None,
    stability_tier: str | None = None,
    min_stability: float | None = None,
    limit: int = 50,
    gold_path: str | Path = "data/gold/gold_candidate_bootstrap_stability.parquet",
) -> dict[str, object]:
    path = Path(gold_path)
    df = pl.read_parquet(path) if path.exists() else _empty_bootstrap_stability()
    if df.is_empty() or not set(BOOTSTRAP_STABILITY_SCHEMA).issubset(df.columns):
        filtered = _empty_bootstrap_stability()
    else:
        filtered = df
        if cancer_type:
            filtered = filtered.filter(pl.col("cancer_type") == cancer_type)
        if gene_query:
            filtered = filtered.filter(
                pl.col("gene_symbol").str.to_uppercase().str.contains(gene_query.upper(), literal=True)
            )
        if stability_tier:
            filtered = filtered.filter(pl.col("bootstrap_stability_tier") == stability_tier.lower())
        if min_stability is not None:
            filtered = filtered.filter(pl.col("bootstrap_stability_score") >= float(min_stability))
        filtered = filtered.sort(
            ["bootstrap_stability_score", "priority_score"],
            descending=[True, True],
        )
    capped = filtered.head(max(int(limit), 0))
    return {
        "filters": {
            "cancer_type": cancer_type,
            "gene_query": gene_query,
            "stability_tier": stability_tier,
            "min_stability": min_stability,
            "limit": limit,
        },
        "rows": capped.to_dicts(),
        "row_count": capped.height,
        "total_matching_rows": filtered.height,
        "warning": "Candidate-restricted bootstrap stability is exploratory and is not external validation.",
    }
