from __future__ import annotations


def build_graph_edges_stub() -> list[dict[str, str]]:
    return [
        {
            "edge_id": "edge-1",
            "source_node_id": "ENSG00000141510",
            "target_node_id": "TCGA-BRCA",
            "edge_type": "OVEREXPRESSED_IN",
            "weight": "1.0",
            "evidence_source": "stub",
        }
    ]
