from __future__ import annotations

from pathlib import Path

import polars as pl


BATCH_EFFECT_SENSITIVITY_SCHEMA = {
    "cancer_type": pl.Utf8,
    "gene_symbol": pl.Utf8,
    "tumor_log2_median": pl.Float64,
    "normal_log2_median": pl.Float64,
    "tumor_expression_percentile": pl.Float64,
    "normal_expression_percentile": pl.Float64,
    "percentile_delta": pl.Float64,
    "tumor_robust_z": pl.Float64,
    "normal_robust_z": pl.Float64,
    "robust_z_delta": pl.Float64,
    "sample_count_tumor": pl.Int64,
    "sample_count_normal": pl.Int64,
    "support_tier": pl.Utf8,
    "sensitivity_direction": pl.Utf8,
    "batch_method": pl.Utf8,
    "batch_effect_caveat": pl.Utf8,
}


def _empty_batch_effect_sensitivity() -> pl.DataFrame:
    return pl.DataFrame(schema=BATCH_EFFECT_SENSITIVITY_SCHEMA)


def _load_batch_effect_sensitivity(gold_path: str | Path) -> pl.DataFrame:
    path = Path(gold_path)
    if not path.exists():
        return _empty_batch_effect_sensitivity()
    df = pl.read_parquet(path)
    if not set(BATCH_EFFECT_SENSITIVITY_SCHEMA).issubset(set(df.columns)):
        return _empty_batch_effect_sensitivity()
    return df.select(list(BATCH_EFFECT_SENSITIVITY_SCHEMA))


def batch_effect_sensitivity(
    cancer_type: str | None = None,
    gene_query: str | None = None,
    support_tier: str | None = None,
    direction: str | None = None,
    min_abs_percentile_delta: float | None = None,
    limit: int = 50,
    gold_path: str | Path = "data/gold/gold_batch_effect_sensitivity.parquet",
) -> dict[str, object]:
    df = _load_batch_effect_sensitivity(gold_path)
    if df.is_empty():
        return {
            "filters": {
                "cancer_type": cancer_type,
                "gene_query": gene_query,
                "support_tier": support_tier,
                "direction": direction,
                "min_abs_percentile_delta": min_abs_percentile_delta,
                "limit": limit,
            },
            "rows": [],
            "row_count": 0,
            "warning": "Batch-effect sensitivity mart is unavailable. Run `make run-gold` first.",
        }

    filtered = df
    if cancer_type:
        filtered = filtered.filter(pl.col("cancer_type") == cancer_type)
    if gene_query:
        filtered = filtered.filter(
            pl.col("gene_symbol").cast(pl.Utf8).str.to_uppercase().str.contains(gene_query.upper(), literal=True)
        )
    if support_tier:
        filtered = filtered.filter(pl.col("support_tier").cast(pl.Utf8).str.to_lowercase() == support_tier.lower())
    if direction:
        filtered = filtered.filter(
            pl.col("sensitivity_direction").cast(pl.Utf8).str.to_lowercase() == direction.lower()
        )
    if min_abs_percentile_delta is not None:
        filtered = filtered.filter(pl.col("percentile_delta").abs() >= float(min_abs_percentile_delta))

    filtered = filtered.sort(
        [
            pl.col("percentile_delta").abs(),
            pl.col("robust_z_delta").abs(),
            pl.col("sample_count_tumor"),
            pl.col("sample_count_normal"),
        ],
        descending=[True, True, True, True],
    )
    capped = filtered.head(max(int(limit), 0))
    return {
        "filters": {
            "cancer_type": cancer_type,
            "gene_query": gene_query,
            "support_tier": support_tier,
            "direction": direction,
            "min_abs_percentile_delta": min_abs_percentile_delta,
            "limit": limit,
        },
        "rows": capped.to_dicts(),
        "row_count": capped.height,
        "total_matching_rows": filtered.height,
        "warning": (
            "Exploratory batch-effect sensitivity only; rank and robust-z scaling reduce scale dependence "
            "but do not remove TCGA-GTEx study effects."
        ),
    }


def batch_effect_sensitivity_dataframe(
    cancer_type: str | None = None,
    gene_query: str | None = None,
    support_tier: str | None = None,
    direction: str | None = None,
    min_abs_percentile_delta: float | None = None,
    limit: int = 50,
    gold_path: str | Path = "data/gold/gold_batch_effect_sensitivity.parquet",
) -> pl.DataFrame:
    payload = batch_effect_sensitivity(
        cancer_type=cancer_type,
        gene_query=gene_query,
        support_tier=support_tier,
        direction=direction,
        min_abs_percentile_delta=min_abs_percentile_delta,
        limit=limit,
        gold_path=gold_path,
    )
    rows = payload.get("rows", [])
    return pl.DataFrame(rows) if rows else _empty_batch_effect_sensitivity()
