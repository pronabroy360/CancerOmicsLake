from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path
import time

import polars as pl


EXTERNAL_VALIDATION_SCHEMA = {
    "cancer_type": pl.Utf8,
    "gene_symbol": pl.Utf8,
    "native_log2_fold_change": pl.Float64,
    "recount3_log2_fold_change": pl.Float64,
    "effect_delta": pl.Float64,
    "native_direction": pl.Utf8,
    "recount3_direction": pl.Utf8,
    "direction_agreement": pl.Utf8,
    "native_abs_effect_rank": pl.Float64,
    "recount3_abs_effect_rank": pl.Float64,
    "absolute_rank_delta": pl.Float64,
    "top_k": pl.Int64,
    "top_k_overlap": pl.Boolean,
    "top_k_jaccard_by_cancer": pl.Float64,
    "native_sample_count_tumor": pl.Int64,
    "native_sample_count_normal": pl.Int64,
    "recount3_sample_count_tumor": pl.Int64,
    "recount3_sample_count_normal": pl.Int64,
    "validation_score": pl.Float64,
    "validation_tier": pl.Utf8,
    "external_source": pl.Utf8,
    "external_annotation": pl.Utf8,
    "validation_caveat": pl.Utf8,
}


PROJECT_TISSUES = {
    "TCGA-BRCA": ["Breast - Mammary Tissue", "Breast"],
    "TCGA-LUAD": ["Lung"],
    "TCGA-COAD": ["Colon - Transverse", "Colon - Sigmoid", "Colon"],
}


def _empty_external_validation() -> pl.DataFrame:
    return pl.DataFrame(schema=EXTERNAL_VALIDATION_SCHEMA)


def _direction(expr: str) -> pl.Expr:
    return (
        pl.when(pl.col(expr) >= 1.0)
        .then(pl.lit("up"))
        .when(pl.col(expr) <= -1.0)
        .then(pl.lit("down"))
        .otherwise(pl.lit("stable"))
    )


def _read_recount3_expression(path: Path) -> pl.DataFrame:
    if not path.exists():
        return pl.DataFrame()
    if path.suffix.lower() == ".csv":
        df = pl.read_csv(path)
    else:
        df = pl.read_parquet(path)
    required = {"gene_symbol", "expression_value", "source"}
    if not required.issubset(set(df.columns)):
        raise ValueError(f"recount3 expression extract missing required columns: {sorted(required - set(df.columns))}")
    for column, dtype in {
        "project_id": pl.Utf8,
        "sample_id": pl.Utf8,
        "sample_type": pl.Utf8,
        "tissue_site": pl.Utf8,
        "external_annotation": pl.Utf8,
    }.items():
        if column not in df.columns:
            df = df.with_columns(pl.lit(None, dtype=dtype).alias(column))
    return df.with_columns(
        [
            pl.col("source").cast(pl.Utf8, strict=False).str.to_uppercase().alias("source"),
            pl.col("gene_symbol").cast(pl.Utf8, strict=False).str.to_uppercase().alias("gene_symbol"),
            pl.col("expression_value").cast(pl.Float64, strict=False).alias("expression_value"),
            pl.col("sample_id").cast(pl.Utf8, strict=False).fill_null("").alias("sample_id"),
            pl.col("project_id").cast(pl.Utf8, strict=False).fill_null("").alias("project_id"),
            pl.col("sample_type").cast(pl.Utf8, strict=False).fill_null("").alias("sample_type"),
            pl.col("tissue_site").cast(pl.Utf8, strict=False).fill_null("").alias("tissue_site"),
            pl.col("external_annotation").cast(pl.Utf8, strict=False).fill_null("unknown").alias("external_annotation"),
        ]
    ).filter(pl.col("expression_value").is_not_null() & (pl.col("expression_value") >= 0))


def _build_recount3_contrasts(recount3: pl.DataFrame) -> pl.DataFrame:
    if recount3.is_empty():
        return pl.DataFrame()

    contrasts: list[pl.DataFrame] = []
    for project_id, tissues in PROJECT_TISSUES.items():
        tumor = (
            recount3.filter(
                (pl.col("source") == "TCGA")
                & (pl.col("project_id") == project_id)
                & (pl.col("sample_type").str.to_lowercase() == "primary tumor")
            )
            .group_by("gene_symbol")
            .agg(
                [
                    pl.col("expression_value").median().alias("recount3_median_tumor_expression"),
                    pl.col("sample_id").n_unique().alias("recount3_sample_count_tumor"),
                ]
            )
        )
        normal = (
            recount3.filter((pl.col("source") == "GTEX") & pl.col("tissue_site").is_in(tissues))
            .group_by("gene_symbol")
            .agg(
                [
                    pl.col("expression_value").median().alias("recount3_median_normal_expression"),
                    pl.col("sample_id").n_unique().alias("recount3_sample_count_normal"),
                    pl.col("external_annotation").drop_nulls().first().alias("external_annotation"),
                ]
            )
        )
        if tumor.is_empty() or normal.is_empty():
            continue
        contrasts.append(
            tumor.join(normal, on="gene_symbol", how="inner").with_columns(
                [
                    pl.lit(project_id).alias("cancer_type"),
                    (
                        (pl.col("recount3_median_tumor_expression") + 1.0).log(2)
                        - (pl.col("recount3_median_normal_expression") + 1.0).log(2)
                    ).alias("recount3_log2_fold_change"),
                ]
            )
        )
    if not contrasts:
        return pl.DataFrame()
    return pl.concat(contrasts, how="diagonal_relaxed")


def build_external_expression_validation(
    gold_dir: str | Path = "data/gold",
    recount3_expression_path: str | Path = "data/silver/silver_expression_recount3.parquet",
    output_path: str | Path = "data/gold/gold_external_expression_validation.parquet",
    report_path: str | Path = "outputs/reports/external_expression_validation_report.json",
    top_k: int = 100,
) -> dict[str, object]:
    if top_k < 1:
        raise ValueError("top_k must be positive")
    started = time.monotonic()
    gold_root = Path(gold_dir)
    native_path = gold_root / "gold_tumor_vs_normal_expression.parquet"
    output = Path(output_path)
    report = Path(report_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    report.parent.mkdir(parents=True, exist_ok=True)

    if not native_path.exists() or not Path(recount3_expression_path).exists():
        result = _empty_external_validation()
        status = "skipped_missing_inputs"
    else:
        native = pl.read_parquet(native_path)
        recount3 = _read_recount3_expression(Path(recount3_expression_path))
        recount3_contrasts = _build_recount3_contrasts(recount3)
        if native.is_empty() or recount3_contrasts.is_empty():
            result = _empty_external_validation()
            status = "skipped_no_overlap"
        else:
            result = _score_validation(native, recount3_contrasts, top_k=top_k)
            status = "completed"

    result.write_parquet(output)
    tier_counts = (
        result.group_by("validation_tier").len().sort("validation_tier").to_dicts()
        if not result.is_empty()
        else []
    )
    summary = {
        "status": status,
        "generated_at": datetime.now(UTC).isoformat(),
        "row_count": int(result.height),
        "top_k": int(top_k),
        "tier_counts": tier_counts,
        "external_source": "recount3",
        "input_path": str(recount3_expression_path),
        "path": str(output),
        "elapsed_seconds": round(time.monotonic() - started, 3),
    }
    report.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def _score_validation(native: pl.DataFrame, recount3_contrasts: pl.DataFrame, top_k: int) -> pl.DataFrame:
    native_required = {
        "cancer_type",
        "gene_symbol",
        "log2_fold_change",
        "sample_count_tumor",
        "sample_count_normal",
    }
    if not native_required.issubset(set(native.columns)):
        raise ValueError(f"native tumor-vs-normal table missing required columns: {sorted(native_required - set(native.columns))}")

    joined = (
        native.select(
            [
                "cancer_type",
                pl.col("gene_symbol").cast(pl.Utf8, strict=False).str.to_uppercase().alias("gene_symbol"),
                pl.col("log2_fold_change").cast(pl.Float64, strict=False).alias("native_log2_fold_change"),
                pl.col("sample_count_tumor").cast(pl.Int64, strict=False).alias("native_sample_count_tumor"),
                pl.col("sample_count_normal").cast(pl.Int64, strict=False).alias("native_sample_count_normal"),
            ]
        )
        .join(
            recount3_contrasts.select(
                [
                    "cancer_type",
                    "gene_symbol",
                    "recount3_log2_fold_change",
                    "recount3_sample_count_tumor",
                    "recount3_sample_count_normal",
                    "external_annotation",
                ]
            ),
            on=["cancer_type", "gene_symbol"],
            how="inner",
        )
        .with_columns(
            [
                pl.col("native_log2_fold_change").abs().rank(method="average", descending=True).over("cancer_type").alias("native_abs_effect_rank"),
                pl.col("recount3_log2_fold_change").abs().rank(method="average", descending=True).over("cancer_type").alias("recount3_abs_effect_rank"),
            ]
        )
        .with_columns(
            [
                (pl.col("native_log2_fold_change") - pl.col("recount3_log2_fold_change")).abs().alias("effect_delta"),
                _direction("native_log2_fold_change").alias("native_direction"),
                _direction("recount3_log2_fold_change").alias("recount3_direction"),
                (pl.col("native_abs_effect_rank") - pl.col("recount3_abs_effect_rank")).abs().alias("absolute_rank_delta"),
            ]
        )
        .with_columns(
            [
                pl.when(pl.col("native_direction") == pl.col("recount3_direction"))
                .then(pl.lit("concordant"))
                .when(
                    pl.col("native_direction").is_in(["up", "down"])
                    & pl.col("recount3_direction").is_in(["up", "down"])
                )
                .then(pl.lit("discordant"))
                .otherwise(pl.lit("inconclusive"))
                .alias("direction_agreement"),
                (pl.col("native_abs_effect_rank") <= top_k).alias("native_top_k"),
                (pl.col("recount3_abs_effect_rank") <= top_k).alias("recount3_top_k"),
            ]
        )
    )
    if joined.is_empty():
        return _empty_external_validation()

    jaccards = {}
    for project_id in joined.get_column("cancer_type").unique().to_list():
        project = joined.filter(pl.col("cancer_type") == project_id)
        native_top = set(project.filter(pl.col("native_top_k")).get_column("gene_symbol").to_list())
        recount_top = set(project.filter(pl.col("recount3_top_k")).get_column("gene_symbol").to_list())
        union = native_top | recount_top
        jaccards[str(project_id)] = len(native_top & recount_top) / len(union) if union else 0.0

    jaccard_df = pl.DataFrame(
        {
            "cancer_type": list(jaccards.keys()),
            "top_k_jaccard_by_cancer": list(jaccards.values()),
        },
        schema={"cancer_type": pl.Utf8, "top_k_jaccard_by_cancer": pl.Float64},
    )

    return (
        joined.join(jaccard_df, on="cancer_type", how="left")
        .with_columns(
            [
                (pl.col("native_top_k") & pl.col("recount3_top_k")).alias("top_k_overlap"),
                pl.col("top_k_jaccard_by_cancer").fill_null(0.0),
                (
                    (
                        pl.when(pl.col("direction_agreement") == "concordant")
                        .then(1.0)
                        .when(pl.col("direction_agreement") == "inconclusive")
                        .then(0.5)
                        .otherwise(0.0)
                    )
                    * 0.45
                    + (1.0 - (pl.col("effect_delta") / 4.0).clip(0.0, 1.0)) * 0.35
                    + (1.0 - (pl.col("absolute_rank_delta") / pl.len().over("cancer_type")).clip(0.0, 1.0)) * 0.20
                ).alias("validation_score"),
            ]
        )
        .with_columns(
            [
                pl.when(pl.col("validation_score") >= 0.8)
                .then(pl.lit("high"))
                .when(pl.col("validation_score") >= 0.6)
                .then(pl.lit("moderate"))
                .when(pl.col("validation_score") >= 0.4)
                .then(pl.lit("limited"))
                .otherwise(pl.lit("discordant"))
                .alias("validation_tier"),
                pl.lit(int(top_k)).alias("top_k"),
                pl.lit("recount3").alias("external_source"),
                pl.lit(
                    "External validation against uniformly processed recount3 expression; agreement strengthens reproducibility but does not establish clinical validity."
                ).alias("validation_caveat"),
            ]
        )
        .select(list(EXTERNAL_VALIDATION_SCHEMA))
        .sort(["validation_score", "top_k_overlap", "effect_delta"], descending=[True, True, False])
        .with_columns(pl.col(pl.Float64).round(6))
    )


def external_expression_validation(
    cancer_type: str | None = None,
    gene_query: str | None = None,
    validation_tier: str | None = None,
    direction_agreement: str | None = None,
    min_validation_score: float | None = None,
    limit: int = 50,
    gold_path: str | Path = "data/gold/gold_external_expression_validation.parquet",
) -> dict[str, object]:
    path = Path(gold_path)
    df = pl.read_parquet(path) if path.exists() else _empty_external_validation()
    if df.is_empty():
        filtered = _empty_external_validation()
    else:
        filtered = df
        if cancer_type:
            filtered = filtered.filter(pl.col("cancer_type") == cancer_type)
        if gene_query:
            filtered = filtered.filter(pl.col("gene_symbol").str.contains(gene_query.upper()))
        if validation_tier:
            filtered = filtered.filter(pl.col("validation_tier") == validation_tier.lower())
        if direction_agreement:
            filtered = filtered.filter(pl.col("direction_agreement") == direction_agreement.lower())
        if min_validation_score is not None:
            filtered = filtered.filter(pl.col("validation_score") >= float(min_validation_score))
        filtered = filtered.sort(["validation_score", "effect_delta"], descending=[True, False])

    total_matching = int(filtered.height)
    return {
        "filters": {
            "cancer_type": cancer_type,
            "gene_query": gene_query,
            "validation_tier": validation_tier,
            "direction_agreement": direction_agreement,
            "min_validation_score": min_validation_score,
            "limit": limit,
        },
        "row_count": int(min(total_matching, limit)),
        "total_matching_rows": total_matching,
        "warning": (
            "External recount3 validation is a reproducibility check over a uniformly processed expression source; "
            "it is not clinical validation."
        ),
        "rows": filtered.head(limit).to_dicts(),
    }
