from __future__ import annotations

import polars as pl


PUBLIC_NODE_LABELS = frozenset({"CancerType", "Dataset", "Gene", "Pathway", "Tissue"})


def filter_public_graph_tables(
    nodes: pl.DataFrame,
    edges: pl.DataFrame,
) -> tuple[pl.DataFrame, pl.DataFrame, dict[str, int]]:
    if nodes.is_empty() or "node_label" not in nodes.columns or "node_id" not in nodes.columns:
        return nodes.head(0), edges.head(0), {
            "input_nodes": nodes.height,
            "public_nodes": 0,
            "excluded_nodes": nodes.height,
            "input_edges": edges.height,
            "public_edges": 0,
            "excluded_edges": edges.height,
        }

    public_nodes = nodes.filter(pl.col("node_label").is_in(sorted(PUBLIC_NODE_LABELS)))
    public_node_ids = public_nodes.get_column("node_id").unique().to_list()
    if edges.is_empty() or not {"source_node_id", "target_node_id"}.issubset(edges.columns):
        public_edges = edges.head(0)
    else:
        public_edges = edges.filter(
            pl.col("source_node_id").is_in(public_node_ids)
            & pl.col("target_node_id").is_in(public_node_ids)
        )

    return public_nodes, public_edges, {
        "input_nodes": nodes.height,
        "public_nodes": public_nodes.height,
        "excluded_nodes": nodes.height - public_nodes.height,
        "input_edges": edges.height,
        "public_edges": public_edges.height,
        "excluded_edges": edges.height - public_edges.height,
    }
