from __future__ import annotations

from pathlib import Path

import polars as pl


REFERENCE_TRIANGULATION_SCHEMA = {
    "cancer_type": pl.Utf8,
    "gene_symbol": pl.Utf8,
    "median_tcga_tumor_expression": pl.Float64,
    "median_tcga_normal_expression": pl.Float64,
    "median_gtex_normal_expression": pl.Float64,
    "sample_count_tumor": pl.Int64,
    "sample_count_tcga_normal": pl.Int64,
    "sample_count_gtex_normal": pl.Int64,
    "log2_fc_tumor_vs_tcga_normal": pl.Float64,
    "log2_fc_tumor_vs_gtex": pl.Float64,
    "log2_fc_tcga_normal_vs_gtex": pl.Float64,
    "reference_effect_delta": pl.Float64,
    "tcga_reference_direction": pl.Utf8,
    "gtex_reference_direction": pl.Utf8,
    "reference_concordance": pl.Utf8,
    "tcga_normal_support_tier": pl.Utf8,
    "reference_stability_score": pl.Float64,
    "triangulation_caveat": pl.Utf8,
}


def _empty_reference_triangulation() -> pl.DataFrame:
    return pl.DataFrame(schema=REFERENCE_TRIANGULATION_SCHEMA)


def _project_tissue_mapping() -> pl.DataFrame:
    return pl.DataFrame(
        [
            {"cancer_type": "TCGA-BRCA", "tissue_site": "Breast - Mammary Tissue"},
            {"cancer_type": "TCGA-BRCA", "tissue_site": "Breast"},
            {"cancer_type": "TCGA-LUAD", "tissue_site": "Lung"},
            {"cancer_type": "TCGA-COAD", "tissue_site": "Colon - Transverse"},
            {"cancer_type": "TCGA-COAD", "tissue_site": "Colon - Sigmoid"},
            {"cancer_type": "TCGA-COAD", "tissue_site": "Colon"},
        ]
    )


def _direction(column: str) -> pl.Expr:
    return (
        pl.when(pl.col(column) >= 1.0)
        .then(pl.lit("up"))
        .when(pl.col(column) <= -1.0)
        .then(pl.lit("down"))
        .otherwise(pl.lit("stable"))
    )


def build_reference_triangulation_table(
    expression_tcga: pl.DataFrame,
    expression_gtex: pl.DataFrame,
) -> pl.DataFrame:
    required_tcga = {
        "project_id",
        "sample_id",
        "sample_type",
        "gene_id",
        "gene_symbol",
        "expression_value",
        "expression_unit",
        "pipeline_workflow",
        "data_origin",
    }
    required_gtex = {"gtex_sample_id", "tissue_site", "gene_symbol", "expression_value"}
    if (
        expression_tcga.is_empty()
        or expression_gtex.is_empty()
        or not required_tcga.issubset(expression_tcga.columns)
        or not required_gtex.issubset(expression_gtex.columns)
    ):
        return _empty_reference_triangulation()

    workflow = pl.col("pipeline_workflow").cast(pl.Utf8, strict=False).str.to_lowercase()
    origin = pl.col("data_origin").cast(pl.Utf8, strict=False).str.to_lowercase()
    eligible = expression_tcga.filter(
        (pl.col("expression_unit").cast(pl.Utf8, strict=False).str.to_uppercase() == "TPM")
        & pl.col("gene_id").cast(pl.Utf8, strict=False).str.starts_with("ENSG")
        & (workflow.str.contains("star", literal=True) | origin.str.contains("rna_seq.augmented_star_gene_counts"))
    )
    sample_type = pl.col("sample_type").cast(pl.Utf8, strict=False).str.to_lowercase()
    tumor = eligible.filter(sample_type == "primary tumor")
    tcga_normal = eligible.filter(sample_type == "solid tissue normal")
    if tumor.is_empty() or tcga_normal.is_empty():
        return _empty_reference_triangulation()

    tumor_agg = tumor.group_by(["project_id", "gene_symbol"]).agg(
        [
            pl.col("expression_value").median().alias("median_tcga_tumor_expression"),
            pl.col("sample_id").n_unique().cast(pl.Int64).alias("sample_count_tumor"),
        ]
    )
    tcga_normal_agg = tcga_normal.group_by(["project_id", "gene_symbol"]).agg(
        [
            pl.col("expression_value").median().alias("median_tcga_normal_expression"),
            pl.col("sample_id").n_unique().cast(pl.Int64).alias("sample_count_tcga_normal"),
        ]
    )
    gtex_agg = (
        expression_gtex.join(_project_tissue_mapping(), on="tissue_site", how="inner")
        .group_by(["cancer_type", "gene_symbol"])
        .agg(
            [
                pl.col("expression_value").median().alias("median_gtex_normal_expression"),
                pl.col("gtex_sample_id").n_unique().cast(pl.Int64).alias("sample_count_gtex_normal"),
            ]
        )
        .rename({"cancer_type": "project_id"})
    )
    combined = tumor_agg.join(tcga_normal_agg, on=["project_id", "gene_symbol"], how="inner").join(
        gtex_agg,
        on=["project_id", "gene_symbol"],
        how="inner",
    )
    if combined.is_empty():
        return _empty_reference_triangulation()

    scored = (
        combined.with_columns(
            [
                (
                    (pl.col("median_tcga_tumor_expression") + 1.0)
                    / (pl.col("median_tcga_normal_expression") + 1.0)
                )
                .log(base=2)
                .alias("log2_fc_tumor_vs_tcga_normal"),
                (
                    (pl.col("median_tcga_tumor_expression") + 1.0)
                    / (pl.col("median_gtex_normal_expression") + 1.0)
                )
                .log(base=2)
                .alias("log2_fc_tumor_vs_gtex"),
                (
                    (pl.col("median_tcga_normal_expression") + 1.0)
                    / (pl.col("median_gtex_normal_expression") + 1.0)
                )
                .log(base=2)
                .alias("log2_fc_tcga_normal_vs_gtex"),
            ]
        )
        .with_columns(
            [
                (pl.col("log2_fc_tumor_vs_tcga_normal") - pl.col("log2_fc_tumor_vs_gtex"))
                .abs()
                .alias("reference_effect_delta"),
                _direction("log2_fc_tumor_vs_tcga_normal").alias("tcga_reference_direction"),
                _direction("log2_fc_tumor_vs_gtex").alias("gtex_reference_direction"),
            ]
        )
        .with_columns(
            [
                pl.when(pl.col("tcga_reference_direction") == pl.col("gtex_reference_direction"))
                .then(pl.concat_str([pl.lit("concordant_"), pl.col("tcga_reference_direction")]))
                .when(
                    pl.col("tcga_reference_direction").is_in(["up", "down"])
                    & pl.col("gtex_reference_direction").is_in(["up", "down"])
                )
                .then(pl.lit("discordant"))
                .otherwise(pl.lit("reference_sensitive"))
                .alias("reference_concordance"),
                pl.when(pl.col("sample_count_tcga_normal") >= 30)
                .then(pl.lit("high"))
                .when(pl.col("sample_count_tcga_normal") >= 10)
                .then(pl.lit("moderate"))
                .otherwise(pl.lit("limited"))
                .alias("tcga_normal_support_tier"),
            ]
        )
        .with_columns(
            (
                (pl.col("sample_count_tcga_normal") / 30.0).clip(0.0, 1.0)
                * pl.when(pl.col("reference_concordance").str.starts_with("concordant_"))
                .then(1.0)
                .when(pl.col("reference_concordance") == "reference_sensitive")
                .then(0.5)
                .otherwise(0.0)
                * (1.0 - (pl.col("reference_effect_delta") / 4.0).clip(0.0, 1.0))
            )
            .round(6)
            .alias("reference_stability_score"),
            pl.lit(
                "TCGA adjacent normal reduces cross-study dependence but may contain field effects; GTEx remains an independent healthy reference."
            ).alias("triangulation_caveat"),
            pl.col("project_id").alias("cancer_type"),
        )
    )
    return scored.select(list(REFERENCE_TRIANGULATION_SCHEMA)).sort(
        ["reference_stability_score", "reference_effect_delta"],
        descending=[True, False],
    )


def reference_triangulation(
    cancer_type: str | None = None,
    gene_query: str | None = None,
    concordance: str | None = None,
    support_tier: str | None = None,
    min_stability: float | None = None,
    limit: int = 50,
    gold_path: str | Path = "data/gold/gold_reference_triangulation.parquet",
) -> dict[str, object]:
    path = Path(gold_path)
    df = pl.read_parquet(path) if path.exists() else _empty_reference_triangulation()
    if df.is_empty() or not set(REFERENCE_TRIANGULATION_SCHEMA).issubset(df.columns):
        filtered = _empty_reference_triangulation()
    else:
        filtered = df
        if cancer_type:
            filtered = filtered.filter(pl.col("cancer_type") == cancer_type)
        if gene_query:
            filtered = filtered.filter(
                pl.col("gene_symbol").str.to_uppercase().str.contains(gene_query.upper(), literal=True)
            )
        if concordance:
            filtered = filtered.filter(pl.col("reference_concordance") == concordance.lower())
        if support_tier:
            filtered = filtered.filter(pl.col("tcga_normal_support_tier") == support_tier.lower())
        if min_stability is not None:
            filtered = filtered.filter(pl.col("reference_stability_score") >= float(min_stability))
        filtered = filtered.sort(
            ["reference_stability_score", "reference_effect_delta"],
            descending=[True, False],
        )
    capped = filtered.head(max(int(limit), 0))
    return {
        "filters": {
            "cancer_type": cancer_type,
            "gene_query": gene_query,
            "concordance": concordance,
            "support_tier": support_tier,
            "min_stability": min_stability,
            "limit": limit,
        },
        "rows": capped.to_dicts(),
        "row_count": capped.height,
        "total_matching_rows": filtered.height,
        "warning": "Exploratory reference triangulation only; adjacent normal tissue is not equivalent to healthy tissue.",
    }
