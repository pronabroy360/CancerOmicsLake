from __future__ import annotations

import polars as pl


TRANSCRIPT_EVIDENCE_SCHEMA = {
    "cancer_type": pl.Utf8,
    "gene_symbol": pl.Utf8,
    "transcript_id": pl.Utf8,
    "vep_consequence": pl.Utf8,
    "vep_impact": pl.Utf8,
    "variant_classification": pl.Utf8,
    "profiled_sample_count": pl.Int64,
    "distinct_sample_count": pl.Int64,
    "event_count": pl.Int64,
    "sample_fraction": pl.Float64,
    "hgvsc_annotation_event_count": pl.Int64,
    "hgvsp_annotation_event_count": pl.Int64,
    "all_effects_annotation_event_count": pl.Int64,
    "annotation_scope": pl.Utf8,
    "impact_interpretation": pl.Utf8,
}

_GROUP_KEYS = [
    "project_id",
    "gene_symbol",
    "transcript_id",
    "vep_consequence",
    "vep_impact",
    "variant_classification",
]


def build_mutation_transcript_evidence(
    mutations: pl.DataFrame,
    mutation_profile: pl.DataFrame,
) -> pl.DataFrame:
    """Aggregate source-reported transcript annotations without biological interpretation."""
    required = {"project_id", "sample_id", "gene_symbol"}
    if mutations.is_empty() or not required.issubset(mutations.columns):
        return pl.DataFrame(schema=TRANSCRIPT_EVIDENCE_SCHEMA)

    annotation_columns = ("transcript_id", "vep_consequence", "vep_impact", "variant_classification")
    missing_group_fields = [column for column in _GROUP_KEYS if column not in mutations.columns]
    if missing_group_fields:
        mutations = mutations.with_columns([pl.lit("Unknown").alias(column) for column in missing_group_fields])
    for column in ("hgvsc", "hgvsp", "all_effects"):
        if column not in mutations.columns:
            mutations = mutations.with_columns(pl.lit(None, dtype=pl.Utf8).alias(column))
    events = mutations.filter(
        pl.col("project_id").is_not_null()
        & pl.col("sample_id").is_not_null()
        & pl.col("gene_symbol").is_not_null()
        & pl.col("gene_symbol").cast(pl.Utf8).str.strip_chars().ne("")
    )
    if events.is_empty():
        return pl.DataFrame(schema=TRANSCRIPT_EVIDENCE_SCHEMA)

    events = events.with_columns(
        [
            (
                pl.col(column).cast(pl.Utf8).fill_null("Unknown").str.strip_chars()
                .str.to_uppercase() if column == "vep_impact"
                else pl.col(column).cast(pl.Utf8).fill_null("Unknown").str.strip_chars()
            ).replace("", "Unknown").alias(column)
            for column in annotation_columns
        ]
    )
    profile_source = mutation_profile if not mutation_profile.is_empty() else events
    denominators = profile_source.group_by("project_id").agg(
        pl.col("sample_id").n_unique().cast(pl.Int64).alias("profiled_sample_count")
    )
    counts = events.group_by(_GROUP_KEYS).agg(
        [
            pl.col("sample_id").n_unique().cast(pl.Int64).alias("distinct_sample_count"),
            pl.len().cast(pl.Int64).alias("event_count"),
            *[
                pl.col(column).cast(pl.Utf8).fill_null("").str.strip_chars().ne("")
                .sum().cast(pl.Int64).alias(f"{column}_annotation_event_count")
                for column in ("hgvsc", "hgvsp", "all_effects")
            ],
        ]
    )
    return (
        counts.join(denominators, on="project_id", how="left")
        .with_columns(
            pl.col("project_id").alias("cancer_type"),
            (
                pl.col("distinct_sample_count")
                / pl.when(pl.col("profiled_sample_count") > 0)
                .then(pl.col("profiled_sample_count"))
                .otherwise(None)
            )
            .fill_null(0.0)
            .cast(pl.Float64)
            .alias("sample_fraction"),
            pl.lit("gdc_maf_reported_transcript").alias("annotation_scope"),
            pl.lit("source_vep_category_not_driver_classification").alias("impact_interpretation"),
        )
        .select(*TRANSCRIPT_EVIDENCE_SCHEMA.keys())
        .sort(["cancer_type", "gene_symbol", "transcript_id", "vep_consequence", "vep_impact"])
    )
