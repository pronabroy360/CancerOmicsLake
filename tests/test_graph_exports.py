from pathlib import Path

import polars as pl

from src.graph.export_graphify import export_graphify_from_gold_graph_tables
from src.graph.export_neo4j import export_neo4j_from_gold_graph_tables


def test_export_graph_csvs_from_gold_tables(tmp_path: Path) -> None:
    nodes_path = tmp_path / "gold_graph_nodes.parquet"
    edges_path = tmp_path / "gold_graph_edges.parquet"
    out_root = tmp_path / "exports"

    pl.DataFrame(
        [
            {"node_id": "TCGA-BRCA", "node_label": "CancerType", "name": "TCGA-BRCA"},
            {"node_id": "GENE:TP53", "node_label": "Gene", "name": "TP53"},
        ]
    ).write_parquet(nodes_path)
    pl.DataFrame(
        [
            {
                "edge_id": "e1",
                "source_node_id": "GENE:TP53",
                "target_node_id": "TCGA-BRCA",
                "edge_type": "MUTATED_IN_CANCER",
                "weight": 0.25,
                "evidence_source": "TCGA",
            }
        ]
    ).write_parquet(edges_path)

    neo4j = export_neo4j_from_gold_graph_tables(nodes_path, edges_path, out_root / "neo4j")
    graphify = export_graphify_from_gold_graph_tables(nodes_path, edges_path, out_root / "graphify")

    assert neo4j["nodes_count"] == 2
    assert neo4j["edges_count"] == 1
    assert Path(neo4j["nodes_csv"]).exists()
    assert Path(neo4j["edges_csv"]).exists()
    assert Path(neo4j["bulk_dir"]).exists()
    assert neo4j["bulk_node_file_count"] == 2
    assert neo4j["bulk_edge_file_count"] == 1
    assert Path(neo4j["import_cypher"]).exists()

    assert graphify["nodes_count"] == 2
    assert graphify["edges_count"] == 1
    assert Path(graphify["nodes_csv"]).exists()
    assert Path(graphify["edges_csv"]).exists()
    assert b"\r\n" not in Path(neo4j["nodes_csv"]).read_bytes()
    assert b"\r\n" not in Path(graphify["edges_csv"]).read_bytes()
