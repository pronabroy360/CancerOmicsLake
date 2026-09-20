from __future__ import annotations

import polars as pl

from src.processing.mutation_consequences import classify_protein_impact


FUNCTIONAL_EVIDENCE_SCHEMA = {
    "gene_symbol": pl.Utf8,
    "cancer_type": pl.Utf8,
    "total_profiled_sample_count": pl.Int64,
    "protein_altering_mutated_sample_count": pl.Int64,
    "putative_loss_of_function_sample_count": pl.Int64,
    "missense_sample_count": pl.Int64,
    "inframe_sample_count": pl.Int64,
    "other_protein_altering_sample_count": pl.Int64,
    "recurrent_locus_count": pl.Int64,
    "max_locus_sample_count": pl.Int64,
    "samples_with_recurrent_locus_count": pl.Int64,
    "recurrent_locus_sample_fraction": pl.Float64,
    "recurrence_threshold_samples": pl.Int64,
    "driver_evidence_scope": pl.Utf8,
    "driver_classification": pl.Utf8,
}

_LOCUS_KEYS = [
    "project_id",
    "gene_symbol",
    "chromosome",
    "start_position",
    "reference_allele",
    "tumor_seq_allele",
]


def build_mutation_functional_evidence(
    mutations: pl.DataFrame,
    mutation_profile: pl.DataFrame,
    recurrence_threshold_samples: int = 2,
) -> pl.DataFrame:
    """Summarize functional classes and exact-locus recurrence without calling drivers."""
    if recurrence_threshold_samples < 2:
        raise ValueError("recurrence_threshold_samples must be at least 2")
    required = {"project_id", "sample_id", "gene_symbol", "variant_classification", *_LOCUS_KEYS[2:]}
    if mutations.is_empty() or not required.issubset(mutations.columns):
        return pl.DataFrame(schema=FUNCTIONAL_EVIDENCE_SCHEMA)

    events = (
        mutations.filter(
            pl.col("project_id").is_not_null()
            & pl.col("sample_id").is_not_null()
            & pl.col("gene_symbol").is_not_null()
            & pl.col("is_protein_altering").fill_null(False)
        )
        .with_columns(
            pl.col("variant_classification")
            .map_elements(classify_protein_impact, return_dtype=pl.Utf8)
            .alias("functional_impact_group")
        )
    )
    if events.is_empty():
        return pl.DataFrame(schema=FUNCTIONAL_EVIDENCE_SCHEMA)

    profile_source = mutation_profile if not mutation_profile.is_empty() else events
    denominators = profile_source.group_by("project_id").agg(
        pl.col("sample_id").n_unique().cast(pl.Int64).alias("total_profiled_sample_count")
    )
    counts = events.group_by(["project_id", "gene_symbol"]).agg(
        [
            pl.col("sample_id").n_unique().cast(pl.Int64).alias("protein_altering_mutated_sample_count"),
            *[
                pl.col("sample_id")
                .filter(pl.col("functional_impact_group") == group)
                .n_unique()
                .cast(pl.Int64)
                .alias(column)
                for group, column in (
                    ("putative_loss_of_function", "putative_loss_of_function_sample_count"),
                    ("missense", "missense_sample_count"),
                    ("inframe", "inframe_sample_count"),
                    ("other_protein_altering", "other_protein_altering_sample_count"),
                )
            ],
        ]
    )

    recurrent_loci = (
        events.group_by(_LOCUS_KEYS)
        .agg(pl.col("sample_id").n_unique().cast(pl.Int64).alias("locus_sample_count"))
        .filter(pl.col("locus_sample_count") >= recurrence_threshold_samples)
    )
    if recurrent_loci.is_empty():
        recurrence = counts.select(["project_id", "gene_symbol"]).with_columns(
            [
                pl.lit(0, dtype=pl.Int64).alias("recurrent_locus_count"),
                pl.lit(0, dtype=pl.Int64).alias("max_locus_sample_count"),
                pl.lit(0, dtype=pl.Int64).alias("samples_with_recurrent_locus_count"),
            ]
        )
    else:
        recurrent_summary = recurrent_loci.group_by(["project_id", "gene_symbol"]).agg(
            [
                pl.len().cast(pl.Int64).alias("recurrent_locus_count"),
                pl.col("locus_sample_count").max().cast(pl.Int64).alias("max_locus_sample_count"),
            ]
        )
        recurrent_samples = (
            events.join(recurrent_loci.select(_LOCUS_KEYS), on=_LOCUS_KEYS, how="inner")
            .group_by(["project_id", "gene_symbol"])
            .agg(pl.col("sample_id").n_unique().cast(pl.Int64).alias("samples_with_recurrent_locus_count"))
        )
        recurrence = recurrent_summary.join(recurrent_samples, on=["project_id", "gene_symbol"], how="left")

    return (
        counts.join(denominators, on="project_id", how="left")
        .join(recurrence, on=["project_id", "gene_symbol"], how="left")
        .with_columns(
            [
                pl.col("project_id").alias("cancer_type"),
                pl.col("recurrent_locus_count").fill_null(0).cast(pl.Int64),
                pl.col("max_locus_sample_count").fill_null(0).cast(pl.Int64),
                pl.col("samples_with_recurrent_locus_count").fill_null(0).cast(pl.Int64),
            ]
        )
        .with_columns(
            (
                pl.col("samples_with_recurrent_locus_count")
                / pl.when(pl.col("total_profiled_sample_count") > 0)
                .then(pl.col("total_profiled_sample_count"))
                .otherwise(None)
            )
            .fill_null(0.0)
            .cast(pl.Float64)
            .alias("recurrent_locus_sample_fraction"),
            pl.lit(recurrence_threshold_samples, dtype=pl.Int64).alias("recurrence_threshold_samples"),
            pl.lit("consequence_and_exact_locus_recurrence").alias("driver_evidence_scope"),
            pl.lit("not_assessed").alias("driver_classification"),
        )
        .select(*FUNCTIONAL_EVIDENCE_SCHEMA.keys())
        .sort(["cancer_type", "gene_symbol"])
    )
