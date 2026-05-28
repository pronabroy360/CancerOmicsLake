from __future__ import annotations

import csv
from pathlib import Path

import polars as pl


def export_neo4j_csv(rows: list[dict[str, str]], output_path: str | Path) -> Path:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        output.write_text("", encoding="utf-8")
        return output
    with output.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    return output


def export_neo4j_from_gold_graph_tables(
    graph_nodes_path: str | Path = "data/gold/gold_graph_nodes.parquet",
    graph_edges_path: str | Path = "data/gold/gold_graph_edges.parquet",
    output_dir: str | Path = "outputs/graph_exports/neo4j",
) -> dict[str, object]:
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)

    nodes_df = pl.read_parquet(graph_nodes_path) if Path(graph_nodes_path).exists() else pl.DataFrame()
    edges_df = pl.read_parquet(graph_edges_path) if Path(graph_edges_path).exists() else pl.DataFrame()

    nodes_rows = nodes_df.to_dicts() if not nodes_df.is_empty() else []
    edges_rows = edges_df.to_dicts() if not edges_df.is_empty() else []

    nodes_csv = export_neo4j_csv(nodes_rows, output_root / "nodes.csv")
    edges_csv = export_neo4j_csv(edges_rows, output_root / "edges.csv")

    return {
        "nodes_csv": str(nodes_csv),
        "edges_csv": str(edges_csv),
        "nodes_count": len(nodes_rows),
        "edges_count": len(edges_rows),
    }
