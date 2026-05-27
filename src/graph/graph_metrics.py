from __future__ import annotations


def graph_size_summary(nodes: list[dict[str, str]], edges: list[dict[str, str]]) -> dict[str, int]:
    return {"node_count": len(nodes), "edge_count": len(edges)}
