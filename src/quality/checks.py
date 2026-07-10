from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime
import json
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


def build_quality_payload(run_id: str, results: list[CheckResult], context: dict[str, object] | None = None) -> dict[str, object]:
    statuses = {result.status for result in results}
    status = "passed"
    if "failed" in statuses:
        status = "failed"
    elif "warning" in statuses:
        status = "passed_with_warnings"
    payload: dict[str, object] = {
        "pipeline_run_id": run_id,
        "generated_at": datetime.now(UTC).isoformat(),
        "status": status,
        "checks": [result.to_dict() for result in results],
    }
    if context:
        payload.update(context)
    return payload


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


def _count_invalid_int(df: pl.DataFrame, col: str) -> int:
    if col not in df.columns:
        return 0
    return (
        df.select(pl.col(col).cast(pl.Int64, strict=False).is_null().sum().cast(pl.Int64).alias("cnt")).item(0, 0) or 0
    )


def _count_invalid_expression_unit(df: pl.DataFrame, col: str, allowed: set[str]) -> int:
    if col not in df.columns:
        return 0
    allowed_upper = {v.upper() for v in allowed}
    return (
        df.select(
            (~pl.col(col).cast(pl.Utf8, strict=False).str.to_uppercase().is_in(list(allowed_upper)))
            .sum()
            .cast(pl.Int64)
            .alias("cnt")
        ).item(0, 0)
        or 0
    )


def _count_tcga_workflow_unit_mismatch(df: pl.DataFrame) -> int:
    required = {"pipeline_workflow", "expression_unit"}
    if df.is_empty() or not required.issubset(set(df.columns)):
        return 0
    return (
        df.with_columns(
            [
                pl.col("pipeline_workflow").cast(pl.Utf8, strict=False).fill_null("").str.to_lowercase().alias("wf"),
                pl.col("expression_unit").cast(pl.Utf8, strict=False).fill_null("").str.to_uppercase().alias("unit"),
            ]
        )
        .filter(
            (
                pl.col("wf").str.contains("htseq - counts") | pl.col("wf").str.contains("htseq_counts")
            )
            & (pl.col("unit") != "COUNT")
            | (
                pl.col("wf").str.contains("fpkm")
                & ~pl.col("unit").is_in(["FPKM"])
            )
        )
        .height
    )


def _missing_columns(df: pl.DataFrame, required: list[str]) -> int:
    return len([c for c in required if c not in df.columns])


def _detect_live_mode(download_report_path: Path) -> bool:
    if not download_report_path.exists():
        return False
    try:
        payload = json.loads(download_report_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return False
    source_metadata_file = str(payload.get("source_metadata_file", ""))
    return "_live" in Path(source_metadata_file).name


def _infer_data_subdir(data_category: str) -> str:
    category = data_category.lower()
    if "transcriptome profiling" in category:
        return "expression"
    if "simple nucleotide variation" in category:
        return "mutations"
    if "clinical" in category:
        return "clinical"
    if "biospecimen" in category:
        return "biospecimen"
    return "other"


def _md5_file(path: Path) -> str:
    import hashlib

    hasher = hashlib.md5()
    with path.open("rb") as f:
        while True:
            chunk = f.read(8192)
            if not chunk:
                break
            hasher.update(chunk)
    return hasher.hexdigest()


def _download_integrity_counts(
    manifest: pl.DataFrame,
    bronze_tcga_root: Path,
    download_report_path: Path,
) -> tuple[int, int, bool, bool]:
    # Return (missing_file_count, checksum_mismatch_count, applicable, partial_mode)
    if not download_report_path.exists():
        return 0, 0, False, False

    payload = json.loads(download_report_path.read_text(encoding="utf-8"))
    status = str(payload.get("status", ""))
    if status == "skipped_metadata_only":
        return 0, 0, False, False

    required_cols = {"project_id", "file_name", "data_category", "access", "md5sum"}
    if manifest.is_empty() or not required_cols.issubset(set(manifest.columns)):
        return 0, 0, False, False

    max_downloads = payload.get("max_downloads")
    total_candidates = int(payload.get("total_candidates", 0) or 0)
    selected_candidates = int(payload.get("selected_candidates", total_candidates) or 0)
    attempted_downloads = int(payload.get("attempted_downloads", 0) or 0)
    cap_applied = bool(payload.get("cap_applied", False))
    partial_mode = bool(
        status == "completed_with_failures"
        or
        (max_downloads is not None and attempted_downloads < total_candidates)
        or cap_applied
        or selected_candidates < total_candidates
    )
    allowed_data_subdirs_raw = payload.get("allowed_data_subdirs", [])
    allowed_data_subdirs = {
        str(x).strip().lower()
        for x in allowed_data_subdirs_raw
        if isinstance(x, str) and str(x).strip()
    }
    selected_files_raw = payload.get("selected_files", [])
    selected_file_keys: set[tuple[str, str, str]] = set()
    if isinstance(selected_files_raw, list):
        for item in selected_files_raw:
            if not isinstance(item, dict):
                continue
            project_id = str(item.get("project_id", "")).strip()
            file_name = str(item.get("file_name", "")).strip()
            data_subdir = str(item.get("data_subdir", "")).strip().lower()
            if project_id and file_name and data_subdir:
                selected_file_keys.add((project_id, data_subdir, file_name))

    missing = 0
    checksum_mismatch = 0
    rows = manifest.iter_rows(named=True)
    for row in rows:
        if str(row.get("access", "")).lower() != "open":
            continue
        project_id = str(row.get("project_id", "")).strip()
        file_name = str(row.get("file_name", "")).strip()
        data_category = str(row.get("data_category", ""))
        md5sum = str(row.get("md5sum", "")).strip()
        if not project_id or not file_name:
            continue

        data_subdir = _infer_data_subdir(data_category)
        if allowed_data_subdirs and data_subdir not in allowed_data_subdirs:
            continue
        if selected_file_keys and (project_id, data_subdir, file_name) not in selected_file_keys:
            continue
        path = bronze_tcga_root / project_id / data_subdir / file_name
        if not path.exists():
            missing += 1
            continue
        if md5sum:
            observed = _md5_file(path)
            if observed != md5sum:
                checksum_mismatch += 1

    return missing, checksum_mismatch, True, partial_mode


def run_silver_quality_checks(
    silver_dir: str | Path = "data/silver",
    bronze_tcga_root: str | Path = "data/bronze/tcga",
    download_report_path: str | Path = "outputs/reports/tcga_download_report.json",
    gold_dir: str | Path = "data/gold",
) -> list[CheckResult]:
    root = Path(silver_dir)
    gold_root = Path(gold_dir)

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
    expr_tcga = _read_or_empty(
        root / "silver_expression_tcga.parquet",
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
    mutations = _read_or_empty(
        root / "silver_mutations.parquet",
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
    gold_mut_gene = _read_or_empty(
        gold_root / "gold_mutation_frequency_by_gene.parquet",
        {
            "gene_symbol": pl.Utf8,
            "cancer_type": pl.Utf8,
            "mutated_sample_count": pl.Int64,
            "total_profiled_sample_count": pl.Int64,
            "mutation_frequency": pl.Float64,
            "top_variant_classification": pl.Utf8,
        },
    )
    gold_graph_nodes = _read_or_empty(
        gold_root / "gold_graph_nodes.parquet",
        {"node_id": pl.Utf8, "node_label": pl.Utf8, "name": pl.Utf8, "primary_site": pl.Utf8, "source": pl.Utf8},
    )
    gold_graph_edges = _read_or_empty(
        gold_root / "gold_graph_edges.parquet",
        {
            "edge_id": pl.Utf8,
            "source_node_id": pl.Utf8,
            "target_node_id": pl.Utf8,
            "edge_type": pl.Utf8,
            "weight": pl.Float64,
            "evidence_source": pl.Utf8,
        },
    )

    null_project_ids = _count_null_or_blank(projects, "project_id")
    duplicate_sample_ids = (
        samples
        .filter(
            pl.col("sample_id").cast(pl.Utf8, strict=False).is_not_null()
            & (pl.col("sample_id").cast(pl.Utf8, strict=False).str.strip_chars() != "")
            & (pl.col("sample_id").cast(pl.Utf8, strict=False).str.to_lowercase() != "unknown")
        )
        .group_by("sample_id")
        .len()
        .filter(pl.col("len") > 1)
        .height
        if "sample_id" in samples.columns
        else 0
    )
    patients = _read_or_empty(
        root / "silver_patients.parquet",
        {"project_id": pl.Utf8, "case_id": pl.Utf8, "submitter_id": pl.Utf8},
    )
    missing_patient_fk = (
        samples.join(
            patients.select(["project_id", "case_id"]).unique(),
            on=["project_id", "case_id"],
            how="anti",
        ).height
        if {"project_id", "case_id"}.issubset(set(samples.columns))
        else 0
    )
    access_violations = (
        manifest.filter(pl.col("access").cast(pl.Utf8, strict=False) != "open").height
        if "access" in manifest.columns
        else 0
    )
    missing_manifest_md5 = _count_null_or_blank(manifest, "md5sum")
    null_gene_ids = _count_null_or_blank(expr_gtex, "gene_id")
    negative_expr = (
        expr_gtex.filter(pl.col("expression_value").cast(pl.Float64, strict=False) < 0).height
        if "expression_value" in expr_gtex.columns
        else 0
    )
    null_gene_ids_tcga = _count_null_or_blank(expr_tcga, "gene_id")
    negative_expr_tcga = (
        expr_tcga.filter(pl.col("expression_value").cast(pl.Float64, strict=False) < 0).height
        if "expression_value" in expr_tcga.columns
        else 0
    )
    null_mut_gene = _count_null_or_blank(mutations, "gene_symbol")
    invalid_mut_start = _count_invalid_int(mutations, "start_position")
    invalid_mut_end = _count_invalid_int(mutations, "end_position")
    invalid_tcga_units = _count_invalid_expression_unit(expr_tcga, "expression_unit", {"TPM", "FPKM", "COUNT"})
    tcga_workflow_unit_mismatch = _count_tcga_workflow_unit_mismatch(expr_tcga)
    invalid_gtex_units = _count_invalid_expression_unit(expr_gtex, "expression_unit", {"TPM"})
    gtex_stub_rows = (
        expr_gtex.filter(
            pl.col("data_origin")
            .cast(pl.Utf8, strict=False)
            .fill_null("")
            .str.to_lowercase()
            .str.contains("stub|placeholder|demo")
        ).height
        if "data_origin" in expr_gtex.columns
        else expr_gtex.height
    )
    gtex_min_tissue_samples = (
        int(
            expr_gtex.group_by("tissue_site")
            .agg(pl.col("gtex_sample_id").n_unique().alias("sample_count"))
            .get_column("sample_count")
            .min()
            or 0
        )
        if not expr_gtex.is_empty() and {"tissue_site", "gtex_sample_id"}.issubset(expr_gtex.columns)
        else 0
    )
    missing_downloaded_files, checksum_mismatches, download_check_applicable, download_partial_mode = _download_integrity_counts(
        manifest=manifest,
        bronze_tcga_root=Path(bronze_tcga_root),
        download_report_path=Path(download_report_path),
    )
    missing_projects_cols = _missing_columns(projects, ["project_id", "primary_site", "disease_type"])
    missing_samples_cols = _missing_columns(samples, ["project_id", "case_id", "sample_id", "sample_type"])
    missing_expr_tcga_cols = _missing_columns(
        expr_tcga,
        ["project_id", "case_id", "sample_id", "gene_id", "gene_symbol", "expression_value", "expression_unit"],
    )
    missing_mut_cols = _missing_columns(
        mutations,
        ["project_id", "case_id", "sample_id", "gene_symbol", "variant_classification", "start_position", "end_position"],
    )
    missing_gold_mut_cols = _missing_columns(
        gold_mut_gene,
        ["gene_symbol", "cancer_type", "mutated_sample_count", "mutation_frequency"],
    )
    missing_gold_graph_node_cols = _missing_columns(gold_graph_nodes, ["node_id", "node_label", "name"])
    missing_gold_graph_edge_cols = _missing_columns(
        gold_graph_edges,
        ["edge_id", "source_node_id", "target_node_id", "edge_type"],
    )
    samples_missing_project_fk = (
        samples.join(projects.select(["project_id"]).unique(), on=["project_id"], how="anti").height
        if ("project_id" in samples.columns and "project_id" in projects.columns)
        else 0
    )
    mutation_missing_case_fk = (
        mutations.filter(
            pl.col("case_id").cast(pl.Utf8, strict=False).is_not_null()
            & (pl.col("case_id").cast(pl.Utf8, strict=False).str.strip_chars() != "")
            & (pl.col("case_id").cast(pl.Utf8, strict=False).str.to_lowercase() != "unknown")
        )
        .join(
            patients.select(["project_id", "case_id"]).unique(),
            on=["project_id", "case_id"],
            how="anti",
        )
        .height
        if {"project_id", "case_id"}.issubset(set(mutations.columns))
        else 0
    )
    if not gold_graph_edges.is_empty():
        if gold_graph_nodes.is_empty() or "node_id" not in gold_graph_nodes.columns:
            graph_edges_missing_nodes = gold_graph_edges.height
        else:
            node_ids = gold_graph_nodes.get_column("node_id").to_list()
            graph_edges_missing_nodes = gold_graph_edges.filter(
                ~pl.col("source_node_id").is_in(node_ids)
                | ~pl.col("target_node_id").is_in(node_ids)
            ).height
    else:
        graph_edges_missing_nodes = 0
    live_mode_detected = _detect_live_mode(Path(download_report_path))
    expected_non_zero_failure = 0
    if live_mode_detected:
        if expr_tcga.height == 0:
            expected_non_zero_failure += 1
        if mutations.height == 0:
            expected_non_zero_failure += 1
        if gold_mut_gene.height == 0:
            expected_non_zero_failure += 1

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
            check_name="silver_samples_patient_fk_integrity",
            status="passed" if missing_patient_fk == 0 else "failed",
            failed_rows=int(missing_patient_fk),
        ),
        CheckResult(
            check_name="silver_manifest_access_open_only",
            status="passed" if access_violations == 0 else "failed",
            failed_rows=int(access_violations),
        ),
        CheckResult(
            check_name="silver_manifest_md5_present",
            status="passed" if missing_manifest_md5 == 0 else "failed",
            failed_rows=int(missing_manifest_md5),
        ),
        CheckResult(
            check_name="silver_projects_schema_columns_present",
            status="passed" if missing_projects_cols == 0 else "failed",
            failed_rows=int(missing_projects_cols),
        ),
        CheckResult(
            check_name="silver_samples_schema_columns_present",
            status="passed" if missing_samples_cols == 0 else "failed",
            failed_rows=int(missing_samples_cols),
        ),
        CheckResult(
            check_name="silver_expression_tcga_schema_columns_present",
            status="passed" if missing_expr_tcga_cols == 0 else "failed",
            failed_rows=int(missing_expr_tcga_cols),
        ),
        CheckResult(
            check_name="silver_mutations_schema_columns_present",
            status="passed" if missing_mut_cols == 0 else "failed",
            failed_rows=int(missing_mut_cols),
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
        CheckResult(
            check_name="silver_expression_tcga_null_gene_id",
            status="passed" if null_gene_ids_tcga == 0 else "failed",
            failed_rows=int(null_gene_ids_tcga),
        ),
        CheckResult(
            check_name="silver_expression_tcga_non_negative",
            status="passed" if negative_expr_tcga == 0 else "failed",
            failed_rows=int(negative_expr_tcga),
        ),
        CheckResult(
            check_name="silver_expression_tcga_unit_supported",
            status="passed" if invalid_tcga_units == 0 else "failed",
            failed_rows=int(invalid_tcga_units),
        ),
        CheckResult(
            check_name="silver_expression_tcga_workflow_unit_compatibility",
            status="passed" if tcga_workflow_unit_mismatch == 0 else "warning",
            failed_rows=int(tcga_workflow_unit_mismatch),
        ),
        CheckResult(
            check_name="silver_expression_gtex_unit_supported",
            status="passed" if invalid_gtex_units == 0 else "failed",
            failed_rows=int(invalid_gtex_units),
        ),
        CheckResult(
            check_name="silver_expression_gtex_public_provenance",
            status="passed" if gtex_stub_rows == 0 else "warning",
            failed_rows=int(gtex_stub_rows),
        ),
        CheckResult(
            check_name="silver_expression_gtex_min_tissue_sample_support",
            status="passed" if gtex_min_tissue_samples >= 30 else "warning",
            failed_rows=0 if gtex_min_tissue_samples >= 30 else 30 - gtex_min_tissue_samples,
            metric_name="minimum_unique_samples_per_tissue",
            metric_value=float(gtex_min_tissue_samples),
            threshold=30.0,
        ),
        CheckResult(
            check_name="silver_mutations_null_gene_symbol",
            status="passed" if null_mut_gene == 0 else "failed",
            failed_rows=int(null_mut_gene),
        ),
        CheckResult(
            check_name="silver_mutations_start_position_valid_integer",
            status="passed" if invalid_mut_start == 0 else "failed",
            failed_rows=int(invalid_mut_start),
        ),
        CheckResult(
            check_name="silver_mutations_end_position_valid_integer",
            status="passed" if invalid_mut_end == 0 else "failed",
            failed_rows=int(invalid_mut_end),
        ),
        CheckResult(
            check_name="silver_samples_project_fk_integrity",
            status="passed" if samples_missing_project_fk == 0 else "failed",
            failed_rows=int(samples_missing_project_fk),
        ),
        CheckResult(
            check_name="silver_mutations_case_fk_integrity",
            status="passed" if mutation_missing_case_fk == 0 else "warning",
            failed_rows=int(mutation_missing_case_fk),
        ),
        CheckResult(
            check_name="gold_mutation_frequency_schema_columns_present",
            status="passed" if (gold_mut_gene.is_empty() or missing_gold_mut_cols == 0) else "failed",
            failed_rows=int(missing_gold_mut_cols),
        ),
        CheckResult(
            check_name="gold_graph_nodes_schema_columns_present",
            status="passed" if (gold_graph_nodes.is_empty() or missing_gold_graph_node_cols == 0) else "failed",
            failed_rows=int(missing_gold_graph_node_cols),
        ),
        CheckResult(
            check_name="gold_graph_edges_schema_columns_present",
            status="passed" if (gold_graph_edges.is_empty() or missing_gold_graph_edge_cols == 0) else "failed",
            failed_rows=int(missing_gold_graph_edge_cols),
        ),
        CheckResult(
            check_name="gold_graph_edges_node_fk_integrity",
            status="passed" if graph_edges_missing_nodes == 0 else "failed",
            failed_rows=int(graph_edges_missing_nodes),
        ),
        CheckResult(
            check_name="live_mode_non_zero_row_sanity",
            status="passed" if expected_non_zero_failure == 0 else "failed",
            failed_rows=int(expected_non_zero_failure),
        ),
        CheckResult(
            check_name="bronze_tcga_download_file_presence",
            status=(
                "passed"
                if (not download_check_applicable or missing_downloaded_files == 0)
                else ("warning" if download_partial_mode else "failed")
            ),
            failed_rows=int(missing_downloaded_files),
        ),
        CheckResult(
            check_name="bronze_tcga_download_checksum_match",
            status=(
                "passed"
                if (not download_check_applicable or checksum_mismatches == 0)
                else ("warning" if download_partial_mode else "failed")
            ),
            failed_rows=int(checksum_mismatches),
        ),
    ]
