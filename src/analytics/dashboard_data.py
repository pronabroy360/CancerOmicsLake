from __future__ import annotations

import json
from pathlib import Path

import polars as pl

from src.analytics.cohort_summary import cohort_summary_from_gold
from src.analytics.expression_summary import expression_by_gene
from src.analytics.tumor_vs_normal import tumor_vs_normal_by_gene


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
