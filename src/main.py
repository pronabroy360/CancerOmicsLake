from __future__ import annotations

import argparse
import csv
from datetime import UTC, datetime
from pathlib import Path

from src.common.config import load_config
from src.common.logging import configure_logging, get_logger
from src.common.paths import ensure_base_dirs
from src.ingestion.gdc_client import query_tcga_metadata_stub
from src.ingestion.gdc_manifest_builder import write_manifest
from src.ingestion.gtex_downloader import gtex_metadata_stub
from src.processing.build_expression_table import with_log2_expression
from src.processing.normalize_gtex_expression import normalize_gtex_rows
from src.quality.checks import (
    build_quality_payload,
    check_gene_mapping_rate,
    check_non_negative_expression,
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


def run_metadata_mode(config_path: str) -> None:
    logger = get_logger("canceromicslake")
    ensure_base_dirs()
    cfg = load_config(config_path)

    tcga_records = query_tcga_metadata_stub(cfg)
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

    metadata_out = Path("data/bronze/tcga/metadata/tcga_metadata_stub.csv")
    write_tcga_metadata_csv(tcga_rows, metadata_out)
    logger.info("Wrote TCGA metadata stub rows: %s", len(tcga_rows))

    manifest_out = Path("data/bronze/tcga/metadata/gdc_manifest_stub.tsv")
    write_manifest(tcga_records, manifest_out)
    logger.info("Wrote GDC manifest stub: %s", manifest_out)

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

    args = parser.parse_args()
    configure_logging()

    if args.command == "validate-config":
        load_config(args.config)
        print("Config validation passed.")
        return
    if args.command == "run-metadata":
        run_metadata_mode(args.config)
        print("Metadata-only pipeline run completed.")
        return


if __name__ == "__main__":
    main()
