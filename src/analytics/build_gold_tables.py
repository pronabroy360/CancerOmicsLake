from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
import time

import polars as pl


def _read_or_empty(path: Path, schema: dict[str, pl.DataType]) -> pl.DataFrame:
    if path.exists():
        last_error: BaseException | None = None
        for _ in range(3):
            try:
                return pl.read_parquet(path)
            except BaseException as exc:
                last_error = exc
                time.sleep(0.2)
        # Fallback to pyarrow reader for occasional runtime parquet panics.
        try:
            import pyarrow.parquet as pq

            table = pq.read_table(path)
            return pl.from_arrow(table)
        except Exception:
            if last_error:
                raise RuntimeError(f"Failed to read parquet file: {path}") from last_error
            raise
    return pl.DataFrame(schema=schema)


def _project_tissue_mapping() -> pl.DataFrame:
    return pl.DataFrame(
        [
            {"project_id": "TCGA-BRCA", "tissue_site": "Breast - Mammary Tissue"},
            {"project_id": "TCGA-BRCA", "tissue_site": "Breast"},
            {"project_id": "TCGA-LUAD", "tissue_site": "Lung"},
            {"project_id": "TCGA-COAD", "tissue_site": "Colon - Transverse"},
            {"project_id": "TCGA-COAD", "tissue_site": "Colon - Sigmoid"},
            {"project_id": "TCGA-COAD", "tissue_site": "Colon"},
        ]
    )


def _empty_tumor_vs_normal() -> pl.DataFrame:
    return pl.DataFrame(
        schema={
            "gene_symbol": pl.Utf8,
            "cancer_type": pl.Utf8,
            "median_tcga_tumor_expression": pl.Float64,
            "median_gtex_normal_expression": pl.Float64,
            "mean_tcga_tumor_expression": pl.Float64,
            "mean_gtex_normal_expression": pl.Float64,
            "log2_fold_change": pl.Float64,
            "sample_count_tumor": pl.Int64,
            "sample_count_normal": pl.Int64,
        }
    )


def _build_tumor_vs_normal_table(expr_tcga: pl.DataFrame, expr_gtex: pl.DataFrame) -> pl.DataFrame:
    if expr_tcga.is_empty() or expr_gtex.is_empty():
        return _empty_tumor_vs_normal()

    tumor = expr_tcga.filter(
        pl.col("sample_type").cast(pl.Utf8, strict=False).str.to_lowercase().str.contains("tumor")
    )
    if tumor.is_empty():
        return _empty_tumor_vs_normal()

    tumor_agg = tumor.group_by(["project_id", "gene_symbol"]).agg(
        [
            pl.col("expression_value").median().alias("median_tcga_tumor_expression"),
            pl.col("expression_value").mean().alias("mean_tcga_tumor_expression"),
            pl.col("sample_id").n_unique().cast(pl.Int64).alias("sample_count_tumor"),
        ]
    )

    mapping = _project_tissue_mapping()
    normal = expr_gtex.join(mapping, on="tissue_site", how="inner")
    if normal.is_empty():
        return _empty_tumor_vs_normal()

    normal_agg = normal.group_by(["project_id", "gene_symbol"]).agg(
        [
            pl.col("expression_value").median().alias("median_gtex_normal_expression"),
            pl.col("expression_value").mean().alias("mean_gtex_normal_expression"),
            pl.col("gtex_sample_id").n_unique().cast(pl.Int64).alias("sample_count_normal"),
        ]
    )

    combined = tumor_agg.join(normal_agg, on=["project_id", "gene_symbol"], how="inner")
    if combined.is_empty():
        return _empty_tumor_vs_normal()

    return combined.with_columns(
        [
            pl.col("project_id").alias("cancer_type"),
            (
                (
                    (pl.col("median_tcga_tumor_expression") + 1.0)
                    / (pl.col("median_gtex_normal_expression") + 1.0)
                )
                .log(base=2)
                .cast(pl.Float64)
            ).alias("log2_fold_change"),
        ]
    ).select(
        [
            pl.col("gene_symbol"),
            pl.col("cancer_type"),
            pl.col("median_tcga_tumor_expression").cast(pl.Float64),
            pl.col("median_gtex_normal_expression").cast(pl.Float64),
            pl.col("mean_tcga_tumor_expression").cast(pl.Float64),
            pl.col("mean_gtex_normal_expression").cast(pl.Float64),
            pl.col("log2_fold_change"),
            pl.col("sample_count_tumor").cast(pl.Int64),
            pl.col("sample_count_normal").cast(pl.Int64),
        ]
    )


def build_gold_cohort_summary(
    silver_dir: str | Path = "data/silver",
    gold_dir: str | Path = "data/gold",
) -> dict[str, object]:
    silver_root = Path(silver_dir)
    gold_root = Path(gold_dir)
    gold_root.mkdir(parents=True, exist_ok=True)

    projects = _read_or_empty(
        silver_root / "silver_projects.parquet",
        {"project_id": pl.Utf8, "primary_site": pl.Utf8, "disease_type": pl.Utf8},
    )
    patients = _read_or_empty(
        silver_root / "silver_patients.parquet",
        {"project_id": pl.Utf8, "case_id": pl.Utf8, "submitter_id": pl.Utf8},
    )
    samples = _read_or_empty(
        silver_root / "silver_samples.parquet",
        {"project_id": pl.Utf8, "case_id": pl.Utf8, "sample_id": pl.Utf8, "sample_type": pl.Utf8},
    )
    file_manifest = _read_or_empty(
        silver_root / "silver_file_manifest.parquet",
        {
            "project_id": pl.Utf8,
            "case_id": pl.Utf8,
            "sample_id": pl.Utf8,
            "file_id": pl.Utf8,
            "file_name": pl.Utf8,
            "data_category": pl.Utf8,
            "data_type": pl.Utf8,
            "experimental_strategy": pl.Utf8,
            "workflow_type": pl.Utf8,
            "access": pl.Utf8,
            "file_size": pl.Int64,
            "md5sum": pl.Utf8,
            "ingested_at": pl.Utf8,
        },
    )
    expr_tcga = _read_or_empty(
        silver_root / "silver_expression_tcga.parquet",
        {
            "project_id": pl.Utf8,
            "case_id": pl.Utf8,
            "sample_id": pl.Utf8,
            "sample_type": pl.Utf8,
            "gene_id": pl.Utf8,
            "gene_symbol": pl.Utf8,
            "expression_value": pl.Float64,
            "expression_unit": pl.Utf8,
            "log2_expression": pl.Float64,
            "pipeline_workflow": pl.Utf8,
            "data_origin": pl.Utf8,
            "ingested_at": pl.Utf8,
        },
    )
    expr_gtex = _read_or_empty(
        silver_root / "silver_expression_gtex.parquet",
        {
            "gtex_sample_id": pl.Utf8,
            "tissue_site": pl.Utf8,
            "tissue_detail": pl.Utf8,
            "gene_id": pl.Utf8,
            "gene_symbol": pl.Utf8,
            "expression_value": pl.Float64,
            "expression_unit": pl.Utf8,
            "log2_expression": pl.Float64,
            "source_version": pl.Utf8,
            "data_origin": pl.Utf8,
            "ingested_at": pl.Utf8,
        },
    )
    mutations = _read_or_empty(
        silver_root / "silver_mutations.parquet",
        {
            "project_id": pl.Utf8,
            "case_id": pl.Utf8,
            "sample_id": pl.Utf8,
            "gene_id": pl.Utf8,
            "gene_symbol": pl.Utf8,
            "variant_classification": pl.Utf8,
            "variant_type": pl.Utf8,
            "chromosome": pl.Utf8,
            "start_position": pl.Int64,
            "end_position": pl.Int64,
            "reference_allele": pl.Utf8,
            "tumor_seq_allele": pl.Utf8,
            "data_origin": pl.Utf8,
            "ingested_at": pl.Utf8,
        },
    )

    summary = pl.DataFrame(
        [
            {
                "tcga_project_count": projects.select(pl.col("project_id").n_unique()).item(0, 0)
                if not projects.is_empty()
                else 0,
                "tcga_patient_count": patients.select(pl.col("case_id").n_unique()).item(0, 0)
                if not patients.is_empty()
                else 0,
                "tcga_sample_count": samples.select(pl.col("sample_id").n_unique()).item(0, 0)
                if not samples.is_empty()
                else 0,
                "tcga_file_count": file_manifest.select(pl.col("file_id").n_unique()).item(0, 0)
                if not file_manifest.is_empty()
                else 0,
                "gtex_expression_sample_count": expr_gtex.select(pl.col("gtex_sample_id").n_unique()).item(0, 0)
                if not expr_gtex.is_empty()
                else 0,
                "tcga_expression_row_count": expr_tcga.height,
                "gtex_expression_row_count": expr_gtex.height,
                "gene_count": 0,
                "mutation_record_count": mutations.height,
                "generated_at": datetime.now(UTC).isoformat(),
            }
        ]
    )

    if mutations.is_empty():
        mutation_by_gene = pl.DataFrame(
            schema={
                "gene_symbol": pl.Utf8,
                "cancer_type": pl.Utf8,
                "mutated_sample_count": pl.Int64,
                "total_profiled_sample_count": pl.Int64,
                "mutation_frequency": pl.Float64,
                "top_variant_classification": pl.Utf8,
            }
        )
        mutation_by_cancer = pl.DataFrame(
            schema={
                "cancer_type": pl.Utf8,
                "total_profiled_sample_count": pl.Int64,
                "mutated_sample_count": pl.Int64,
                "mutation_event_count": pl.Int64,
                "mutation_event_rate": pl.Float64,
            }
        )
    else:
        mutation_events = mutations.filter(
            pl.col("project_id").is_not_null() & pl.col("sample_id").is_not_null() & pl.col("gene_symbol").is_not_null()
        )
        sample_counts = samples.group_by("project_id").agg(
            pl.col("sample_id").n_unique().alias("total_profiled_sample_count")
        )
        mutated_counts = mutation_events.group_by(["project_id", "gene_symbol"]).agg(
            pl.col("sample_id").n_unique().alias("mutated_sample_count")
        )
        variant_top = (
            mutation_events.group_by(["project_id", "gene_symbol", "variant_classification"])
            .len()
            .sort(["project_id", "gene_symbol", "len"], descending=[False, False, True])
            .group_by(["project_id", "gene_symbol"])
            .agg(pl.first("variant_classification").alias("top_variant_classification"))
        )
        mutation_by_gene = (
            mutated_counts.join(variant_top, on=["project_id", "gene_symbol"], how="left")
            .join(sample_counts, on="project_id", how="left")
            .with_columns(
                [
                    pl.col("project_id").alias("cancer_type"),
                    (
                        pl.col("mutated_sample_count")
                        / pl.when(pl.col("total_profiled_sample_count") > 0)
                        .then(pl.col("total_profiled_sample_count"))
                        .otherwise(None)
                    ).cast(pl.Float64).alias("mutation_frequency"),
                ]
            )
            .select(
                [
                    pl.col("gene_symbol"),
                    pl.col("cancer_type"),
                    pl.col("mutated_sample_count"),
                    pl.col("total_profiled_sample_count").fill_null(0).cast(pl.Int64),
                    pl.col("mutation_frequency").fill_null(0.0),
                    pl.col("top_variant_classification").fill_null("Unknown"),
                ]
            )
        )

        mutation_by_cancer = (
            mutation_events.group_by("project_id")
            .agg(
                [
                    pl.col("sample_id").n_unique().alias("mutated_sample_count"),
                    pl.len().alias("mutation_event_count"),
                ]
            )
            .join(sample_counts, on="project_id", how="left")
            .with_columns(
                [
                    pl.col("project_id").alias("cancer_type"),
                    (
                        pl.col("mutation_event_count")
                        / pl.when(pl.col("total_profiled_sample_count") > 0)
                        .then(pl.col("total_profiled_sample_count"))
                        .otherwise(None)
                    ).cast(pl.Float64).alias("mutation_event_rate"),
                ]
            )
            .select(
                [
                    pl.col("cancer_type"),
                    pl.col("total_profiled_sample_count").fill_null(0).cast(pl.Int64),
                    pl.col("mutated_sample_count").fill_null(0).cast(pl.Int64),
                    pl.col("mutation_event_count").fill_null(0).cast(pl.Int64),
                    pl.col("mutation_event_rate").fill_null(0.0),
                ]
            )
        )

    output_path = gold_root / "gold_cohort_summary.parquet"
    output_mut_by_gene = gold_root / "gold_mutation_frequency_by_gene.parquet"
    output_mut_by_cancer = gold_root / "gold_mutation_frequency_by_cancer.parquet"
    output_tumor_vs_normal = gold_root / "gold_tumor_vs_normal_expression.parquet"
    tumor_vs_normal = _build_tumor_vs_normal_table(expr_tcga=expr_tcga, expr_gtex=expr_gtex)
    summary.write_parquet(output_path)
    mutation_by_gene.write_parquet(output_mut_by_gene)
    mutation_by_cancer.write_parquet(output_mut_by_cancer)
    tumor_vs_normal.write_parquet(output_tumor_vs_normal)

    return {
        "gold_cohort_summary_path": str(output_path),
        "gold_mutation_frequency_by_gene_path": str(output_mut_by_gene),
        "gold_mutation_frequency_by_cancer_path": str(output_mut_by_cancer),
        "gold_tumor_vs_normal_expression_path": str(output_tumor_vs_normal),
        "tcga_project_count": int(summary["tcga_project_count"][0]),
        "tcga_patient_count": int(summary["tcga_patient_count"][0]),
        "tcga_sample_count": int(summary["tcga_sample_count"][0]),
        "tcga_file_count": int(summary["tcga_file_count"][0]),
        "gtex_expression_sample_count": int(summary["gtex_expression_sample_count"][0]),
        "tcga_expression_row_count": int(summary["tcga_expression_row_count"][0]),
        "gtex_expression_row_count": int(summary["gtex_expression_row_count"][0]),
        "mutation_record_count": int(summary["mutation_record_count"][0]),
        "mutation_gene_rows": int(mutation_by_gene.height),
        "mutation_cancer_rows": int(mutation_by_cancer.height),
        "tumor_vs_normal_rows": int(tumor_vs_normal.height),
    }
