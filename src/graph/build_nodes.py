from __future__ import annotations


def build_graph_nodes_stub() -> list[dict[str, str]]:
    return [
        {"node_id": "TCGA-BRCA", "node_label": "CancerType", "name": "Breast invasive carcinoma"},
        {"node_id": "ENSG00000141510", "node_label": "Gene", "name": "TP53"},
    ]
