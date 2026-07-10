from pathlib import Path

import polars as pl

from src.analytics.batch_effect_sensitivity import (
    BATCH_EFFECT_SENSITIVITY_SCHEMA,
    batch_effect_sensitivity,
    batch_effect_sensitivity_dataframe,
)


def test_batch_effect_sensitivity_filters_and_sorts(tmp_path: Path) -> None:
    path = tmp_path / "gold_batch_effect_sensitivity.parquet"
    rows = [
        {
            "cancer_type": "TCGA-BRCA",
            "gene_symbol": "TP53",
            "tumor_log2_median": 5.0,
            "normal_log2_median": 2.0,
            "tumor_expression_percentile": 0.95,
            "normal_expression_percentile": 0.10,
            "percentile_delta": 0.85,
            "tumor_robust_z": 2.0,
            "normal_robust_z": -0.5,
            "robust_z_delta": 2.5,
            "sample_count_tumor": 95,
            "sample_count_normal": 50,
            "support_tier": "high",
            "sensitivity_direction": "rank_up",
            "batch_method": "within_cohort_rank_and_robust_z",
            "batch_effect_caveat": "exploratory",
        },
        {
            "cancer_type": "TCGA-BRCA",
            "gene_symbol": "LOW1",
            "tumor_log2_median": 1.0,
            "normal_log2_median": 5.0,
            "tumor_expression_percentile": 0.05,
            "normal_expression_percentile": 0.90,
            "percentile_delta": -0.85,
            "tumor_robust_z": -1.0,
            "normal_robust_z": 1.0,
            "robust_z_delta": -2.0,
            "sample_count_tumor": 95,
            "sample_count_normal": 50,
            "support_tier": "high",
            "sensitivity_direction": "rank_down",
            "batch_method": "within_cohort_rank_and_robust_z",
            "batch_effect_caveat": "exploratory",
        },
    ]
    pl.DataFrame(rows, schema=BATCH_EFFECT_SENSITIVITY_SCHEMA).write_parquet(path)

    payload = batch_effect_sensitivity(
        cancer_type="TCGA-BRCA",
        support_tier="high",
        direction="rank_up",
        min_abs_percentile_delta=0.5,
        gold_path=path,
    )

    assert payload["row_count"] == 1
    assert payload["rows"][0]["gene_symbol"] == "TP53"
    assert "Exploratory batch-effect sensitivity" in payload["warning"]


def test_batch_effect_sensitivity_dataframe_returns_empty_contract(tmp_path: Path) -> None:
    df = batch_effect_sensitivity_dataframe(gold_path=tmp_path / "missing.parquet")

    assert df.is_empty()
    assert set(BATCH_EFFECT_SENSITIVITY_SCHEMA).issubset(set(df.columns))
