from __future__ import annotations

import csv
from datetime import UTC, datetime
import gzip
import json
import math
from pathlib import Path
from typing import Any, Iterator

import polars as pl
import pyarrow as pa
import pyarrow.parquet as pq

from src.common.config import AppConfig


GTEX_ARROW_SCHEMA = pa.schema(
    [
        ("gtex_sample_id", pa.string()),
        ("donor_id", pa.string()),
        ("tissue_site", pa.string()),
        ("tissue_detail", pa.string()),
        ("gene_id", pa.string()),
        ("gene_symbol", pa.string()),
        ("expression_value", pa.float64()),
        ("expression_unit", pa.string()),
        ("log2_expression", pa.float64()),
        ("source_version", pa.string()),
        ("data_origin", pa.string()),
        ("ingested_at", pa.string()),
    ]
)


def _batched(rows: Iterator[list[str]], batch_size: int) -> Iterator[list[list[str]]]:
    batch: list[list[str]] = []
    for row in rows:
        batch.append(row)
        if len(batch) >= batch_size:
            yield batch
            batch = []
    if batch:
        yield batch


def _sample_tissue_map(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream, delimiter="\t")
        return {
            str(row.get("SAMPID", "")): str(row.get("SMTSD", ""))
            for row in reader
            if row.get("SAMPID")
        }


def _open_gct(path: Path, sample_cap: int) -> tuple[list[str], Iterator[list[str]], int]:
    stream = gzip.open(path, "rt", encoding="utf-8", newline="")
    reader = csv.reader(stream, delimiter="\t")
    version = next(reader, [])
    dimensions = next(reader, [])
    header = next(reader, [])
    if not version or version[0] != "#1.3" or len(header) < 4:
        stream.close()
        raise ValueError(f"Unsupported or malformed GTEx GCT file: {path}")
    declared_genes = int(dimensions[0]) if dimensions else 0
    samples = header[3 : 3 + sample_cap]

    def selected_rows() -> Iterator[list[str]]:
        try:
            for row in reader:
                if len(row) >= 3 + len(samples):
                    yield [row[1], row[2], *row[3 : 3 + len(samples)]]
        finally:
            stream.close()

    return samples, selected_rows(), declared_genes


def _long_batch(
    rows: list[list[str]],
    sample_ids: list[str],
    tissue: str,
    source_version: str,
    source_path: Path,
    ingested_at: str,
) -> pa.Table:
    columns = ["gene_id_raw", "gene_symbol", *sample_ids]
    wide = pl.DataFrame(rows, schema=columns, orient="row", strict=False)
    long = (
        wide.with_columns(
            pl.col("gene_id_raw").cast(pl.Utf8).str.replace(r"\.\d+$", "").alias("gene_id")
        )
        .drop("gene_id_raw")
        .unpivot(index=["gene_id", "gene_symbol"], variable_name="gtex_sample_id", value_name="expression_value")
        .with_columns(
            [
                pl.col("gtex_sample_id").str.extract(r"^(GTEX-[^-]+)", 1).alias("donor_id"),
                pl.lit(tissue).alias("tissue_site"),
                pl.lit(tissue).alias("tissue_detail"),
                pl.col("expression_value").cast(pl.Float64, strict=False).fill_null(0.0),
                pl.lit("TPM").alias("expression_unit"),
                pl.col("expression_value")
                .cast(pl.Float64, strict=False)
                .fill_null(0.0)
                .map_elements(lambda value: math.log2(value + 1.0), return_dtype=pl.Float64)
                .alias("log2_expression"),
                pl.lit(source_version).alias("source_version"),
                pl.lit(str(source_path)).alias("data_origin"),
                pl.lit(ingested_at).alias("ingested_at"),
            ]
        )
        .select(GTEX_ARROW_SCHEMA.names)
    )
    return long.to_arrow().cast(GTEX_ARROW_SCHEMA)


def harmonize_gtex_gct_files(
    config: AppConfig,
    input_dir: str | Path = "data/bronze/gtex/expression",
    output_path: str | Path = "data/silver/silver_expression_gtex.parquet",
    report_path: str | Path = "outputs/reports/gtex_harmonization_report.json",
    sample_cap_per_tissue: int | None = None,
    gene_batch_size: int = 250,
) -> dict[str, Any]:
    root = Path(input_dir)
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    temporary = out.with_suffix(out.suffix + ".tmp")
    temporary.unlink(missing_ok=True)
    sample_cap = sample_cap_per_tissue or config.gtex.sample_cap_per_tissue
    if sample_cap <= 0:
        raise ValueError("GTEx sample cap must be positive")

    sample_attributes = root / Path(config.gtex.sample_attributes_url).name
    metadata_tissues = _sample_tissue_map(sample_attributes)
    ingested_at = datetime.now(UTC).isoformat()
    tissue_results: list[dict[str, object]] = []
    total_rows = 0
    total_genes = 0
    writer: pq.ParquetWriter | None = None

    try:
        writer = pq.ParquetWriter(temporary, GTEX_ARROW_SCHEMA, compression="zstd")
        for tissue in config.gtex.tissues:
            file_name = config.gtex.tissue_files.get(tissue)
            if not file_name:
                raise ValueError(f"No GTEx file configured for tissue: {tissue}")
            source = root / file_name
            if not source.exists():
                raise FileNotFoundError(f"Missing GTEx expression file: {source}")

            sample_ids, rows, declared_genes = _open_gct(source, sample_cap)
            mismatch_samples = [
                sample_id
                for sample_id in sample_ids
                if metadata_tissues and metadata_tissues.get(sample_id) != tissue
            ]
            if mismatch_samples:
                raise ValueError(
                    f"GTEx sample metadata tissue mismatch for {tissue}: {mismatch_samples[:5]}"
                )

            genes_written = 0
            rows_written = 0
            for batch in _batched(rows, gene_batch_size):
                table = _long_batch(
                    batch,
                    sample_ids,
                    tissue,
                    config.gtex.version,
                    source,
                    ingested_at,
                )
                writer.write_table(table)
                genes_written += len(batch)
                rows_written += table.num_rows
            tissue_results.append(
                {
                    "tissue": tissue,
                    "source_file": str(source),
                    "declared_gene_count": declared_genes,
                    "genes_written": genes_written,
                    "samples_selected": len(sample_ids),
                    "rows_written": rows_written,
                    "metadata_validated": bool(metadata_tissues),
                }
            )
            total_rows += rows_written
            total_genes += genes_written
    except Exception:
        if writer is not None:
            writer.close()
        temporary.unlink(missing_ok=True)
        raise
    else:
        if writer is not None:
            writer.close()
        temporary.replace(out)

    payload = {
        "generated_at": datetime.now(UTC).isoformat(),
        "status": "passed",
        "source": "GTEx Portal open-access V8 tissue TPM GCT files",
        "source_version": config.gtex.version,
        "sample_cap_per_tissue": sample_cap,
        "tissue_count": len(tissue_results),
        "selected_sample_count": sum(int(row["samples_selected"]) for row in tissue_results),
        "total_rows": total_rows,
        "total_gene_tissue_rows": total_genes,
        "output_path": str(out),
        "output_bytes": out.stat().st_size,
        "tissues": tissue_results,
    }
    report = Path(report_path)
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload
