from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import polars as pl

from src.common.config import AppConfig
from src.ingestion.gtex_downloader import gtex_metadata_stub
from src.processing.build_expression_table import with_log2_expression
from src.processing.normalize_gtex_expression import normalize_gtex_rows


def _latest_tcga_metadata_csv(metadata_dir: str | Path) -> Path:
    path = Path(metadata_dir)
    candidates = sorted(path.glob("tcga_metadata_*.csv"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not candidates:
        raise FileNotFoundError(f"No TCGA metadata CSV found in {path}")
    return candidates[0]


def _write_parquet(df: pl.DataFrame, output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.write_parquet(output_path)
    return output_path


def _empty_tcga_expression_df() -> pl.DataFrame:
    return pl.DataFrame(
        schema={
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
        }
    )


def _empty_gtex_expression_df() -> pl.DataFrame:
    return pl.DataFrame(
        schema={
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
        }
    )


def _build_tcga_expression_table(raw_metadata: pl.DataFrame, ingest_time: str) -> pl.DataFrame:
    # Until raw TCGA expression quantification files are parsed, emit stable schema with zero rows.
    return _empty_tcga_expression_df().with_columns(pl.lit(ingest_time).alias("ingested_at")).head(0)


def _build_gtex_expression_table(config: AppConfig | None, ingest_time: str) -> pl.DataFrame:
    if config is None:
        return _empty_gtex_expression_df().with_columns(pl.lit(ingest_time).alias("ingested_at")).head(0)

    rows = gtex_metadata_stub(config)
    normalized = normalize_gtex_rows(rows)
    with_log2 = with_log2_expression(normalized)
    gtex_df = pl.DataFrame(with_log2).select(
        [
            pl.col("gtex_sample_id"),
            pl.col("tissue_site"),
            pl.col("tissue_detail"),
            pl.col("gene_id_normalized").alias("gene_id"),
            pl.col("gene_symbol"),
            pl.col("expression_value").cast(pl.Float64, strict=False),
            pl.col("expression_unit"),
            pl.col("log2_expression").cast(pl.Float64, strict=False),
            pl.col("source_version"),
        ]
    )
    return gtex_df.with_columns(
        [
            pl.lit("stub").alias("data_origin"),
            pl.lit(ingest_time).alias("ingested_at"),
        ]
    )


def build_silver_tables_from_bronze(
    config: AppConfig | None = None,
    bronze_metadata_dir: str | Path = "data/bronze/tcga/metadata",
    silver_dir: str | Path = "data/silver",
) -> dict[str, object]:
    source_path = _latest_tcga_metadata_csv(bronze_metadata_dir)
    silver_root = Path(silver_dir)
    ingest_time = datetime.now(UTC).isoformat()

    raw = pl.read_csv(source_path)
    if raw.is_empty():
        raise ValueError(f"Metadata file is empty: {source_path}")

    projects = raw.select(
        [
            pl.col("project_id"),
            pl.col("primary_site"),
            pl.col("disease_type"),
        ]
    ).unique()

    patients = raw.select(
        [
            pl.col("project_id"),
            pl.col("case_id"),
            pl.col("submitter_id"),
        ]
    ).unique()

    samples = raw.select(
        [
            pl.col("project_id"),
            pl.col("case_id"),
            pl.col("sample_id"),
            pl.col("sample_type"),
        ]
    ).unique()

    file_manifest = raw.select(
        [
            pl.col("project_id"),
            pl.col("case_id"),
            pl.col("sample_id"),
            pl.col("file_id"),
            pl.col("file_name"),
            pl.col("data_category"),
            pl.col("data_type"),
            pl.col("experimental_strategy"),
            pl.col("workflow_type"),
            pl.col("access"),
            pl.col("file_size").cast(pl.Int64, strict=False),
            pl.col("md5sum"),
        ]
    ).with_columns(pl.lit(ingest_time).alias("ingested_at"))

    expression_tcga = _build_tcga_expression_table(raw, ingest_time)
    expression_gtex = _build_gtex_expression_table(config, ingest_time)

    out_projects = _write_parquet(projects, silver_root / "silver_projects.parquet")
    out_patients = _write_parquet(patients, silver_root / "silver_patients.parquet")
    out_samples = _write_parquet(samples, silver_root / "silver_samples.parquet")
    out_manifest = _write_parquet(file_manifest, silver_root / "silver_file_manifest.parquet")
    out_expr_tcga = _write_parquet(expression_tcga, silver_root / "silver_expression_tcga.parquet")
    out_expr_gtex = _write_parquet(expression_gtex, silver_root / "silver_expression_gtex.parquet")

    return {
        "source_metadata_file": str(source_path),
        "silver_projects_path": str(out_projects),
        "silver_patients_path": str(out_patients),
        "silver_samples_path": str(out_samples),
        "silver_file_manifest_path": str(out_manifest),
        "silver_expression_tcga_path": str(out_expr_tcga),
        "silver_expression_gtex_path": str(out_expr_gtex),
        "projects_count": projects.height,
        "patients_count": patients.height,
        "samples_count": samples.height,
        "file_manifest_count": file_manifest.height,
        "expression_tcga_count": expression_tcga.height,
        "expression_gtex_count": expression_gtex.height,
    }
