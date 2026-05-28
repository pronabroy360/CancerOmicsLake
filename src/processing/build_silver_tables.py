from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import polars as pl

from src.common.config import AppConfig
from src.processing.build_mutation_table import load_tcga_mutation_table
from src.processing.expression_loaders import load_gtex_expression_table, load_tcga_expression_table


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
    config: AppConfig | None = None,
    bronze_metadata_dir: str | Path = "data/bronze/tcga/metadata",
    silver_dir: str | Path = "data/silver",
    tcga_expression_dir: str | Path | None = None,
    gtex_expression_dir: str | Path = "data/bronze/gtex/expression",
) -> dict[str, object]:
    source_path = _latest_tcga_metadata_csv(bronze_metadata_dir)
    silver_root = Path(silver_dir)
    ingest_time = datetime.now(UTC).isoformat()
    tcga_expr_root = Path(tcga_expression_dir) if tcga_expression_dir is not None else Path(bronze_metadata_dir).parent

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

    expression_tcga = load_tcga_expression_table(
        config=config,
        ingest_time=ingest_time,
        metadata_df=raw,
        tcga_expression_dir=tcga_expr_root,
    )
    expression_gtex = load_gtex_expression_table(
        config=config,
        ingest_time=ingest_time,
        gtex_expression_dir=gtex_expression_dir,
    )
    mutations_tcga = load_tcga_mutation_table(config=config, ingest_time=ingest_time, metadata_df=raw)

    out_projects = _write_parquet(projects, silver_root / "silver_projects.parquet")
    out_patients = _write_parquet(patients, silver_root / "silver_patients.parquet")
    out_samples = _write_parquet(samples, silver_root / "silver_samples.parquet")
    out_manifest = _write_parquet(file_manifest, silver_root / "silver_file_manifest.parquet")
    out_expr_tcga = _write_parquet(expression_tcga, silver_root / "silver_expression_tcga.parquet")
    out_expr_gtex = _write_parquet(expression_gtex, silver_root / "silver_expression_gtex.parquet")
    out_mutations = _write_parquet(mutations_tcga, silver_root / "silver_mutations.parquet")

    return {
        "source_metadata_file": str(source_path),
        "silver_projects_path": str(out_projects),
        "silver_patients_path": str(out_patients),
        "silver_samples_path": str(out_samples),
        "silver_file_manifest_path": str(out_manifest),
        "silver_expression_tcga_path": str(out_expr_tcga),
        "silver_expression_gtex_path": str(out_expr_gtex),
        "silver_mutations_path": str(out_mutations),
        "projects_count": projects.height,
        "patients_count": patients.height,
        "samples_count": samples.height,
        "file_manifest_count": file_manifest.height,
        "expression_tcga_count": expression_tcga.height,
        "expression_gtex_count": expression_gtex.height,
        "mutations_count": mutations_tcga.height,
    }
