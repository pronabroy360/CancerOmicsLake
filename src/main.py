from __future__ import annotations

import argparse
import csv
from datetime import UTC, datetime
import json
import os
from pathlib import Path

from src.common.cap_profiles import resolve_cap_profile
from src.common.config import load_config
from src.common.logging import configure_logging, get_logger
from src.common.paths import ensure_base_dirs
from src.common.reporting import inject_report_context, resolve_run_mode
from src.analytics.build_gold_tables import build_gold_cohort_summary
from src.analytics.evidence_confidence import build_evidence_confidence
from src.graph.build_edges import build_graph_edges_table
from src.graph.build_nodes import build_graph_nodes_table
from src.graph.export_graphify import export_graphify_from_gold_graph_tables
from src.graph.export_neo4j import export_neo4j_from_gold_graph_tables
from src.graph.graph_metrics import build_graph_node_metrics
from src.ingestion.gdc_client import LiveGdcRequiredError, query_tcga_metadata_with_audit
from src.ingestion.gdc_manifest_builder import write_manifest
from src.ingestion.tcga_downloader import download_tcga_files
from src.ingestion.gtex_downloader import gtex_metadata_stub
from src.operations.demo_check import run_demo_check, write_demo_check_report
from src.operations.dbt_runner import run_dbt_command
from src.operations.ingestion_traceability import (
    build_ingestion_traceability_report,
    write_ingestion_traceability_report,
)
from src.operations.project_completion import (
    build_project_completion_report,
    write_project_completion_report,
)
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
    run_mode: str = "manual",
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
        inject_report_context(audit_out, {"run_mode": run_mode})
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
    inject_report_context(audit_out, {"run_mode": run_mode})
    logger.info("Wrote GDC ingestion audit: %s", audit_out)

    gtex_rows = gtex_metadata_stub(cfg)
    gtex_norm = normalize_gtex_rows(gtex_rows)
    gtex_expr = with_log2_expression(gtex_norm)
    check_results = [
        check_non_negative_expression(gtex_expr),
        check_gene_mapping_rate(gtex_expr, threshold=cfg.quality.gene_mapping_rate_threshold),
    ]
    run_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    payload = build_quality_payload(run_id, check_results, context={"run_mode": run_mode})
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

    parser_download = subparsers.add_parser("run-download-tcga")
    parser_download.add_argument("--config", required=True)
    parser_download.add_argument("--force-download", action="store_true")
    parser_download.add_argument("--max-downloads", type=int, default=None)
    parser_download.add_argument("--data-subdirs", default=None, help="comma-separated: expression,mutations,clinical,biospecimen,other")
    parser_download.add_argument("--expression-cap-per-project", type=int, default=None)
    parser_download.add_argument("--mutation-cap-per-project", type=int, default=None)
    parser_download.add_argument("--use-medium-cap-profile", action="store_true")
    parser_download.add_argument("--use-aggressive-cap-profile", action="store_true")

    parser_gold = subparsers.add_parser("run-gold")
    parser_gold.add_argument("--config", required=True)

    parser_quality = subparsers.add_parser("run-quality")
    parser_quality.add_argument("--config", required=True)

    parser_graph_export = subparsers.add_parser("run-graph-export")
    parser_graph_export.add_argument("--config", required=True)

    parser_graph_metrics = subparsers.add_parser("run-graph-metrics")
    parser_graph_metrics.add_argument("--config", required=True)

    parser_evidence_confidence = subparsers.add_parser("run-evidence-confidence")
    parser_evidence_confidence.add_argument("--config", required=True)

    parser_dbt_run = subparsers.add_parser("run-dbt")
    parser_dbt_run.add_argument("--config", required=True)
    parser_dbt_run.add_argument("--mode", choices=["auto", "local", "docker"], default="auto")

    parser_dbt_test = subparsers.add_parser("test-dbt")
    parser_dbt_test.add_argument("--config", required=True)
    parser_dbt_test.add_argument("--mode", choices=["auto", "local", "docker"], default="auto")

    parser_traceability = subparsers.add_parser("run-ingestion-traceability")
    parser_traceability.add_argument("--config", required=True)
    parser_traceability.add_argument("--output", default="outputs/reports/ingestion_traceability_report.json")

    parser_demo_check = subparsers.add_parser("run-demo-check")
    parser_demo_check.add_argument("--config", required=True)
    parser_demo_check.add_argument("--strict-no-stub", action="store_true")
    parser_demo_check.add_argument("--output", default="outputs/reports/demo_check_report.json")

    parser_completion = subparsers.add_parser("run-project-completion")
    parser_completion.add_argument("--config", required=True)
    parser_completion.add_argument("--output", default="outputs/reports/project_completion_report.json")

    parser_flow = subparsers.add_parser("run-flow")
    parser_flow.add_argument("--config", required=True)
    parser_flow.add_argument("--require-live-gdc", action="store_true")
    parser_flow.add_argument("--force-download", action="store_true")
    parser_flow.add_argument("--data-subdirs", default=None, help="comma-separated: expression,mutations,clinical,biospecimen,other")
    parser_flow.add_argument("--use-medium-cap-profile", action="store_true")
    parser_flow.add_argument("--use-aggressive-cap-profile", action="store_true")
    parser_flow.add_argument("--expression-cap-per-project", type=int, default=None)
    parser_flow.add_argument("--mutation-cap-per-project", type=int, default=None)

    args = parser.parse_args()
    configure_logging()
    run_mode = resolve_run_mode(os.getenv("RUN_MODE") or os.getenv("GITHUB_EVENT_NAME"))

    if args.command == "validate-config":
        load_config(args.config)
        print("Config validation passed.")
        return
    if args.command == "run-metadata":
        run_metadata_mode(
            args.config,
            require_live_gdc=args.require_live_gdc,
            gdc_base_url_override=args.gdc_base_url,
            run_mode=run_mode,
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
    if args.command == "run-download-tcga":
        cfg = load_config(args.config)
        subdirs = None
        if args.data_subdirs:
            subdirs = {x.strip().lower() for x in args.data_subdirs.split(",") if x.strip()}
        cap_expression = args.expression_cap_per_project
        cap_mutation = args.mutation_cap_per_project
        if args.use_medium_cap_profile:
            cap_expression, cap_mutation = resolve_cap_profile("medium")
        if args.use_aggressive_cap_profile:
            cap_expression, cap_mutation = resolve_cap_profile("aggressive")
        caps = None
        if cap_expression is not None or cap_mutation is not None:
            caps = {
                project_id: {
                    **({"expression": cap_expression} if cap_expression is not None else {}),
                    **({"mutations": cap_mutation} if cap_mutation is not None else {}),
                }
                for project_id in cfg.tcga.projects
            }
        summary = download_tcga_files(
            cfg,
            force_download=args.force_download,
            max_downloads=args.max_downloads,
            allowed_data_subdirs=subdirs,
            project_modality_caps=caps,
            run_mode=run_mode,
        )
        logger = get_logger("canceromicslake")
        logger.info(
            "TCGA download status=%s candidates=%s attempted=%s downloaded=%s skipped=%s failed=%s",
            summary["status"],
            summary["total_candidates"],
            summary["attempted_downloads"],
            summary["downloaded_count"],
            summary["skipped_existing_count"],
            summary["failed_count"],
        )
        print("TCGA file download stage completed.")
        return
    if args.command == "run-gold":
        load_config(args.config)
        summary = build_gold_cohort_summary()
        node_summary = build_graph_nodes_table()
        edge_summary = build_graph_edges_table()
        logger = get_logger("canceromicslake")
        logger.info("Gold cohort summary written to %s", summary["gold_cohort_summary_path"])
        logger.info(
            "Gold summary counts: projects=%s patients=%s samples=%s files=%s gtex_expr_samples=%s mutation_records=%s mutation_gene_rows=%s tumor_vs_normal_rows=%s candidate_priority_rows=%s",
            summary["tcga_project_count"],
            summary["tcga_patient_count"],
            summary["tcga_sample_count"],
            summary["tcga_file_count"],
            summary["gtex_expression_sample_count"],
            summary["mutation_record_count"],
            summary["mutation_gene_rows"],
            summary["tumor_vs_normal_rows"],
            summary["candidate_gene_priority_rows"],
        )
        logger.info("Graph tables: nodes=%s (%s) edges=%s (%s)", node_summary["count"], node_summary["path"], edge_summary["count"], edge_summary["path"])
        print("Gold table build completed.")
        return
    if args.command == "run-quality":
        load_config(args.config)
        results = run_silver_quality_checks()
        run_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        payload = build_quality_payload(run_id, results, context={"run_mode": run_mode})
        output = write_quality_json(payload, "outputs/reports/silver_data_quality_report.json")
        logger = get_logger("canceromicslake")
        logger.info("Silver quality report written to %s", output)
        logger.info("Silver quality status=%s checks=%s", payload["status"], len(results))
        print("Silver quality run completed.")
        return
    if args.command == "run-graph-export":
        load_config(args.config)
        neo4j_summary = export_neo4j_from_gold_graph_tables()
        graphify_summary = export_graphify_from_gold_graph_tables()
        metrics_summary = build_graph_node_metrics()
        confidence_summary = build_evidence_confidence()
        logger = get_logger("canceromicslake")
        logger.info(
            "Neo4j export: nodes=%s edges=%s dir=outputs/graph_exports/neo4j",
            neo4j_summary["nodes_count"],
            neo4j_summary["edges_count"],
        )
        logger.info(
            "Neo4j bulk files: node_files=%s edge_files=%s import_script=%s",
            neo4j_summary.get("bulk_node_file_count", 0),
            neo4j_summary.get("bulk_edge_file_count", 0),
            neo4j_summary.get("import_cypher", ""),
        )
        logger.info(
            "Graphify export: nodes=%s edges=%s dir=outputs/graph_exports/graphify",
            graphify_summary["nodes_count"],
            graphify_summary["edges_count"],
        )
        logger.info(
            "Graph metrics: rows=%s report=%s",
            metrics_summary["metric_rows"],
            metrics_summary["report_path"],
        )
        logger.info(
            "Evidence confidence: rows=%s high_confidence=%s path=%s",
            confidence_summary["row_count"],
            confidence_summary["high_confidence_count"],
            confidence_summary["path"],
        )
        print("Graph export completed.")
        return
    if args.command == "run-graph-metrics":
        load_config(args.config)
        metrics_summary = build_graph_node_metrics()
        confidence_summary = build_evidence_confidence()
        logger = get_logger("canceromicslake")
        logger.info(
            "Graph metrics written: rows=%s report=%s",
            metrics_summary["metric_rows"],
            metrics_summary["report_path"],
        )
        logger.info("Evidence confidence rows=%s", confidence_summary["row_count"])
        print("Graph metrics completed.")
        return
    if args.command == "run-evidence-confidence":
        load_config(args.config)
        confidence_summary = build_evidence_confidence()
        logger = get_logger("canceromicslake")
        logger.info(
            "Evidence confidence written: rows=%s high_confidence=%s path=%s",
            confidence_summary["row_count"],
            confidence_summary["high_confidence_count"],
            confidence_summary["path"],
        )
        print("Evidence confidence build completed.")
        return
    if args.command == "run-dbt":
        load_config(args.config)
        payload = run_dbt_command("run", requested_mode=args.mode)
        logger = get_logger("canceromicslake")
        logger.info("dbt run completed via %s mode.", payload["mode"])
        print("dbt run completed.")
        return
    if args.command == "test-dbt":
        load_config(args.config)
        payload = run_dbt_command("test", requested_mode=args.mode)
        logger = get_logger("canceromicslake")
        logger.info("dbt test completed via %s mode.", payload["mode"])
        print("dbt test completed.")
        return
    if args.command == "run-ingestion-traceability":
        load_config(args.config)
        payload = build_ingestion_traceability_report()
        output = write_ingestion_traceability_report(payload, args.output)
        logger = get_logger("canceromicslake")
        logger.info("Ingestion traceability report written to %s", output)
        logger.info("Ingestion traceability status=%s warnings=%s", payload["status"], len(payload.get("warnings", [])))
        print("Ingestion traceability report generated.")
        return
    if args.command == "run-demo-check":
        load_config(args.config)
        payload = run_demo_check(strict_no_stub=args.strict_no_stub)
        output = write_demo_check_report(payload, args.output)
        logger = get_logger("canceromicslake")
        logger.info("Demo check report written to %s", output)
        logger.info("Demo check status=%s checks=%s failed=%s", payload["status"], payload["check_count"], payload["failed_count"])
        if payload["status"] != "passed":
            raise RuntimeError(f"Demo check failed. See {output}")
        print("Reviewer demo check completed.")
        return
    if args.command == "run-project-completion":
        load_config(args.config)
        payload = build_project_completion_report()
        output = write_project_completion_report(payload, args.output)
        logger = get_logger("canceromicslake")
        logger.info(
            "Project completion report written to %s with %s/%s milestones done.",
            output,
            payload["completed_milestones"],
            payload["total_milestones"],
        )
        print("Project completion report generated.")
        return
    if args.command == "run-flow":
        from src.orchestration.pipeline_flow import run_pipeline_with_fallback

        cap_expression = args.expression_cap_per_project
        cap_mutation = args.mutation_cap_per_project
        subdirs = None
        if args.data_subdirs:
            subdirs = {x.strip().lower() for x in args.data_subdirs.split(",") if x.strip()}
        if args.use_medium_cap_profile:
            cap_expression, cap_mutation = resolve_cap_profile("medium")
        if args.use_aggressive_cap_profile:
            cap_expression, cap_mutation = resolve_cap_profile("aggressive")

        result = run_pipeline_with_fallback(
            config_path=args.config,
            require_live_gdc=args.require_live_gdc,
            run_mode=run_mode,
            force_download=args.force_download,
            allowed_data_subdirs=subdirs,
            expression_cap_per_project=cap_expression,
            mutation_cap_per_project=cap_mutation,
        )
        logger = get_logger("canceromicslake")
        logger.info("Pipeline flow completed: run_id=%s status=%s", result["pipeline_run_id"], result["status"])
        print("Pipeline flow completed.")
        return


if __name__ == "__main__":
    main()
