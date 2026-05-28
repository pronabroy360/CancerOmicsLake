from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

import polars as pl


@dataclass
class CheckResult:
    check_name: str
    status: str
    failed_rows: int = 0
    metric_name: str = ""
    metric_value: float | None = None
    threshold: float | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def check_non_negative_expression(rows: list[dict[str, str]]) -> CheckResult:
    failed = sum(1 for row in rows if float(row["expression_value"]) < 0)
    return CheckResult(
        check_name="expression_values_non_negative",
        status="passed" if failed == 0 else "failed",
        failed_rows=failed,
    )


def check_gene_mapping_rate(mapped_rows: list[dict[str, str]], threshold: float = 0.98) -> CheckResult:
    if not mapped_rows:
        rate = 0.0
    else:
        ok = sum(1 for row in mapped_rows if bool(row.get("gene_id_normalized")))
        rate = ok / len(mapped_rows)
    status = "passed" if rate >= threshold else "warning"
    return CheckResult(
        check_name="gene_mapping_rate",
        status=status,
        metric_name="mapping_rate",
        metric_value=rate,
        threshold=threshold,
    )


def build_quality_payload(run_id: str, results: list[CheckResult]) -> dict[str, object]:
    statuses = {result.status for result in results}
    status = "passed"
    if "failed" in statuses:
        status = "failed"
    elif "warning" in statuses:
        status = "passed_with_warnings"
    return {
        "pipeline_run_id": run_id,
        "generated_at": datetime.now(UTC).isoformat(),
        "status": status,
        "checks": [result.to_dict() for result in results],
    }


def _read_or_empty(path: Path, schema: dict[str, pl.DataType]) -> pl.DataFrame:
    if path.exists():
        return pl.read_parquet(path)
    return pl.DataFrame(schema=schema)


def _count_null_or_blank(df: pl.DataFrame, col: str) -> int:
    if col not in df.columns:
        return 0
    return (
        df.select(
            pl.col(col)
            .cast(pl.Utf8, strict=False)
            .fill_null("")
            .str.strip_chars()
            .eq("")
            .sum()
            .cast(pl.Int64)
            .alias("cnt")
        )
        .item(0, 0)
        or 0
    )


def run_silver_quality_checks(silver_dir: str | Path = "data/silver") -> list[CheckResult]:
    root = Path(silver_dir)

    projects = _read_or_empty(
        root / "silver_projects.parquet",
        {"project_id": pl.Utf8, "primary_site": pl.Utf8, "disease_type": pl.Utf8},
    )
    samples = _read_or_empty(
        root / "silver_samples.parquet",
        {"project_id": pl.Utf8, "case_id": pl.Utf8, "sample_id": pl.Utf8, "sample_type": pl.Utf8},
    )
    manifest = _read_or_empty(
        root / "silver_file_manifest.parquet",
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
    expr_gtex = _read_or_empty(
        root / "silver_expression_gtex.parquet",
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

    null_project_ids = _count_null_or_blank(projects, "project_id")
    duplicate_sample_ids = (
        samples.group_by("sample_id").len().filter(pl.col("len") > 1).height if "sample_id" in samples.columns else 0
    )
    access_violations = (
        manifest.filter(pl.col("access").cast(pl.Utf8, strict=False) != "open").height
        if "access" in manifest.columns
        else 0
    )
    null_gene_ids = _count_null_or_blank(expr_gtex, "gene_id")
    negative_expr = (
        expr_gtex.filter(pl.col("expression_value").cast(pl.Float64, strict=False) < 0).height
        if "expression_value" in expr_gtex.columns
        else 0
    )

    return [
        CheckResult(
            check_name="silver_projects_null_project_id",
            status="passed" if null_project_ids == 0 else "failed",
            failed_rows=int(null_project_ids),
        ),
        CheckResult(
            check_name="silver_samples_duplicate_sample_id",
            status="passed" if duplicate_sample_ids == 0 else "failed",
            failed_rows=int(duplicate_sample_ids),
        ),
        CheckResult(
            check_name="silver_manifest_access_open_only",
            status="passed" if access_violations == 0 else "failed",
            failed_rows=int(access_violations),
        ),
        CheckResult(
            check_name="silver_expression_gtex_null_gene_id",
            status="passed" if null_gene_ids == 0 else "failed",
            failed_rows=int(null_gene_ids),
        ),
        CheckResult(
            check_name="silver_expression_gtex_non_negative",
            status="passed" if negative_expr == 0 else "failed",
            failed_rows=int(negative_expr),
        ),
    ]
