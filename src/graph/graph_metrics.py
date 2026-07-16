from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any

import polars as pl

from src.graph.public_graph import filter_public_graph_tables


NODE_SCHEMA = {
    "node_id": pl.Utf8,
    "node_label": pl.Utf8,
    "name": pl.Utf8,
    "primary_site": pl.Utf8,
    "source": pl.Utf8,
}

EDGE_SCHEMA = {
    "edge_id": pl.Utf8,
    "source_node_id": pl.Utf8,
    "target_node_id": pl.Utf8,
    "edge_type": pl.Utf8,
    "weight": pl.Float64,
    "evidence_source": pl.Utf8,
}

METRIC_SCHEMA = {
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


def _read_or_empty(path: Path, schema: dict[str, pl.DataType]) -> pl.DataFrame:
    if path.exists():
        return pl.read_parquet(path)
    return pl.DataFrame(schema=schema)


def _empty_metrics() -> pl.DataFrame:
    return pl.DataFrame(schema=METRIC_SCHEMA)


def graph_size_summary(nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> dict[str, int]:
    return {"node_count": len(nodes), "edge_count": len(edges)}


def build_graph_node_metrics(
    graph_nodes_path: str | Path = "data/gold/gold_graph_nodes.parquet",
    graph_edges_path: str | Path = "data/gold/gold_graph_edges.parquet",
    output_path: str | Path = "data/gold/gold_graph_node_metrics.parquet",
    report_path: str | Path = "outputs/reports/graph_metrics_report.json",
    public_safe: bool = True,
) -> dict[str, object]:
    nodes_path = Path(graph_nodes_path)
    edges_path = Path(graph_edges_path)
    nodes = _read_or_empty(nodes_path, NODE_SCHEMA)
    edges = _read_or_empty(edges_path, EDGE_SCHEMA)
    public_filter_audit: dict[str, int] | None = None
    if public_safe:
        nodes, edges, public_filter_audit = filter_public_graph_tables(nodes, edges)

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    report_out = Path(report_path)
    report_out.parent.mkdir(parents=True, exist_ok=True)

    if nodes.is_empty():
        metrics = _empty_metrics()
        metrics.write_parquet(out)
        payload = {
            "generated_at": datetime.now(UTC).isoformat(),
            "status": "warning",
            "node_count": 0,
            "edge_count": int(edges.height),
            "metric_rows": 0,
            "top_nodes_by_degree": [],
            "edge_type_counts": [],
            "warning": "Graph nodes table is empty or missing.",
            "public_safe": public_safe,
            "public_filter_audit": public_filter_audit,
        }
        report_out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return {"path": str(out), "report_path": str(report_out), "metric_rows": 0, "status": "warning"}

    if edges.is_empty():
        metrics = nodes.select(
            [
                pl.col("node_id"),
                pl.col("node_label"),
                pl.col("name"),
                pl.lit(0, dtype=pl.Int64).alias("total_degree"),
                pl.lit(0, dtype=pl.Int64).alias("in_degree"),
                pl.lit(0, dtype=pl.Int64).alias("out_degree"),
                pl.lit(0.0, dtype=pl.Float64).alias("weighted_degree"),
                pl.lit(0, dtype=pl.Int64).alias("edge_type_count"),
                pl.int_range(1, pl.len() + 1).alias("degree_rank"),
            ]
        )
    else:
        out_degree = edges.group_by("source_node_id").agg(
            [
                pl.len().alias("out_degree"),
                pl.col("weight").cast(pl.Float64, strict=False).fill_null(0.0).sum().alias("out_weight"),
                pl.col("edge_type").n_unique().alias("out_edge_type_count"),
            ]
        )
        in_degree = edges.group_by("target_node_id").agg(
            [
                pl.len().alias("in_degree"),
                pl.col("weight").cast(pl.Float64, strict=False).fill_null(0.0).sum().alias("in_weight"),
                pl.col("edge_type").n_unique().alias("in_edge_type_count"),
            ]
        )
        metrics = (
            nodes.select(["node_id", "node_label", "name"])
            .join(out_degree, left_on="node_id", right_on="source_node_id", how="left")
            .join(in_degree, left_on="node_id", right_on="target_node_id", how="left")
            .with_columns(
                [
                    pl.col("out_degree").fill_null(0).cast(pl.Int64),
                    pl.col("in_degree").fill_null(0).cast(pl.Int64),
                    pl.col("out_weight").fill_null(0.0).cast(pl.Float64),
                    pl.col("in_weight").fill_null(0.0).cast(pl.Float64),
                    pl.col("out_edge_type_count").fill_null(0).cast(pl.Int64),
                    pl.col("in_edge_type_count").fill_null(0).cast(pl.Int64),
                ]
            )
            .with_columns(
                [
                    (pl.col("out_degree") + pl.col("in_degree")).alias("total_degree"),
                    (pl.col("out_weight") + pl.col("in_weight")).alias("weighted_degree"),
                    (pl.col("out_edge_type_count") + pl.col("in_edge_type_count")).alias("edge_type_count"),
                ]
            )
            .sort(["total_degree", "weighted_degree", "node_id"], descending=[True, True, False])
            .with_row_index("degree_rank", offset=1)
            .select(
                [
                    "node_id",
                    "node_label",
                    "name",
                    "total_degree",
                    "in_degree",
                    "out_degree",
                    "weighted_degree",
                    "edge_type_count",
                    "degree_rank",
                ]
            )
        )

    metrics.write_parquet(out)
    top_nodes = metrics.sort(["total_degree", "weighted_degree"], descending=[True, True]).head(20).to_dicts()
    edge_type_counts = (
        edges.group_by("edge_type")
        .agg(
            [
                pl.len().alias("edge_count"),
                pl.col("weight").cast(pl.Float64, strict=False).fill_null(0.0).mean().alias("mean_weight"),
            ]
        )
        .sort("edge_count", descending=True)
        .to_dicts()
        if not edges.is_empty()
        else []
    )
    payload = {
        "generated_at": datetime.now(UTC).isoformat(),
        "status": "passed",
        "node_count": int(nodes.height),
        "edge_count": int(edges.height),
        "metric_rows": int(metrics.height),
        "top_nodes_by_degree": top_nodes,
        "edge_type_counts": edge_type_counts,
        "public_safe": public_safe,
        "public_filter_audit": public_filter_audit,
    }
    report_out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return {
        "path": str(out),
        "report_path": str(report_out),
        "metric_rows": int(metrics.height),
        "node_count": int(nodes.height),
        "edge_count": int(edges.height),
        "status": "passed",
        "public_safe": public_safe,
        "public_filter_audit": public_filter_audit,
    }
