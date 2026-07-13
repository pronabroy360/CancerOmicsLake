from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path
import time

import numpy as np
import polars as pl
from scipy.stats import rankdata, wilcoxon

from src.analytics.expression_statistics import _benjamini_hochberg


PAIRED_EXPRESSION_SCHEMA = {
    "cancer_type": pl.Utf8,
    "gene_symbol": pl.Utf8,
    "matched_case_count": pl.Int64,
    "paired_median_tumor": pl.Float64,
    "paired_median_normal": pl.Float64,
    "paired_median_log2_difference": pl.Float64,
    "paired_wilcoxon_statistic": pl.Float64,
    "paired_p_value": pl.Float64,
    "paired_fdr_q_value": pl.Float64,
    "paired_rank_biserial": pl.Float64,
    "recount3_fdr_q_value": pl.Float64,
    "recount3_rank_biserial": pl.Float64,
    "paired_external_direction_agreement": pl.Utf8,
    "paired_support_score": pl.Float64,
    "paired_support_tier": pl.Utf8,
    "paired_caveat": pl.Utf8,
}

MIN_MATCHED_CASES = 10
FDR_THRESHOLD = 0.05
EFFECT_THRESHOLD = 0.30


def _empty_paired_expression() -> pl.DataFrame:
    return pl.DataFrame(schema=PAIRED_EXPRESSION_SCHEMA)


def _paired_rank_biserial(differences: np.ndarray) -> float:
    nonzero = differences[differences != 0]
    if nonzero.size == 0:
        return 0.0
    ranks = rankdata(np.abs(nonzero), method="average")
    positive = float(ranks[nonzero > 0].sum())
    negative = float(ranks[nonzero < 0].sum())
    total = positive + negative
    return (positive - negative) / total if total else 0.0


def _project_paired_tests(expression: pl.DataFrame, project_id: str) -> pl.DataFrame:
    project = expression.filter(pl.col("project_id") == project_id)
    tumor = (
        project.filter(pl.col("sample_type").str.to_lowercase() == "primary tumor")
        .group_by(["case_id", "gene_symbol"])
        .agg(pl.col("expression_value").median().alias("tumor_expression"))
    )
    normal = (
        project.filter(pl.col("sample_type").str.to_lowercase() == "solid tissue normal")
        .group_by(["case_id", "gene_symbol"])
        .agg(pl.col("expression_value").median().alias("normal_expression"))
    )
    matched = tumor.join(normal, on=["case_id", "gene_symbol"], how="inner")
    if matched.is_empty():
        return pl.DataFrame()
    grouped = matched.group_by("gene_symbol").agg(
        [
            pl.col("tumor_expression").alias("tumor_values"),
            pl.col("normal_expression").alias("normal_values"),
            pl.col("case_id").n_unique().alias("matched_case_count"),
        ]
    )
    rows: list[dict[str, object]] = []
    for gene_symbol, tumor_values, normal_values, matched_count in grouped.iter_rows():
        if int(matched_count) < MIN_MATCHED_CASES:
            continue
        tumor_array = np.asarray(tumor_values, dtype=float)
        normal_array = np.asarray(normal_values, dtype=float)
        tumor_log = np.log2(tumor_array + 1.0)
        normal_log = np.log2(normal_array + 1.0)
        differences = tumor_log - normal_log
        if np.allclose(differences, 0.0):
            statistic, p_value = 0.0, 1.0
        else:
            test = wilcoxon(
                tumor_log,
                normal_log,
                alternative="two-sided",
                zero_method="wilcox",
                method="approx",
            )
            statistic, p_value = float(test.statistic), max(float(test.pvalue), 1e-300)
        rows.append(
            {
                "cancer_type": project_id,
                "gene_symbol": str(gene_symbol).upper(),
                "matched_case_count": int(matched_count),
                "paired_median_tumor": float(np.median(tumor_array)),
                "paired_median_normal": float(np.median(normal_array)),
                "paired_median_log2_difference": float(np.median(differences)),
                "paired_wilcoxon_statistic": statistic,
                "paired_p_value": p_value,
                "paired_rank_biserial": float(_paired_rank_biserial(differences)),
            }
        )
    if not rows:
        return pl.DataFrame()
    result = pl.DataFrame(rows)
    return result.with_columns(
        pl.Series("paired_fdr_q_value", _benjamini_hochberg(result.get_column("paired_p_value").to_numpy()))
    )


def _build_paired_tests(tcga_path: Path) -> pl.DataFrame:
    if not tcga_path.exists():
        return pl.DataFrame()
    expression = pl.read_parquet(
        tcga_path,
        columns=["project_id", "case_id", "sample_type", "gene_symbol", "expression_value"],
    ).filter(
        pl.col("case_id").is_not_null()
        & (pl.col("case_id") != "Unknown")
        & pl.col("gene_symbol").is_not_null()
        & pl.col("expression_value").is_not_null()
    )
    results = [_project_paired_tests(expression, project_id) for project_id in sorted(expression["project_id"].unique())]
    return pl.concat([result for result in results if not result.is_empty()], how="diagonal_relaxed") if any(
        not result.is_empty() for result in results
    ) else pl.DataFrame()


def _score_paired_support(paired: pl.DataFrame, external: pl.DataFrame) -> pl.DataFrame:
    if paired.is_empty():
        return _empty_paired_expression()
    external_columns = {
        "cancer_type",
        "gene_symbol",
        "recount3_fdr_q_value",
        "recount3_rank_biserial",
    }
    if external.is_empty() or not external_columns.issubset(external.columns):
        external = pl.DataFrame(
            schema={
                "cancer_type": pl.Utf8,
                "gene_symbol": pl.Utf8,
                "recount3_fdr_q_value": pl.Float64,
                "recount3_rank_biserial": pl.Float64,
            }
        )
    joined = paired.join(
        external.select(sorted(external_columns)),
        on=["cancer_type", "gene_symbol"],
        how="left",
    ).with_columns(
        [
            pl.col("recount3_fdr_q_value").fill_null(1.0),
            pl.col("recount3_rank_biserial").fill_null(0.0),
        ]
    )
    q_score = (-pl.col("paired_fdr_q_value").clip(1e-300, 1.0).log10() / 10.0).clip(0.0, 1.0)
    effect_score = (pl.col("paired_rank_biserial").abs() / 0.5).clip(0.0, 1.0)
    sample_score = (pl.col("matched_case_count") / 40.0).clip(0.0, 1.0)
    return (
        joined.with_columns(
            [
                pl.when(
                    (pl.col("paired_rank_biserial") > 0) == (pl.col("recount3_rank_biserial") > 0)
                )
                .then(pl.lit("concordant"))
                .otherwise(pl.lit("discordant"))
                .alias("paired_external_direction_agreement"),
                (q_score * 0.50 + effect_score * 0.30 + sample_score * 0.20)
                .clip(0.0, 1.0)
                .alias("paired_support_score"),
            ]
        )
        .with_columns(
            [
                pl.when(
                    (pl.col("paired_fdr_q_value") <= FDR_THRESHOLD)
                    & (pl.col("paired_rank_biserial").abs() >= EFFECT_THRESHOLD)
                    & (pl.col("recount3_fdr_q_value") <= FDR_THRESHOLD)
                    & (pl.col("recount3_rank_biserial").abs() >= EFFECT_THRESHOLD)
                    & (pl.col("paired_external_direction_agreement") == "discordant")
                )
                .then(pl.lit("paired_discordant"))
                .when(
                    (pl.col("paired_fdr_q_value") <= FDR_THRESHOLD)
                    & (pl.col("paired_rank_biserial").abs() >= EFFECT_THRESHOLD)
                    & (pl.col("recount3_fdr_q_value") <= FDR_THRESHOLD)
                    & (pl.col("recount3_rank_biserial").abs() >= EFFECT_THRESHOLD)
                    & (pl.col("paired_external_direction_agreement") == "concordant")
                )
                .then(pl.lit("paired_replicated"))
                .when(
                    (pl.col("paired_fdr_q_value") <= FDR_THRESHOLD)
                    & (pl.col("paired_rank_biserial").abs() >= EFFECT_THRESHOLD)
                )
                .then(pl.lit("paired_internal_fdr"))
                .otherwise(pl.lit("limited"))
                .alias("paired_support_tier"),
                pl.lit(
                    "Within-case TCGA tumor-versus-adjacent-normal Wilcoxon support reduces source confounding, but adjacent tissue may contain field effects and does not establish causality or clinical validity."
                ).alias("paired_caveat"),
            ]
        )
        .with_columns(
            pl.when(pl.col("paired_support_tier") == "paired_discordant")
            .then(0.0)
            .otherwise(pl.col("paired_support_score"))
            .alias("paired_support_score")
        )
        .select(list(PAIRED_EXPRESSION_SCHEMA))
        .sort(["paired_support_score", "paired_fdr_q_value"], descending=[True, False])
    )


def build_paired_expression_support(
    tcga_path: str | Path = "data/silver/silver_expression_tcga.parquet",
    external_statistics_path: str | Path = "data/gold/gold_expression_statistical_support.parquet",
    output_path: str | Path = "data/gold/gold_paired_tcga_expression_support.parquet",
    report_path: str | Path = "outputs/reports/paired_expression_support_report.json",
) -> dict[str, object]:
    started = time.monotonic()
    output = Path(output_path)
    report = Path(report_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    report.parent.mkdir(parents=True, exist_ok=True)
    paired = _build_paired_tests(Path(tcga_path))
    external_path = Path(external_statistics_path)
    external = pl.read_parquet(external_path) if external_path.exists() else pl.DataFrame()
    result = _score_paired_support(paired, external)
    status = "completed" if not result.is_empty() else "skipped_insufficient_matched_cases"
    result.write_parquet(output)
    tier_counts = (
        result.group_by("paired_support_tier").len().sort("paired_support_tier").to_dicts()
        if not result.is_empty()
        else []
    )
    case_support = (
        result.group_by("cancer_type").agg(pl.col("matched_case_count").max()).sort("cancer_type").to_dicts()
        if not result.is_empty()
        else []
    )
    summary = {
        "status": status,
        "generated_at": datetime.now(UTC).isoformat(),
        "row_count": int(result.height),
        "minimum_matched_cases": MIN_MATCHED_CASES,
        "fdr_method": "Benjamini-Hochberg within cancer type",
        "tier_counts": tier_counts,
        "matched_case_support": case_support,
        "path": str(output),
        "elapsed_seconds": round(time.monotonic() - started, 3),
    }
    report.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def paired_expression_support(
    cancer_type: str | None = None,
    gene_query: str | None = None,
    support_tier: str | None = None,
    max_fdr: float | None = None,
    min_support_score: float | None = None,
    limit: int = 50,
    gold_path: str | Path = "data/gold/gold_paired_tcga_expression_support.parquet",
) -> dict[str, object]:
    path = Path(gold_path)
    df = pl.read_parquet(path) if path.exists() else _empty_paired_expression()
    filtered = df if set(PAIRED_EXPRESSION_SCHEMA).issubset(df.columns) else _empty_paired_expression()
    if cancer_type:
        filtered = filtered.filter(pl.col("cancer_type") == cancer_type)
    if gene_query:
        filtered = filtered.filter(pl.col("gene_symbol").str.contains(gene_query.upper(), literal=True))
    if support_tier:
        filtered = filtered.filter(pl.col("paired_support_tier") == support_tier.lower())
    if max_fdr is not None:
        filtered = filtered.filter(pl.col("paired_fdr_q_value") <= float(max_fdr))
    if min_support_score is not None:
        filtered = filtered.filter(pl.col("paired_support_score") >= float(min_support_score))
    filtered = filtered.sort(["paired_support_score", "paired_fdr_q_value"], descending=[True, False])
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
            "Paired TCGA testing reduces source confounding but adjacent-normal field effects remain; "
            "results are not causal or clinically validated."
        ),
        "rows": capped.to_dicts(),
    }
