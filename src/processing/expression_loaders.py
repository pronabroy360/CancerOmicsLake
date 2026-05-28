from __future__ import annotations

import math
from pathlib import Path

import polars as pl

from src.common.config import AppConfig
from src.ingestion.gtex_downloader import gtex_metadata_stub
from src.processing.normalize_gene_ids import normalize_gene_id


def _to_log2(value: float) -> float:
    return math.log2(value + 1.0)


def _safe_read_table(path: Path) -> pl.DataFrame:
    if path.suffix.lower() in {".tsv", ".txt"}:
        return pl.read_csv(path, separator="\t")
    return pl.read_csv(path)


def _resolve_column(df: pl.DataFrame, candidates: list[str]) -> str | None:
    columns = {c.lower(): c for c in df.columns}
    for candidate in candidates:
        if candidate.lower() in columns:
            return columns[candidate.lower()]
    return None


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


def _normalize_gene_id_series(series: pl.Series) -> pl.Series:
    return pl.Series(
        name=series.name,
        values=[normalize_gene_id(str(v))["gene_id_normalized"] if v is not None else "" for v in series.to_list()],
    )


def _infer_tcga_expression_unit(expr_col_name: str, workflow_type: str) -> str:
    col = expr_col_name.lower().strip()
    workflow = workflow_type.lower().strip()
    if col == "tpm":
        return "TPM"
    if col == "fpkm":
        return "FPKM"
    if col == "count":
        return "COUNT"
    if "count" in workflow:
        return "COUNT"
    return "TPM"


def _parse_tcga_expression_file(path: Path, metadata_df: pl.DataFrame) -> pl.DataFrame:
    raw = _safe_read_table(path)
    if raw.is_empty():
        return _empty_tcga_expression_df().head(0)

    sample_col = _resolve_column(raw, ["sample_id", "sample", "sampleid"])
    gene_id_col = _resolve_column(raw, ["gene_id", "gene", "ensembl_gene_id"])
    gene_symbol_col = _resolve_column(raw, ["gene_symbol", "symbol", "hgnc_symbol"])
    expr_col = _resolve_column(raw, ["expression_value", "tpm", "fpkm", "value", "count"])

    if sample_col is None or gene_id_col is None or expr_col is None:
        return _empty_tcga_expression_df().head(0)

    base = raw.select(
        [
            pl.col(sample_col).cast(pl.Utf8).alias("sample_id"),
            pl.col(gene_id_col).cast(pl.Utf8).alias("gene_id_raw"),
            (
                pl.col(gene_symbol_col).cast(pl.Utf8)
                if gene_symbol_col is not None
                else pl.lit("Unknown", dtype=pl.Utf8)
            ).alias("gene_symbol"),
            pl.col(expr_col).cast(pl.Float64, strict=False).fill_null(0.0).alias("expression_value"),
        ]
    )

    if "sample_id" in metadata_df.columns:
        meta = metadata_df.select(
            [
                pl.col("project_id"),
                pl.col("case_id"),
                pl.col("sample_id"),
                pl.col("sample_type"),
                pl.col("workflow_type"),
            ]
        ).unique(subset=["sample_id"])
        base = base.join(meta, on="sample_id", how="left")
    else:
        base = base.with_columns(
            [
                pl.lit("Unknown").alias("project_id"),
                pl.lit("Unknown").alias("case_id"),
                pl.lit("Unknown").alias("sample_type"),
                pl.lit("Unknown").alias("workflow_type"),
            ]
        )

    gene_id_series = _normalize_gene_id_series(base.get_column("gene_id_raw")).alias("gene_id")
    base = base.with_columns(gene_id_series)
    expr_unit = _infer_tcga_expression_unit(
        expr_col_name=expr_col,
        workflow_type=str(base.get_column("workflow_type")[0] if base.height > 0 else ""),
    )

    return base.select(
        [
            pl.col("project_id").fill_null("Unknown").cast(pl.Utf8),
            pl.col("case_id").fill_null("Unknown").cast(pl.Utf8),
            pl.col("sample_id").fill_null("Unknown").cast(pl.Utf8),
            pl.col("sample_type").fill_null("Unknown").cast(pl.Utf8),
            pl.col("gene_id").fill_null("").cast(pl.Utf8),
            pl.col("gene_symbol").fill_null("Unknown").cast(pl.Utf8),
            pl.col("expression_value").cast(pl.Float64),
            pl.lit(expr_unit).alias("expression_unit"),
            pl.col("expression_value").map_elements(_to_log2, return_dtype=pl.Float64).alias("log2_expression"),
            pl.col("workflow_type").fill_null("Unknown").cast(pl.Utf8).alias("pipeline_workflow"),
            pl.lit(str(path)).alias("data_origin"),
        ]
    )


def _metadata_has(df: pl.DataFrame, columns: list[str]) -> bool:
    return all(col in df.columns for col in columns)


def _resolve_tcga_expression_files_from_manifest(root: Path, metadata_df: pl.DataFrame) -> list[Path]:
    required = ["file_name", "data_category", "data_type"]
    if not _metadata_has(metadata_df, required):
        return []

    manifest = metadata_df.select(
        [
            pl.col("project_id") if "project_id" in metadata_df.columns else pl.lit(None).alias("project_id"),
            pl.col("file_name").cast(pl.Utf8),
            pl.col("data_category").cast(pl.Utf8),
            pl.col("data_type").cast(pl.Utf8),
            pl.col("access").cast(pl.Utf8) if "access" in metadata_df.columns else pl.lit("open").alias("access"),
        ]
    ).unique(subset=["project_id", "file_name", "data_category", "data_type", "access"])

    expression_manifest = manifest.filter(
        pl.col("data_category").str.to_lowercase().str.contains("transcriptome profiling")
        & (
            pl.col("data_type").str.to_lowercase().str.contains("gene expression")
            | pl.col("data_type").str.to_lowercase().str.contains("isoform expression")
        )
        & (pl.col("access").str.to_lowercase() == "open")
    )

    if expression_manifest.is_empty():
        return []

    files: list[Path] = []
    for row in expression_manifest.iter_rows(named=True):
        file_name = str(row["file_name"])
        project_id = row.get("project_id")
        candidate_paths: list[Path] = []
        if project_id:
            candidate_paths.append(root / str(project_id) / "expression" / file_name)
            candidate_paths.append(root / str(project_id) / file_name)
        candidate_paths.append(root / "expression" / file_name)

        resolved = next((p for p in candidate_paths if p.exists()), None)
        if resolved is not None:
            files.append(resolved)

    unique_files = sorted(set(files))
    return unique_files


def load_tcga_expression_table(
    config: AppConfig | None,
    ingest_time: str,
    metadata_df: pl.DataFrame,
    tcga_expression_dir: str | Path = "data/bronze/tcga",
) -> pl.DataFrame:
    empty = _empty_tcga_expression_df().with_columns(pl.lit(ingest_time).alias("ingested_at")).head(0)
    if config is None:
        return empty

    root = Path(tcga_expression_dir)
    if not root.exists():
        return empty

    files = _resolve_tcga_expression_files_from_manifest(root=root, metadata_df=metadata_df)
    if not files:
        files = sorted(root.glob("**/expression/*.*"))

    frames: list[pl.DataFrame] = []
    for file_path in files:
        if file_path.suffix.lower() not in {".csv", ".tsv", ".txt"}:
            continue
        parsed = _parse_tcga_expression_file(file_path, metadata_df)
        if not parsed.is_empty():
            frames.append(parsed)

    if not frames:
        return empty

    combined = pl.concat(frames, how="vertical")
    return combined.with_columns(pl.lit(ingest_time).alias("ingested_at"))


def _parse_gtex_expression_file(path: Path, config: AppConfig) -> pl.DataFrame:
    raw = _safe_read_table(path)
    if raw.is_empty():
        return _empty_gtex_expression_df().head(0)

    sample_col = _resolve_column(raw, ["gtex_sample_id", "sample_id", "sample"])
    tissue_site_col = _resolve_column(raw, ["tissue_site", "tissue"])
    tissue_detail_col = _resolve_column(raw, ["tissue_detail", "tissue_detail_site", "tissue"])
    gene_id_col = _resolve_column(raw, ["gene_id", "gene", "ensembl_gene_id"])
    gene_symbol_col = _resolve_column(raw, ["gene_symbol", "symbol", "hgnc_symbol"])
    expr_col = _resolve_column(raw, ["expression_value", "tpm", "value"])
    expr_unit_col = _resolve_column(raw, ["expression_unit", "unit"])
    source_version_col = _resolve_column(raw, ["source_version", "version"])

    if sample_col is None or tissue_site_col is None or gene_id_col is None or expr_col is None:
        return _empty_gtex_expression_df().head(0)

    base = raw.select(
        [
            pl.col(sample_col).cast(pl.Utf8).alias("gtex_sample_id"),
            pl.col(tissue_site_col).cast(pl.Utf8).alias("tissue_site"),
            (
                pl.col(tissue_detail_col).cast(pl.Utf8)
                if tissue_detail_col is not None
                else pl.col(tissue_site_col).cast(pl.Utf8)
            ).alias("tissue_detail"),
            pl.col(gene_id_col).cast(pl.Utf8).alias("gene_id_raw"),
            (
                pl.col(gene_symbol_col).cast(pl.Utf8)
                if gene_symbol_col is not None
                else pl.lit("Unknown", dtype=pl.Utf8)
            ).alias("gene_symbol"),
            pl.col(expr_col).cast(pl.Float64, strict=False).fill_null(0.0).alias("expression_value"),
            (
                pl.col(expr_unit_col).cast(pl.Utf8)
                if expr_unit_col is not None
                else pl.lit("TPM", dtype=pl.Utf8)
            ).alias("expression_unit"),
            (
                pl.col(source_version_col).cast(pl.Utf8)
                if source_version_col is not None
                else pl.lit(config.gtex.version, dtype=pl.Utf8)
            ).alias("source_version"),
        ]
    )
    gene_id_series = _normalize_gene_id_series(base.get_column("gene_id_raw")).alias("gene_id")
    base = base.with_columns(gene_id_series)

    return base.select(
        [
            pl.col("gtex_sample_id"),
            pl.col("tissue_site"),
            pl.col("tissue_detail"),
            pl.col("gene_id"),
            pl.col("gene_symbol"),
            pl.col("expression_value"),
            pl.col("expression_unit"),
            pl.col("expression_value").map_elements(_to_log2, return_dtype=pl.Float64).alias("log2_expression"),
            pl.col("source_version"),
            pl.lit(str(path)).alias("data_origin"),
        ]
    )


def _gtex_stub_frame(config: AppConfig) -> pl.DataFrame:
    rows = gtex_metadata_stub(config)
    mapped_rows: list[dict[str, object]] = []
    for row in rows:
        mapped = normalize_gene_id(row["gene_id"])
        expr = float(row["expression_value"])
        mapped_rows.append(
            {
                "gtex_sample_id": row["gtex_sample_id"],
                "tissue_site": row["tissue_site"],
                "tissue_detail": row["tissue_detail"],
                "gene_id": mapped["gene_id_normalized"],
                "gene_symbol": row["gene_symbol"],
                "expression_value": expr,
                "expression_unit": row["expression_unit"],
                "log2_expression": _to_log2(expr),
                "source_version": row["source_version"],
                "data_origin": "stub",
            }
        )
    return pl.DataFrame(mapped_rows)


def load_gtex_expression_table(
    config: AppConfig | None,
    ingest_time: str,
    gtex_expression_dir: str | Path = "data/bronze/gtex/expression",
) -> pl.DataFrame:
    empty = _empty_gtex_expression_df().with_columns(pl.lit(ingest_time).alias("ingested_at")).head(0)
    if config is None:
        return empty

    root = Path(gtex_expression_dir)
    files = sorted(root.glob("*.*")) if root.exists() else []

    frames: list[pl.DataFrame] = []
    for file_path in files:
        if file_path.suffix.lower() not in {".csv", ".tsv", ".txt"}:
            continue
        parsed = _parse_gtex_expression_file(file_path, config)
        if not parsed.is_empty():
            frames.append(parsed)

    if not frames:
        stub = _gtex_stub_frame(config)
        return stub.with_columns(pl.lit(ingest_time).alias("ingested_at"))

    combined = pl.concat(frames, how="vertical")
    return combined.with_columns(pl.lit(ingest_time).alias("ingested_at"))
