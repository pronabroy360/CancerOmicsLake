from __future__ import annotations

from pathlib import Path

import polars as pl

from src.graph.export_neo4j import export_neo4j_csv
from src.graph.public_graph import filter_public_graph_tables


def export_graphify_csv(rows: list[dict[str, str]], output_path: str | Path) -> Path:
    return export_neo4j_csv(rows, output_path)


def export_graphify_from_gold_graph_tables(
    graph_nodes_path: str | Path = "data/gold/gold_graph_nodes.parquet",
    graph_edges_path: str | Path = "data/gold/gold_graph_edges.parquet",
    output_dir: str | Path = "outputs/graph_exports/graphify",
    public_safe: bool = True,
) -> dict[str, object]:
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)

    nodes_df = pl.read_parquet(graph_nodes_path) if Path(graph_nodes_path).exists() else pl.DataFrame()
    edges_df = pl.read_parquet(graph_edges_path) if Path(graph_edges_path).exists() else pl.DataFrame()

    public_audit = {
        "input_nodes": nodes_df.height,
        "public_nodes": nodes_df.height,
        "excluded_nodes": 0,
        "input_edges": edges_df.height,
        "public_edges": edges_df.height,
        "excluded_edges": 0,
    }
    if public_safe:
        nodes_df, edges_df, public_audit = filter_public_graph_tables(nodes_df, edges_df)

    nodes_rows = nodes_df.to_dicts() if not nodes_df.is_empty() else []
    edges_rows = edges_df.to_dicts() if not edges_df.is_empty() else []

    nodes_csv = export_graphify_csv(nodes_rows, output_root / "nodes.csv")
    edges_csv = export_graphify_csv(edges_rows, output_root / "edges.csv")

    return {
        "nodes_csv": str(nodes_csv),
        "edges_csv": str(edges_csv),
        "nodes_count": len(nodes_rows),
        "edges_count": len(edges_rows),
        "public_safe": public_safe,
        "public_filter_audit": public_audit,
    }
