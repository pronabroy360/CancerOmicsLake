from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path
import time

import numpy as np
import polars as pl
from scipy.stats import mannwhitneyu


EXPRESSION_STATISTICS_SCHEMA = {
    "cancer_type": pl.Utf8,
    "gene_symbol": pl.Utf8,
    "native_sample_count_tumor": pl.Int64,
    "native_sample_count_normal": pl.Int64,
    "native_median_tumor": pl.Float64,
    "native_median_normal": pl.Float64,
    "native_log2_fold_change": pl.Float64,
    "native_mann_whitney_u": pl.Float64,
    "native_p_value": pl.Float64,
    "native_fdr_q_value": pl.Float64,
    "native_rank_biserial": pl.Float64,
    "recount3_sample_count_tumor": pl.Int64,
    "recount3_sample_count_normal": pl.Int64,
    "recount3_median_tumor": pl.Float64,
    "recount3_median_normal": pl.Float64,
    "recount3_log2_fold_change": pl.Float64,
    "recount3_mann_whitney_u": pl.Float64,
    "recount3_p_value": pl.Float64,
    "recount3_fdr_q_value": pl.Float64,
    "recount3_rank_biserial": pl.Float64,
    "effect_direction_agreement": pl.Utf8,
    "statistical_support_score": pl.Float64,
    "statistical_support_tier": pl.Utf8,
    "statistical_caveat": pl.Utf8,
}

PROJECT_TISSUES = {
    "TCGA-BRCA": ["Breast - Mammary Tissue", "Breast"],
    "TCGA-LUAD": ["Lung"],
    "TCGA-COAD": ["Colon - Transverse", "Colon - Sigmoid", "Colon"],
}

MIN_GROUP_SIZE = 5
FDR_THRESHOLD = 0.05
EFFECT_THRESHOLD = 0.30


def _empty_expression_statistics() -> pl.DataFrame:
    return pl.DataFrame(schema=EXPRESSION_STATISTICS_SCHEMA)


def _benjamini_hochberg(p_values: np.ndarray) -> np.ndarray:
    if p_values.size == 0:
        return np.array([], dtype=float)
    cleaned = np.clip(np.nan_to_num(p_values, nan=1.0, posinf=1.0, neginf=1.0), 0.0, 1.0)
    order = np.argsort(cleaned, kind="stable")
    ranked = cleaned[order]
    adjusted = ranked * ranked.size / np.arange(1, ranked.size + 1)
    adjusted = np.minimum.accumulate(adjusted[::-1])[::-1]
    result = np.empty_like(adjusted)
    result[order] = np.clip(adjusted, 0.0, 1.0)
    return result


def _group_values(frame: pl.DataFrame, value_column: str) -> pl.DataFrame:
    return (
        frame.select(["gene_symbol", value_column])
        .drop_nulls()
        .group_by("gene_symbol")
        .agg(pl.col(value_column).alias("values"))
    )


def _test_contrast(
    tumor: pl.DataFrame,
    normal: pl.DataFrame,
    project_id: str,
    prefix: str,
) -> pl.DataFrame:
    joined = _group_values(tumor, "expression_value").rename({"values": "tumor_values"}).join(
        _group_values(normal, "expression_value").rename({"values": "normal_values"}),
        on="gene_symbol",
        how="inner",
    )
    rows: list[dict[str, object]] = []
    for gene_symbol, tumor_values, normal_values in joined.iter_rows():
        tumor_array = np.asarray(tumor_values, dtype=float)
        normal_array = np.asarray(normal_values, dtype=float)
        if tumor_array.size < MIN_GROUP_SIZE or normal_array.size < MIN_GROUP_SIZE:
            continue
        test = mannwhitneyu(tumor_array, normal_array, alternative="two-sided", method="asymptotic")
        denominator = float(tumor_array.size * normal_array.size)
        median_tumor = float(np.median(tumor_array))
        median_normal = float(np.median(normal_array))
        rows.append(
            {
                "cancer_type": project_id,
                "gene_symbol": str(gene_symbol).upper(),
                f"{prefix}_sample_count_tumor": int(tumor_array.size),
                f"{prefix}_sample_count_normal": int(normal_array.size),
                f"{prefix}_median_tumor": median_tumor,
                f"{prefix}_median_normal": median_normal,
                f"{prefix}_log2_fold_change": float(np.log2(median_tumor + 1.0) - np.log2(median_normal + 1.0)),
                f"{prefix}_mann_whitney_u": float(test.statistic),
                f"{prefix}_p_value": max(float(test.pvalue), 1e-300),
                f"{prefix}_rank_biserial": float((2.0 * test.statistic / denominator) - 1.0),
            }
        )
    if not rows:
        return pl.DataFrame()
    result = pl.DataFrame(rows)
    q_values = _benjamini_hochberg(result.get_column(f"{prefix}_p_value").to_numpy())
    return result.with_columns(pl.Series(f"{prefix}_fdr_q_value", q_values))


def _native_statistics(tcga_path: Path, gtex_path: Path) -> pl.DataFrame:
    if not tcga_path.exists() or not gtex_path.exists():
        return pl.DataFrame()
    tcga = pl.read_parquet(tcga_path, columns=["project_id", "sample_type", "gene_symbol", "expression_value"])
    gtex = pl.read_parquet(gtex_path, columns=["tissue_site", "gene_symbol", "expression_value"])
    results: list[pl.DataFrame] = []
    for project_id, tissues in PROJECT_TISSUES.items():
        tumor = tcga.filter(
            (pl.col("project_id") == project_id)
            & (pl.col("sample_type").str.to_lowercase() == "primary tumor")
        )
        normal = gtex.filter(pl.col("tissue_site").is_in(tissues))
        tested = _test_contrast(tumor, normal, project_id, "native")
        if not tested.is_empty():
            results.append(tested)
    return pl.concat(results, how="diagonal_relaxed") if results else pl.DataFrame()


def _recount3_statistics(path: Path) -> pl.DataFrame:
    if not path.exists():
        return pl.DataFrame()
    recount3 = pl.read_parquet(
        path,
        columns=["source", "project_id", "sample_type", "tissue_site", "gene_symbol", "expression_value"],
    )
    results: list[pl.DataFrame] = []
    for project_id, tissues in PROJECT_TISSUES.items():
        tumor = recount3.filter(
            (pl.col("source").str.to_uppercase() == "TCGA")
            & (pl.col("project_id") == project_id)
            & (pl.col("sample_type").str.to_lowercase() == "primary tumor")
        )
        normal = recount3.filter(
            (pl.col("source").str.to_uppercase() == "GTEX") & pl.col("tissue_site").is_in(tissues)
        )
        tested = _test_contrast(tumor, normal, project_id, "recount3")
        if not tested.is_empty():
            results.append(tested)
    return pl.concat(results, how="diagonal_relaxed") if results else pl.DataFrame()


def _support_score(prefix: str) -> pl.Expr:
    q_score = (-pl.col(f"{prefix}_fdr_q_value").clip(1e-300, 1.0).log10() / 10.0).clip(0.0, 1.0)
    effect_score = (pl.col(f"{prefix}_rank_biserial").abs() / 0.5).clip(0.0, 1.0)
    return q_score * 0.60 + effect_score * 0.40


def _score_support(native: pl.DataFrame, recount3: pl.DataFrame) -> pl.DataFrame:
    if native.is_empty() or recount3.is_empty():
        return _empty_expression_statistics()
    joined = native.join(recount3, on=["cancer_type", "gene_symbol"], how="inner")
    if joined.is_empty():
        return _empty_expression_statistics()
    return (
        joined.with_columns(
            [
                pl.when(
                    (pl.col("native_rank_biserial") > 0) == (pl.col("recount3_rank_biserial") > 0)
                )
                .then(pl.lit("concordant"))
                .otherwise(pl.lit("discordant"))
                .alias("effect_direction_agreement"),
                _support_score("native").alias("native_support_score"),
                _support_score("recount3").alias("recount3_support_score"),
            ]
        )
        .with_columns(
            pl.when(pl.col("effect_direction_agreement") == "concordant")
            .then((pl.col("native_support_score") + pl.col("recount3_support_score")) / 2.0)
            .otherwise(0.0)
            .clip(0.0, 1.0)
            .alias("statistical_support_score")
        )
        .with_columns(
            [
                pl.when(
                    (pl.col("effect_direction_agreement") == "discordant")
                    & (pl.col("native_fdr_q_value") <= FDR_THRESHOLD)
                    & (pl.col("recount3_fdr_q_value") <= FDR_THRESHOLD)
                    & (pl.col("native_rank_biserial").abs() >= EFFECT_THRESHOLD)
                    & (pl.col("recount3_rank_biserial").abs() >= EFFECT_THRESHOLD)
                )
                .then(pl.lit("discordant"))
                .when(
                    (pl.col("effect_direction_agreement") == "concordant")
                    & (pl.col("native_fdr_q_value") <= FDR_THRESHOLD)
                    & (pl.col("recount3_fdr_q_value") <= FDR_THRESHOLD)
                    & (pl.col("native_rank_biserial").abs() >= EFFECT_THRESHOLD)
                    & (pl.col("recount3_rank_biserial").abs() >= EFFECT_THRESHOLD)
                )
                .then(pl.lit("replicated_fdr"))
                .when(
                    (pl.col("effect_direction_agreement") == "concordant")
                    & (pl.col("recount3_fdr_q_value") <= FDR_THRESHOLD)
                    & (pl.col("recount3_rank_biserial").abs() >= EFFECT_THRESHOLD)
                )
                .then(pl.lit("recount3_fdr_supported"))
                .when(
                    (pl.col("native_fdr_q_value") <= FDR_THRESHOLD)
                    & (pl.col("native_rank_biserial").abs() >= EFFECT_THRESHOLD)
                )
                .then(pl.lit("native_only_fdr"))
                .otherwise(pl.lit("limited"))
                .alias("statistical_support_tier"),
                pl.lit(
                    "Mann-Whitney association tests with cancer-wise Benjamini-Hochberg FDR; source and disease status remain confounded, so results are not causal, clinical, or batch-corrected differential-expression claims."
                ).alias("statistical_caveat"),
            ]
        )
        .select(list(EXPRESSION_STATISTICS_SCHEMA))
        .sort(["statistical_support_score", "recount3_fdr_q_value"], descending=[True, False])
    )


def build_expression_statistical_support(
    tcga_path: str | Path = "data/silver/silver_expression_tcga.parquet",
    gtex_path: str | Path = "data/silver/silver_expression_gtex.parquet",
    recount3_path: str | Path = "data/silver/silver_expression_recount3.parquet",
    output_path: str | Path = "data/gold/gold_expression_statistical_support.parquet",
    report_path: str | Path = "outputs/reports/expression_statistical_support_report.json",
) -> dict[str, object]:
    started = time.monotonic()
    output = Path(output_path)
    report = Path(report_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    report.parent.mkdir(parents=True, exist_ok=True)
    native = _native_statistics(Path(tcga_path), Path(gtex_path))
    recount3 = _recount3_statistics(Path(recount3_path))
    result = _score_support(native, recount3)
    status = "completed" if not result.is_empty() else "skipped_missing_or_nonoverlapping_inputs"
    result.write_parquet(output)
    tier_counts = (
        result.group_by("statistical_support_tier").len().sort("statistical_support_tier").to_dicts()
        if not result.is_empty()
        else []
    )
    summary = {
        "status": status,
        "generated_at": datetime.now(UTC).isoformat(),
        "row_count": int(result.height),
        "fdr_method": "Benjamini-Hochberg within source and cancer type",
        "fdr_threshold": FDR_THRESHOLD,
        "effect_threshold": EFFECT_THRESHOLD,
        "minimum_group_size": MIN_GROUP_SIZE,
        "tier_counts": tier_counts,
        "path": str(output),
        "elapsed_seconds": round(time.monotonic() - started, 3),
    }
    report.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def expression_statistical_support(
    cancer_type: str | None = None,
    gene_query: str | None = None,
    support_tier: str | None = None,
    max_fdr: float | None = None,
    min_support_score: float | None = None,
    limit: int = 50,
    gold_path: str | Path = "data/gold/gold_expression_statistical_support.parquet",
) -> dict[str, object]:
    path = Path(gold_path)
    df = pl.read_parquet(path) if path.exists() else _empty_expression_statistics()
    filtered = df if set(EXPRESSION_STATISTICS_SCHEMA).issubset(df.columns) else _empty_expression_statistics()
    if cancer_type:
        filtered = filtered.filter(pl.col("cancer_type") == cancer_type)
    if gene_query:
        filtered = filtered.filter(pl.col("gene_symbol").str.contains(gene_query.upper(), literal=True))
    if support_tier:
        filtered = filtered.filter(pl.col("statistical_support_tier") == support_tier.lower())
    if max_fdr is not None:
        filtered = filtered.filter(pl.col("recount3_fdr_q_value") <= float(max_fdr))
    if min_support_score is not None:
        filtered = filtered.filter(pl.col("statistical_support_score") >= float(min_support_score))
    filtered = filtered.sort(["statistical_support_score", "recount3_fdr_q_value"], descending=[True, False])
    total = filtered.height
    capped = filtered.head(max(int(limit), 0))
    return {
        "filters": {
            "cancer_type": cancer_type,
            "gene_query": gene_query,
            "support_tier": support_tier,
            "max_fdr": max_fdr,
            "min_support_score": min_support_score,
            "limit": limit,
        },
        "row_count": capped.height,
        "total_matching_rows": total,
        "warning": (
            "These are association tests with FDR and effect-size support. Source and disease status remain confounded; "
            "the results are not causal, clinical, or batch-corrected differential-expression claims."
        ),
        "rows": capped.to_dicts(),
    }
