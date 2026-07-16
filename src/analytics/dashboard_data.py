from __future__ import annotations

import json
from pathlib import Path

import polars as pl

from src.analytics.batch_effect_sensitivity import (
    BATCH_EFFECT_SENSITIVITY_SCHEMA,
    batch_effect_sensitivity,
)
from src.analytics.bootstrap_stability import BOOTSTRAP_STABILITY_SCHEMA, bootstrap_stability
from src.analytics.candidate_priority import candidate_priority_dataframe
from src.analytics.consensus_candidates import CONSENSUS_CANDIDATE_SCHEMA, consensus_candidates
from src.analytics.evidence_confidence import CONFIDENCE_SCHEMA, evidence_confidence
from src.analytics.external_validation import EXTERNAL_VALIDATION_SCHEMA, external_expression_validation
from src.analytics.expression_statistics import EXPRESSION_STATISTICS_SCHEMA, expression_statistical_support
from src.analytics.paired_expression import PAIRED_EXPRESSION_SCHEMA, paired_expression_support
from src.analytics.pathway_enrichment import PATHWAY_ENRICHMENT_SCHEMA, pathway_enrichment
from src.analytics.reference_triangulation import REFERENCE_TRIANGULATION_SCHEMA, reference_triangulation
from src.analytics.cohort_summary import cohort_summary_from_gold
from src.analytics.expression_summary import expression_by_gene
from src.analytics.tumor_vs_normal import tumor_vs_normal_by_gene
from src.graph.public_graph import PUBLIC_NODE_LABELS, filter_public_graph_tables


def overview_metrics(
    gold_summary_path: str | Path = "data/gold/gold_cohort_summary.parquet",
    quality_report_path: str | Path = "outputs/reports/silver_data_quality_report.json",
) -> dict[str, object]:
    summary = cohort_summary_from_gold(gold_summary_path)
    quality_status = "unknown"
    quality_generated_at = ""
    quality_run_id = ""

    report = Path(quality_report_path)
    if report.exists():
        payload = json.loads(report.read_text(encoding="utf-8"))
        quality_status = str(payload.get("status", "unknown"))
        quality_generated_at = str(payload.get("generated_at", ""))
        quality_run_id = str(payload.get("pipeline_run_id", ""))

    return {
        **summary,
        "quality_status": quality_status,
        "quality_generated_at": quality_generated_at,
        "quality_run_id": quality_run_id,
    }


def cohort_distribution_data(
    silver_samples_path: str | Path = "data/silver/silver_samples.parquet",
) -> dict[str, object]:
    path = Path(silver_samples_path)
    if not path.exists():
        empty = pl.DataFrame({"label": [], "count": []})
        return {
            "project_options": [],
            "sample_type_options": [],
            "samples": pl.DataFrame(schema={"project_id": pl.Utf8, "case_id": pl.Utf8, "sample_id": pl.Utf8, "sample_type": pl.Utf8}),
            "sample_by_cancer": empty,
            "sample_by_type": empty,
            "total_samples": 0,
            "total_cases": 0,
        }

    df = pl.read_parquet(path)
    if df.is_empty() or not {"project_id", "case_id", "sample_id", "sample_type"}.issubset(set(df.columns)):
        empty = pl.DataFrame({"label": [], "count": []})
        return {
            "project_options": [],
            "sample_type_options": [],
            "samples": pl.DataFrame(schema={"project_id": pl.Utf8, "case_id": pl.Utf8, "sample_id": pl.Utf8, "sample_type": pl.Utf8}),
            "sample_by_cancer": empty,
            "sample_by_type": empty,
            "total_samples": 0,
            "total_cases": 0,
        }

    project_options = sorted({str(v) for v in df.get_column("project_id").drop_nulls().unique().to_list()})
    sample_type_options = sorted({str(v) for v in df.get_column("sample_type").drop_nulls().unique().to_list()})

    sample_by_cancer = (
        df.group_by("project_id")
        .agg(pl.col("sample_id").n_unique().alias("count"))
        .sort("count", descending=True)
        .rename({"project_id": "label"})
    )
    sample_by_type = (
        df.group_by("sample_type")
        .agg(pl.col("sample_id").n_unique().alias("count"))
        .sort("count", descending=True)
        .rename({"sample_type": "label"})
    )

    return {
        "project_options": project_options,
        "sample_type_options": sample_type_options,
        "samples": df,
        "sample_by_cancer": sample_by_cancer,
        "sample_by_type": sample_by_type,
        "total_samples": int(df.get_column("sample_id").n_unique()),
        "total_cases": int(df.get_column("case_id").n_unique()),
    }


def gene_expression_data(
    gene_symbol: str,
    silver_dir: str | Path = "data/silver",
) -> dict[str, object]:
    payload = expression_by_gene(gene_symbol=gene_symbol, silver_dir=silver_dir)
    rows = payload.get("rows", [])
    data = pl.DataFrame(rows) if rows else pl.DataFrame(
        schema={
            "source": pl.Utf8,
            "project_id": pl.Utf8,
            "tissue_site": pl.Utf8,
            "median_expression": pl.Float64,
            "mean_expression": pl.Float64,
            "sample_count": pl.Int64,
        }
    )
    tcga = data.filter(pl.col("source") == "TCGA") if not data.is_empty() and "source" in data.columns else data
    gtex = data.filter(pl.col("source") == "GTEx") if not data.is_empty() and "source" in data.columns else data
    return {
        "gene_symbol": str(payload.get("gene_symbol", gene_symbol.upper())),
        "combined": data,
        "tcga": tcga,
        "gtex": gtex,
    }


def tumor_vs_normal_data(
    gene_symbol: str,
    cancer_type: str | None = None,
    gold_path: str | Path = "data/gold/gold_tumor_vs_normal_expression.parquet",
) -> dict[str, object]:
    payload = tumor_vs_normal_by_gene(gene_symbol=gene_symbol, gold_path=gold_path)
    rows = payload.get("rows", [])
    data = pl.DataFrame(rows) if rows else pl.DataFrame(
        schema={
            "gene_symbol": pl.Utf8,
            "cancer_type": pl.Utf8,
            "median_tcga_tumor_expression": pl.Float64,
            "median_gtex_normal_expression": pl.Float64,
            "mean_tcga_tumor_expression": pl.Float64,
            "mean_gtex_normal_expression": pl.Float64,
            "log2_fold_change": pl.Float64,
            "sample_count_tumor": pl.Int64,
            "sample_count_normal": pl.Int64,
        }
    )
    if cancer_type and not data.is_empty() and "cancer_type" in data.columns:
        data = data.filter(pl.col("cancer_type") == cancer_type)
    return {
        "gene_symbol": str(payload.get("gene_symbol", gene_symbol.upper())),
        "warning": str(payload.get("warning", "")),
        "rows": data.sort("log2_fold_change", descending=True) if not data.is_empty() else data,
    }


def mutation_landscape_data(
    cancer_type: str | None = None,
    gene_query: str | None = None,
    limit: int = 50,
    gold_path: str | Path = "data/gold/gold_mutation_frequency_by_gene.parquet",
) -> pl.DataFrame:
    path = Path(gold_path)
    if not path.exists():
        return pl.DataFrame(
            schema={
                "gene_symbol": pl.Utf8,
                "cancer_type": pl.Utf8,
                "mutated_sample_count": pl.Int64,
                "total_profiled_sample_count": pl.Int64,
                "mutation_frequency": pl.Float64,
                "top_variant_classification": pl.Utf8,
            }
        )
    df = pl.read_parquet(path)
    if df.is_empty():
        return df
    if cancer_type:
        df = df.filter(pl.col("cancer_type") == cancer_type)
    if gene_query:
        q = gene_query.upper()
        df = df.filter(pl.col("gene_symbol").cast(pl.Utf8).str.to_uppercase().str.contains(q))
    return df.sort("mutation_frequency", descending=True).head(limit)


def candidate_priority_data(
    cancer_type: str | None = None,
    gene_query: str | None = None,
    tier: str | None = None,
    min_priority_score: float | None = None,
    limit: int = 50,
    gold_path: str | Path = "data/gold/gold_candidate_gene_priority.parquet",
) -> pl.DataFrame:
    return candidate_priority_dataframe(
        cancer_type=cancer_type,
        gene_query=gene_query,
        tier=tier,
        min_priority_score=min_priority_score,
        limit=limit,
        gold_path=gold_path,
    )


def evidence_confidence_data(
    cancer_type: str | None = None,
    gene_query: str | None = None,
    confidence_tier: str | None = None,
    batch_concordance: str | None = None,
    min_confidence: float | None = None,
    limit: int = 50,
    gold_path: str | Path = "data/gold/gold_cancer_gene_evidence_confidence.parquet",
) -> pl.DataFrame:
    payload = evidence_confidence(
        cancer_type=cancer_type,
        gene_query=gene_query,
        confidence_tier=confidence_tier,
        batch_concordance=batch_concordance,
        min_confidence=min_confidence,
        limit=limit,
        gold_path=gold_path,
    )
    rows = payload.get("rows", [])
    return pl.DataFrame(rows) if rows else pl.DataFrame(schema=CONFIDENCE_SCHEMA)


def batch_effect_sensitivity_data(
    cancer_type: str | None = None,
    gene_query: str | None = None,
    support_tier: str | None = None,
    direction: str | None = None,
    min_abs_percentile_delta: float | None = None,
    limit: int = 50,
    gold_path: str | Path = "data/gold/gold_batch_effect_sensitivity.parquet",
) -> pl.DataFrame:
    payload = batch_effect_sensitivity(
        cancer_type=cancer_type,
        gene_query=gene_query,
        support_tier=support_tier,
        direction=direction,
        min_abs_percentile_delta=min_abs_percentile_delta,
        limit=limit,
        gold_path=gold_path,
    )
    rows = payload.get("rows", [])
    return pl.DataFrame(rows) if rows else pl.DataFrame(schema=BATCH_EFFECT_SENSITIVITY_SCHEMA)


def reference_triangulation_data(
    cancer_type: str | None = None,
    gene_query: str | None = None,
    concordance: str | None = None,
    support_tier: str | None = None,
    min_stability: float | None = None,
    limit: int = 50,
    gold_path: str | Path = "data/gold/gold_reference_triangulation.parquet",
) -> pl.DataFrame:
    payload = reference_triangulation(
        cancer_type=cancer_type,
        gene_query=gene_query,
        concordance=concordance,
        support_tier=support_tier,
        min_stability=min_stability,
        limit=limit,
        gold_path=gold_path,
    )
    rows = payload.get("rows", [])
    return pl.DataFrame(rows) if rows else pl.DataFrame(schema=REFERENCE_TRIANGULATION_SCHEMA)


def bootstrap_stability_data(
    cancer_type: str | None = None,
    gene_query: str | None = None,
    stability_tier: str | None = None,
    min_stability: float | None = None,
    limit: int = 50,
    gold_path: str | Path = "data/gold/gold_candidate_bootstrap_stability.parquet",
) -> pl.DataFrame:
    payload = bootstrap_stability(
        cancer_type=cancer_type,
        gene_query=gene_query,
        stability_tier=stability_tier,
        min_stability=min_stability,
        limit=limit,
        gold_path=gold_path,
    )
    rows = payload.get("rows", [])
    return pl.DataFrame(rows) if rows else pl.DataFrame(schema=BOOTSTRAP_STABILITY_SCHEMA)


def external_expression_validation_data(
    cancer_type: str | None = None,
    gene_query: str | None = None,
    validation_tier: str | None = None,
    direction_agreement: str | None = None,
    min_validation_score: float | None = None,
    limit: int = 50,
    gold_path: str | Path = "data/gold/gold_external_expression_validation.parquet",
) -> pl.DataFrame:
    payload = external_expression_validation(
        cancer_type=cancer_type,
        gene_query=gene_query,
        validation_tier=validation_tier,
        direction_agreement=direction_agreement,
        min_validation_score=min_validation_score,
        limit=limit,
        gold_path=gold_path,
    )
    rows = payload.get("rows", [])
    return pl.DataFrame(rows) if rows else pl.DataFrame(schema=EXTERNAL_VALIDATION_SCHEMA)


def consensus_candidates_data(
    cancer_type: str | None = None,
    gene_query: str | None = None,
    decision: str | None = None,
    publication_tier: str | None = None,
    min_consensus_score: float | None = None,
    limit: int = 50,
    gold_path: str | Path = "data/gold/gold_consensus_candidate_genes.parquet",
) -> pl.DataFrame:
    payload = consensus_candidates(
        cancer_type=cancer_type,
        gene_query=gene_query,
        decision=decision,
        publication_tier=publication_tier,
        min_consensus_score=min_consensus_score,
        limit=limit,
        gold_path=gold_path,
    )
    rows = payload.get("rows", [])
    return pl.DataFrame(rows) if rows else pl.DataFrame(schema=CONSENSUS_CANDIDATE_SCHEMA)


def expression_statistical_support_data(
    cancer_type: str | None = None,
    gene_query: str | None = None,
    support_tier: str | None = None,
    max_fdr: float | None = None,
    min_support_score: float | None = None,
    limit: int = 50,
    gold_path: str | Path = "data/gold/gold_expression_statistical_support.parquet",
) -> pl.DataFrame:
    payload = expression_statistical_support(
        cancer_type=cancer_type,
        gene_query=gene_query,
        support_tier=support_tier,
        max_fdr=max_fdr,
        min_support_score=min_support_score,
        limit=limit,
        gold_path=gold_path,
    )
    rows = payload.get("rows", [])
    return pl.DataFrame(rows) if rows else pl.DataFrame(schema=EXPRESSION_STATISTICS_SCHEMA)


def paired_expression_support_data(
    cancer_type: str | None = None,
    gene_query: str | None = None,
    support_tier: str | None = None,
    max_fdr: float | None = None,
    min_support_score: float | None = None,
    limit: int = 50,
    gold_path: str | Path = "data/gold/gold_paired_tcga_expression_support.parquet",
) -> pl.DataFrame:
    payload = paired_expression_support(
        cancer_type=cancer_type,
        gene_query=gene_query,
        support_tier=support_tier,
        max_fdr=max_fdr,
        min_support_score=min_support_score,
        limit=limit,
        gold_path=gold_path,
    )
    rows = payload.get("rows", [])
    return pl.DataFrame(rows) if rows else pl.DataFrame(schema=PAIRED_EXPRESSION_SCHEMA)


def pathway_enrichment_data(
    cancer_type: str | None = None,
    candidate_set: str | None = None,
    pathway_query: str | None = None,
    enrichment_tier: str | None = None,
    max_fdr: float | None = None,
    min_overlap: int | None = None,
    limit: int = 50,
    gold_path: str | Path = "data/gold/gold_pathway_enrichment.parquet",
) -> pl.DataFrame:
    payload = pathway_enrichment(
        cancer_type=cancer_type,
        candidate_set=candidate_set,
        pathway_query=pathway_query,
        enrichment_tier=enrichment_tier,
        max_fdr=max_fdr,
        min_overlap=min_overlap,
        limit=limit,
        gold_path=gold_path,
    )
    rows = payload.get("rows", [])
    return pl.DataFrame(rows) if rows else pl.DataFrame(schema=PATHWAY_ENRICHMENT_SCHEMA)


def graph_explorer_data(
    edge_types: list[str] | None = None,
    node_query: str | None = None,
    max_rows: int = 500,
    graph_nodes_path: str | Path = "data/gold/gold_graph_nodes.parquet",
    graph_edges_path: str | Path = "data/gold/gold_graph_edges.parquet",
) -> dict[str, pl.DataFrame]:
    nodes_path = Path(graph_nodes_path)
    edges_path = Path(graph_edges_path)
    nodes = pl.read_parquet(nodes_path) if nodes_path.exists() else pl.DataFrame()
    edges = pl.read_parquet(edges_path) if edges_path.exists() else pl.DataFrame()
    if not nodes.is_empty() and not edges.is_empty():
        nodes, edges, _ = filter_public_graph_tables(nodes, edges)

    if nodes.is_empty() or edges.is_empty():
        empty_nodes = pl.DataFrame(schema={"node_id": pl.Utf8, "node_label": pl.Utf8, "name": pl.Utf8, "primary_site": pl.Utf8, "source": pl.Utf8})
        empty_edges = pl.DataFrame(schema={"edge_id": pl.Utf8, "source_node_id": pl.Utf8, "target_node_id": pl.Utf8, "edge_type": pl.Utf8, "weight": pl.Float64, "evidence_source": pl.Utf8})
        return {
            "nodes": empty_nodes,
            "edges": empty_edges,
            "edge_type_counts": pl.DataFrame({"edge_type": [], "count": []}),
            "node_label_counts": pl.DataFrame({"node_label": [], "count": []}),
        }

    filtered_edges = edges
    if edge_types:
        filtered_edges = filtered_edges.filter(pl.col("edge_type").is_in(edge_types))

    filtered_nodes = nodes
    if node_query:
        q = node_query.upper()
        filtered_nodes = nodes.filter(
            pl.col("node_id").cast(pl.Utf8).str.to_uppercase().str.contains(q)
            | pl.col("name").cast(pl.Utf8).str.to_uppercase().str.contains(q)
            | pl.col("node_label").cast(pl.Utf8).str.to_uppercase().str.contains(q)
        )
        node_ids = filtered_nodes.get_column("node_id").to_list()
        if node_ids:
            filtered_edges = filtered_edges.filter(
                pl.col("source_node_id").is_in(node_ids) | pl.col("target_node_id").is_in(node_ids)
            )
        else:
            filtered_edges = filtered_edges.head(0)

    filtered_edges = filtered_edges.head(max_rows)
    edge_node_ids = set(filtered_edges.get_column("source_node_id").to_list()) | set(
        filtered_edges.get_column("target_node_id").to_list()
    )
    filtered_nodes = nodes.filter(pl.col("node_id").is_in(list(edge_node_ids))).head(max_rows)

    edge_type_counts = (
        filtered_edges.group_by("edge_type")
        .agg(pl.len().alias("count"))
        .sort("count", descending=True)
    )
    node_label_counts = (
        filtered_nodes.group_by("node_label")
        .agg(pl.len().alias("count"))
        .sort("count", descending=True)
    )

    return {
        "nodes": filtered_nodes,
        "edges": filtered_edges,
        "edge_type_counts": edge_type_counts,
        "node_label_counts": node_label_counts,
    }


def graph_node_metrics_data(
    limit: int = 50,
    graph_metrics_path: str | Path = "data/gold/gold_graph_node_metrics.parquet",
) -> pl.DataFrame:
    path = Path(graph_metrics_path)
    schema = {
        "node_id": pl.Utf8,
        "node_label": pl.Utf8,
        "name": pl.Utf8,
        "total_degree": pl.Int64,
        "in_degree": pl.Int64,
        "out_degree": pl.Int64,
        "weighted_degree": pl.Float64,
        "edge_type_count": pl.Int64,
        "degree_rank": pl.Int64,
    }
    if not path.exists():
        return pl.DataFrame(schema=schema)
    df = pl.read_parquet(path)
    if df.is_empty() or "total_degree" not in df.columns:
        return pl.DataFrame(schema=schema)
    if "node_label" in df.columns:
        df = df.filter(pl.col("node_label").is_in(sorted(PUBLIC_NODE_LABELS)))
    return df.sort(["total_degree", "weighted_degree"], descending=[True, True]).head(limit)


def quality_report_data(
    quality_report_path: str | Path = "outputs/reports/silver_data_quality_report.json",
) -> dict[str, object]:
    report = Path(quality_report_path)
    if not report.exists():
        empty_checks = pl.DataFrame(schema={"check_name": pl.Utf8, "status": pl.Utf8, "failed_rows": pl.Int64})
        return {
            "status": "unknown",
            "pipeline_run_id": "",
            "generated_at": "",
            "checks": empty_checks,
            "status_counts": pl.DataFrame({"status": [], "count": []}),
        }

    payload = json.loads(report.read_text(encoding="utf-8"))
    checks_raw = payload.get("checks", [])
    checks = pl.DataFrame(checks_raw) if isinstance(checks_raw, list) and checks_raw else pl.DataFrame(
        schema={"check_name": pl.Utf8, "status": pl.Utf8, "failed_rows": pl.Int64}
    )
    status_counts = (
        checks.group_by("status")
        .agg(pl.len().alias("count"))
        .sort("count", descending=True)
        if not checks.is_empty() and "status" in checks.columns
        else pl.DataFrame({"status": [], "count": []})
    )
    return {
        "status": str(payload.get("status", "unknown")),
        "pipeline_run_id": str(payload.get("pipeline_run_id", "")),
        "generated_at": str(payload.get("generated_at", "")),
        "checks": checks,
        "status_counts": status_counts,
    }
