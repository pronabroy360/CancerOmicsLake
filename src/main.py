from __future__ import annotations

import argparse
import csv
from datetime import UTC, datetime
import json
from pathlib import Path

from src.common.config import load_config
from src.common.logging import configure_logging, get_logger
from src.common.paths import ensure_base_dirs
from src.analytics.build_gold_tables import build_gold_cohort_summary
from src.ingestion.gdc_client import LiveGdcRequiredError, query_tcga_metadata_with_audit
from src.ingestion.gdc_manifest_builder import write_manifest
from src.ingestion.gtex_downloader import gtex_metadata_stub
from src.processing.build_expression_table import with_log2_expression
from src.processing.build_silver_tables import build_silver_tables_from_bronze
from src.processing.normalize_gtex_expression import normalize_gtex_rows
from src.quality.checks import (
    build_quality_payload,
    check_gene_mapping_rate,
    check_non_negative_expression,
    run_silver_quality_checks,
)
from src.quality.generate_quality_report import write_quality_json


def write_tcga_metadata_csv(rows: list[dict[str, str]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        output_path.write_text("", encoding="utf-8")
        return
    with output_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def run_metadata_mode(
    config_path: str,
    require_live_gdc: bool = False,
    gdc_base_url_override: str | None = None,
) -> None:
    logger = get_logger("canceromicslake")
    ensure_base_dirs()
    cfg = load_config(config_path)
    if require_live_gdc:
        cfg.tcga.require_live_gdc = True
    if gdc_base_url_override:
        cfg.gdc_api.base_url = gdc_base_url_override

    try:
        tcga_records, source_mode, audit = query_tcga_metadata_with_audit(cfg)
    except LiveGdcRequiredError as exc:
        audit_out = Path(cfg.gdc_api.audit_output_path)
        audit_out.parent.mkdir(parents=True, exist_ok=True)
        audit_out.write_text(json.dumps(exc.audit, indent=2), encoding="utf-8")
        logger.error("Live GDC required run failed. Audit written: %s", audit_out)
        raise
    if source_mode == "stub":
        logger.warning(
            "Using stub TCGA metadata source. Live GDC API query may be unavailable in this environment."
        )
    tcga_rows = [
        {
            "project_id": r.project_id,
            "case_id": r.case_id,
            "submitter_id": r.submitter_id,
            "sample_id": r.sample_id,
            "sample_type": r.sample_type,
            "primary_site": r.primary_site,
            "disease_type": r.disease_type,
            "file_id": r.file_id,
            "file_name": r.file_name,
            "data_category": r.data_category,
            "data_type": r.data_type,
            "experimental_strategy": r.experimental_strategy,
            "workflow_type": r.workflow_type,
            "access": r.access,
            "file_size": str(r.file_size),
            "md5sum": r.md5sum,
        }
        for r in tcga_records
    ]

    metadata_out = Path(f"data/bronze/tcga/metadata/tcga_metadata_{source_mode}.csv")
    write_tcga_metadata_csv(tcga_rows, metadata_out)
    logger.info("Wrote TCGA metadata rows: %s (source=%s)", len(tcga_rows), source_mode)

    manifest_out = Path(f"data/bronze/tcga/metadata/gdc_manifest_{source_mode}.tsv")
    write_manifest(tcga_records, manifest_out)
    logger.info("Wrote GDC manifest: %s", manifest_out)

    audit_out = Path(cfg.gdc_api.audit_output_path)
    audit_out.parent.mkdir(parents=True, exist_ok=True)
    audit_out.write_text(json.dumps(audit, indent=2), encoding="utf-8")
    logger.info("Wrote GDC ingestion audit: %s", audit_out)

    gtex_rows = gtex_metadata_stub(cfg)
    gtex_norm = normalize_gtex_rows(gtex_rows)
    gtex_expr = with_log2_expression(gtex_norm)
    check_results = [
        check_non_negative_expression(gtex_expr),
        check_gene_mapping_rate(gtex_expr, threshold=cfg.quality.gene_mapping_rate_threshold),
    ]
    run_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    payload = build_quality_payload(run_id, check_results)
    write_quality_json(payload, "outputs/reports/data_quality_report.json")
    logger.info("Wrote quality report for run: %s", run_id)


def main() -> None:
    parser = argparse.ArgumentParser(description="CancerOmicsLake CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    parser_validate = subparsers.add_parser("validate-config")
    parser_validate.add_argument("--config", required=True)

    parser_metadata = subparsers.add_parser("run-metadata")
    parser_metadata.add_argument("--config", required=True)
    parser_metadata.add_argument("--require-live-gdc", action="store_true")
    parser_metadata.add_argument("--gdc-base-url", default=None)

    parser_silver = subparsers.add_parser("run-silver")
    parser_silver.add_argument("--config", required=True)

    parser_gold = subparsers.add_parser("run-gold")
    parser_gold.add_argument("--config", required=True)

    parser_quality = subparsers.add_parser("run-quality")
    parser_quality.add_argument("--config", required=True)

    args = parser.parse_args()
    configure_logging()

    if args.command == "validate-config":
        load_config(args.config)
        print("Config validation passed.")
        return
    if args.command == "run-metadata":
        run_metadata_mode(
            args.config,
            require_live_gdc=args.require_live_gdc,
            gdc_base_url_override=args.gdc_base_url,
        )
        print("Metadata-only pipeline run completed.")
        return
    if args.command == "run-silver":
        cfg = load_config(args.config)
        summary = build_silver_tables_from_bronze(config=cfg)
        logger = get_logger("canceromicslake")
        logger.info("Silver tables built from %s", summary["source_metadata_file"])
        logger.info(
            "Silver counts: projects=%s patients=%s samples=%s files=%s tcga_expr=%s gtex_expr=%s mutations=%s",
            summary["projects_count"],
            summary["patients_count"],
            summary["samples_count"],
            summary["file_manifest_count"],
            summary["expression_tcga_count"],
            summary["expression_gtex_count"],
            summary["mutations_count"],
        )
        print("Silver table build completed.")
        return
    if args.command == "run-gold":
        load_config(args.config)
        summary = build_gold_cohort_summary()
        logger = get_logger("canceromicslake")
        logger.info("Gold cohort summary written to %s", summary["gold_cohort_summary_path"])
        logger.info(
            "Gold summary counts: projects=%s patients=%s samples=%s files=%s gtex_expr_samples=%s mutation_records=%s mutation_gene_rows=%s",
            summary["tcga_project_count"],
            summary["tcga_patient_count"],
            summary["tcga_sample_count"],
            summary["tcga_file_count"],
            summary["gtex_expression_sample_count"],
            summary["mutation_record_count"],
            summary["mutation_gene_rows"],
        )
        print("Gold table build completed.")
        return
    if args.command == "run-quality":
        load_config(args.config)
        results = run_silver_quality_checks()
        run_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        payload = build_quality_payload(run_id, results)
        output = write_quality_json(payload, "outputs/reports/silver_data_quality_report.json")
        logger = get_logger("canceromicslake")
        logger.info("Silver quality report written to %s", output)
        logger.info("Silver quality status=%s checks=%s", payload["status"], len(results))
        print("Silver quality run completed.")
        return


if __name__ == "__main__":
    main()
