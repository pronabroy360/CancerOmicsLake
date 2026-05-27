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
                "mutation_record_count": 0,
                "generated_at": datetime.now(UTC).isoformat(),
            }
        ]
    )

    output_path = gold_root / "gold_cohort_summary.parquet"
    summary.write_parquet(output_path)

    return {
        "gold_cohort_summary_path": str(output_path),
        "tcga_project_count": int(summary["tcga_project_count"][0]),
        "tcga_patient_count": int(summary["tcga_patient_count"][0]),
        "tcga_sample_count": int(summary["tcga_sample_count"][0]),
        "tcga_file_count": int(summary["tcga_file_count"][0]),
        "gtex_expression_sample_count": int(summary["gtex_expression_sample_count"][0]),
        "tcga_expression_row_count": int(summary["tcga_expression_row_count"][0]),
        "gtex_expression_row_count": int(summary["gtex_expression_row_count"][0]),
    }
