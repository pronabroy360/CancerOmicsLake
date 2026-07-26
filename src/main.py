from __future__ import annotations

import argparse
import csv
from datetime import UTC, datetime
import json
import os
from pathlib import Path

import polars as pl

from src.common.cap_profiles import resolve_cap_profile
from src.common.config import load_config
from src.common.logging import configure_logging, get_logger
from src.common.paths import ensure_base_dirs
from src.common.reporting import inject_report_context, resolve_run_mode
from src.analytics.build_gold_tables import build_gold_cohort_summary
from src.analytics.bootstrap_stability import build_bootstrap_stability
from src.analytics.consensus_candidates import build_consensus_candidates
from src.analytics.evidence_confidence import build_evidence_confidence
from src.analytics.external_validation import build_external_expression_validation
from src.analytics.expression_statistics import build_expression_statistical_support
from src.analytics.paired_expression import build_paired_expression_support
from src.analytics.pathway_enrichment import build_pathway_enrichment
from src.analytics.reference_ablation import build_reference_ablation_evaluation
from src.graph.build_edges import build_graph_edges_table
from src.graph.build_nodes import build_graph_nodes_table
from src.graph.export_graphify import export_graphify_from_gold_graph_tables
from src.graph.export_neo4j import export_neo4j_from_gold_graph_tables
from src.graph.graph_metrics import build_graph_node_metrics
from src.ingestion.gdc_client import LiveGdcRequiredError, query_tcga_metadata_with_audit
from src.ingestion.gdc_manifest_builder import write_manifest
from src.ingestion.tcga_downloader import download_tcga_files
from src.ingestion.gtex_downloader import download_gtex_files, gtex_metadata_stub
from src.ingestion.recount3_expression import build_recount3_expression_extract
from src.operations.demo_check import run_demo_check, write_demo_check_report
from src.operations.dbt_runner import run_dbt_command
from src.operations.ingestion_traceability import (
    build_ingestion_traceability_report,
    write_ingestion_traceability_report,
)
from src.operations.manuscript_package import build_manuscript_package
from src.operations.project_completion import (
    build_project_completion_report,
    write_project_completion_report,
)
from src.operations.research_benchmark import run_research_benchmark
from src.operations.fair_release import build_fair_release
from src.processing.build_expression_table import with_log2_expression
from src.processing.gtex_harmonizer import harmonize_gtex_gct_files
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

    parser_gtex = subparsers.add_parser("run-gtex")
    parser_gtex.add_argument("--config", required=True)
    parser_gtex.add_argument("--force-download", action="store_true")
    parser_gtex.add_argument("--sample-cap-per-tissue", type=int, default=None)

    parser_download = subparsers.add_parser("run-download-tcga")
    parser_download.add_argument("--config", required=True)
    parser_download.add_argument("--force-download", action="store_true")
    parser_download.add_argument("--max-downloads", type=int, default=None)
    parser_download.add_argument("--data-subdirs", default=None, help="comma-separated: expression,mutations,clinical,biospecimen,other")
    parser_download.add_argument("--expression-cap-per-project", type=int, default=None)
    parser_download.add_argument("--mutation-cap-per-project", type=int, default=None)
    parser_download.add_argument("--normal-expression-cap-per-project", type=int, default=None)
    parser_download.add_argument("--use-medium-cap-profile", action="store_true")
    parser_download.add_argument("--use-aggressive-cap-profile", action="store_true")
    parser_download.add_argument("--download-workers", type=int, default=1)
    parser_download.add_argument("--pair-tumors-to-downloaded-normals", action="store_true")

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

    parser_bootstrap = subparsers.add_parser("run-bootstrap-stability")
    parser_bootstrap.add_argument("--config", required=True)
    parser_bootstrap.add_argument("--candidates-per-cancer", type=int, default=500)
    parser_bootstrap.add_argument("--iterations", type=int, default=200)
    parser_bootstrap.add_argument("--top-k", type=int, default=50)
    parser_bootstrap.add_argument("--random-seed", type=int, default=20260710)

    parser_external_validation = subparsers.add_parser("run-external-validation")
    parser_external_validation.add_argument("--config", required=True)
    parser_external_validation.add_argument("--recount3-expression-path", default="data/silver/silver_expression_recount3.parquet")
    parser_external_validation.add_argument("--top-k", type=int, default=100)

    parser_consensus = subparsers.add_parser("run-consensus-candidates")
    parser_consensus.add_argument("--config", required=True)

    parser_reference_ablation = subparsers.add_parser("run-reference-ablation")
    parser_reference_ablation.add_argument("--config", required=True)
    parser_reference_ablation.add_argument(
        "--top-k-values", default="25,50,100,250"
    )

    parser_expression_statistics = subparsers.add_parser("run-expression-statistics")
    parser_expression_statistics.add_argument("--config", required=True)

    parser_paired_expression = subparsers.add_parser("run-paired-expression")
    parser_paired_expression.add_argument("--config", required=True)

    parser_pathway = subparsers.add_parser("run-pathway-enrichment")
    parser_pathway.add_argument("--config", required=True)
    parser_pathway.add_argument("--pathway-gmt", default="data/bronze/reference/pathways/reactome_pathways.gmt")
    parser_pathway.add_argument("--pathway-source", default="Reactome")
    parser_pathway.add_argument("--min-overlap", type=int, default=2)

    parser_recount3 = subparsers.add_parser("run-recount3-expression")
    parser_recount3.add_argument("--config", required=True)
    parser_recount3.add_argument("--sample-cap-per-cohort", type=int, default=30)
    parser_recount3.add_argument(
        "--output", default="data/silver/silver_expression_recount3.parquet"
    )

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

    parser_benchmark = subparsers.add_parser("run-research-benchmark")
    parser_benchmark.add_argument("--config", required=True)
    parser_benchmark.add_argument("--gold-dir", default="data/gold")
    parser_benchmark.add_argument("--output", default="outputs/reports/research_benchmark_report.json")
    parser_benchmark.add_argument("--repeats", type=int, default=7)
    parser_benchmark.add_argument("--warmups", type=int, default=2)
    parser_benchmark.add_argument("--threads", type=int, default=4)

    parser_release = subparsers.add_parser("build-fair-release")
    parser_release.add_argument("--config", required=True)
    parser_release.add_argument("--version", required=True)
    parser_release.add_argument("--gold-dir", default="data/gold")
    parser_release.add_argument("--output-root", default="outputs/releases")
    parser_release.add_argument("--creator", default="Pronab Chandra Roy")

    parser_manuscript = subparsers.add_parser("build-manuscript-package")
    parser_manuscript.add_argument("--config", required=True)
    parser_manuscript.add_argument("--output-dir", default="manuscript")
    parser_manuscript.add_argument(
        "--fair-manifest", default="outputs/releases/v0.1.0/manifest.json"
    )

    parser_flow = subparsers.add_parser("run-flow")
    parser_flow.add_argument("--config", required=True)
    parser_flow.add_argument("--require-live-gdc", action="store_true")
    parser_flow.add_argument("--force-download", action="store_true")
    parser_flow.add_argument("--data-subdirs", default=None, help="comma-separated: expression,mutations,clinical,biospecimen,other")
    parser_flow.add_argument("--use-medium-cap-profile", action="store_true")
    parser_flow.add_argument("--use-aggressive-cap-profile", action="store_true")
    parser_flow.add_argument("--expression-cap-per-project", type=int, default=None)
    parser_flow.add_argument("--mutation-cap-per-project", type=int, default=None)
    parser_flow.add_argument("--download-workers", type=int, default=1)

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
    if args.command == "run-gtex":
        cfg = load_config(args.config)
        download_summary = download_gtex_files(
            config=cfg,
            force_download=args.force_download,
            run_mode=run_mode,
        )
        if download_summary["status"] == "skipped_metadata_only":
            print("GTEx download skipped because metadata-only mode is enabled.")
            return
        if int(download_summary["failed_count"]) > 0:
            raise RuntimeError(f"GTEx download failed for {download_summary['failed_count']} files")
        harmonization = harmonize_gtex_gct_files(
            config=cfg,
            sample_cap_per_tissue=args.sample_cap_per_tissue,
        )
        logger = get_logger("canceromicslake")
        logger.info(
            "GTEx harmonized: tissues=%s samples=%s rows=%s output_bytes=%s",
            harmonization["tissue_count"],
            harmonization["selected_sample_count"],
            harmonization["total_rows"],
            harmonization["output_bytes"],
        )
        print("GTEx download and harmonization completed.")
        return
    if args.command == "run-download-tcga":
        cfg = load_config(args.config)
        subdirs = None
        if args.data_subdirs:
            subdirs = {x.strip().lower() for x in args.data_subdirs.split(",") if x.strip()}
        cap_expression = args.expression_cap_per_project
        cap_mutation = args.mutation_cap_per_project
        cap_normal_expression = args.normal_expression_cap_per_project
        if args.use_medium_cap_profile:
            cap_expression, cap_mutation = resolve_cap_profile("medium")
        if args.use_aggressive_cap_profile:
            cap_expression, cap_mutation = resolve_cap_profile("aggressive")
        caps = None
        if cap_expression is not None or cap_mutation is not None or cap_normal_expression is not None:
            caps = {
                project_id: {
                    **({"expression": cap_expression} if cap_expression is not None else {}),
                    **(
                        {"expression_normal": cap_normal_expression}
                        if cap_normal_expression is not None
                        else {}
                    ),
                    **({"mutations": cap_mutation} if cap_mutation is not None else {}),
                }
                for project_id in cfg.tcga.projects
            }
        paired_case_ids = None
        if args.pair_tumors_to_downloaded_normals:
            expression_path = Path("data/silver/silver_expression_tcga.parquet")
            if not expression_path.exists():
                raise RuntimeError("Paired acquisition requires data/silver/silver_expression_tcga.parquet")
            expression_cases = pl.read_parquet(
                expression_path,
                columns=["project_id", "case_id", "sample_type"],
            ).unique()
            paired_case_ids = {
                project_id: {
                    str(case_id)
                    for case_id in expression_cases.filter(
                        (pl.col("project_id") == project_id)
                        & (pl.col("sample_type").str.to_lowercase() == "solid tissue normal")
                    )
                    .get_column("case_id")
                    .drop_nulls()
                    .to_list()
                    if str(case_id).strip() not in {"", "Unknown"}
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
            download_workers=args.download_workers,
            paired_expression_case_ids_by_project=paired_case_ids,
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
            "Gold summary counts: projects=%s patients=%s samples=%s files=%s gtex_expr_samples=%s mutation_records=%s mutation_gene_rows=%s tumor_vs_normal_rows=%s batch_effect_sensitivity_rows=%s reference_triangulation_rows=%s candidate_priority_rows=%s",
            summary["tcga_project_count"],
            summary["tcga_patient_count"],
            summary["tcga_sample_count"],
            summary["tcga_file_count"],
            summary["gtex_expression_sample_count"],
            summary["mutation_record_count"],
            summary["mutation_gene_rows"],
            summary["tumor_vs_normal_rows"],
            summary["batch_effect_sensitivity_rows"],
            summary["reference_triangulation_rows"],
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
    if args.command == "run-bootstrap-stability":
        load_config(args.config)
        bootstrap_summary = build_bootstrap_stability(
            candidates_per_cancer=args.candidates_per_cancer,
            iterations=args.iterations,
            top_k=args.top_k,
            random_seed=args.random_seed,
        )
        logger = get_logger("canceromicslake")
        logger.info(
            "Bootstrap stability: rows=%s iterations=%s tiers=%s elapsed_seconds=%s",
            bootstrap_summary["row_count"],
            bootstrap_summary["iterations"],
            bootstrap_summary["tier_counts"],
            bootstrap_summary["elapsed_seconds"],
        )
        print("Bootstrap stability build completed.")
        return
    if args.command == "run-external-validation":
        load_config(args.config)
        validation_summary = build_external_expression_validation(
            recount3_expression_path=args.recount3_expression_path,
            top_k=args.top_k,
        )
        logger = get_logger("canceromicslake")
        logger.info(
            "External expression validation: status=%s rows=%s tiers=%s path=%s",
            validation_summary["status"],
            validation_summary["row_count"],
            validation_summary["tier_counts"],
            validation_summary["path"],
        )
        print("External expression validation build completed.")
        return
    if args.command == "run-consensus-candidates":
        load_config(args.config)
        consensus_summary = build_consensus_candidates()
        logger = get_logger("canceromicslake")
        logger.info(
            "Consensus candidates: status=%s rows=%s prioritized=%s watchlist=%s path=%s",
            consensus_summary["status"],
            consensus_summary["row_count"],
            consensus_summary["prioritized_count"],
            consensus_summary["watchlist_count"],
            consensus_summary["path"],
        )
        print("Consensus candidate build completed.")
        return
    if args.command == "run-reference-ablation":
        load_config(args.config)
        top_k_values = [
            int(value.strip())
            for value in args.top_k_values.split(",")
            if value.strip()
        ]
        evaluation = build_reference_ablation_evaluation(top_k_values=top_k_values)
        logger = get_logger("canceromicslake")
        logger.info(
            "Reference ablation: status=%s comparisons=%s ablations=%s top_k_values=%s",
            evaluation["status"],
            evaluation["reference_comparison_rows"],
            evaluation["consensus_ablation_rows"],
            evaluation["top_k_values"],
        )
        print("Reference ablation evaluation completed.")
        return
    if args.command == "run-expression-statistics":
        load_config(args.config)
        statistics_summary = build_expression_statistical_support()
        logger = get_logger("canceromicslake")
        logger.info(
            "Expression statistics: status=%s rows=%s tiers=%s path=%s elapsed_seconds=%s",
            statistics_summary["status"],
            statistics_summary["row_count"],
            statistics_summary["tier_counts"],
            statistics_summary["path"],
            statistics_summary["elapsed_seconds"],
        )
        print("Expression statistical support build completed.")
        return
    if args.command == "run-paired-expression":
        load_config(args.config)
        paired_summary = build_paired_expression_support()
        logger = get_logger("canceromicslake")
        logger.info(
            "Paired expression support: status=%s rows=%s cases=%s tiers=%s path=%s",
            paired_summary["status"],
            paired_summary["row_count"],
            paired_summary["matched_case_support"],
            paired_summary["tier_counts"],
            paired_summary["path"],
        )
        print("Paired expression support build completed.")
        return
    if args.command == "run-pathway-enrichment":
        load_config(args.config)
        pathway_summary = build_pathway_enrichment(
            pathway_gmt_path=args.pathway_gmt,
            pathway_source=args.pathway_source,
            min_overlap=args.min_overlap,
        )
        logger = get_logger("canceromicslake")
        logger.info(
            "Pathway enrichment: status=%s rows=%s pathways=%s tiers=%s path=%s",
            pathway_summary["status"],
            pathway_summary["row_count"],
            pathway_summary["pathway_count"],
            pathway_summary["tier_counts"],
            pathway_summary["path"],
        )
        print("Pathway enrichment build completed.")
        return
    if args.command == "run-recount3-expression":
        load_config(args.config)
        recount3_summary = build_recount3_expression_extract(
            output_path=args.output,
            sample_cap_per_cohort=args.sample_cap_per_cohort,
            run_mode=run_mode,
        )
        logger = get_logger("canceromicslake")
        logger.info(
            "recount3 expression extract: cohorts=%s samples=%s rows=%s bytes=%s",
            recount3_summary["cohort_count"],
            recount3_summary["selected_sample_count"],
            recount3_summary["row_count"],
            recount3_summary["output_bytes"],
        )
        print("recount3 expression extraction completed.")
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
    if args.command == "run-research-benchmark":
        load_config(args.config)
        payload = run_research_benchmark(
            gold_dir=args.gold_dir,
            output_path=args.output,
            repeats=args.repeats,
            warmups=args.warmups,
            threads=args.threads,
        )
        logger = get_logger("canceromicslake")
        passed = sum(1 for workload in payload["workloads"] if workload["status"] == "passed")
        logger.info("Research benchmark status=%s passed_workloads=%s", payload["status"], passed)
        if payload["status"] == "failed":
            raise RuntimeError(f"Research benchmark failed. See {args.output}")
        print("Research benchmark completed.")
        return
    if args.command == "build-fair-release":
        load_config(args.config)
        payload = build_fair_release(
            version=args.version,
            gold_dir=args.gold_dir,
            output_root=args.output_root,
            creator=args.creator,
        )
        logger = get_logger("canceromicslake")
        logger.info(
            "FAIR release built: version=%s resources=%s bytes=%s path=%s",
            payload["release_version"],
            payload["resource_count"],
            payload["total_bytes"],
            payload["release_directory"],
        )
        print("FAIR release bundle completed.")
        return
    if args.command == "build-manuscript-package":
        load_config(args.config)
        payload = build_manuscript_package(
            output_dir=args.output_dir,
            fair_manifest_path=args.fair_manifest,
        )
        logger = get_logger("canceromicslake")
        logger.info(
            "Manuscript package built: files=%s claims=%s path=%s commit=%s",
            payload["file_count"],
            payload["claim_count"],
            payload["output_directory"],
            payload["git_commit"],
        )
        print("Manuscript evidence package completed.")
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
            download_workers=args.download_workers,
        )
        logger = get_logger("canceromicslake")
        logger.info("Pipeline flow completed: run_id=%s status=%s", result["pipeline_run_id"], result["status"])
        print("Pipeline flow completed.")
        return


if __name__ == "__main__":
    main()
