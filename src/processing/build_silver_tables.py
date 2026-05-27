from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import polars as pl


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


def build_silver_tables_from_bronze(
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

    out_projects = _write_parquet(projects, silver_root / "silver_projects.parquet")
    out_patients = _write_parquet(patients, silver_root / "silver_patients.parquet")
    out_samples = _write_parquet(samples, silver_root / "silver_samples.parquet")
    out_manifest = _write_parquet(file_manifest, silver_root / "silver_file_manifest.parquet")

    return {
        "source_metadata_file": str(source_path),
        "silver_projects_path": str(out_projects),
        "silver_patients_path": str(out_patients),
        "silver_samples_path": str(out_samples),
        "silver_file_manifest_path": str(out_manifest),
        "projects_count": projects.height,
        "patients_count": patients.height,
        "samples_count": samples.height,
        "file_manifest_count": file_manifest.height,
    }

