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


def test_public_graph_exports_exclude_patient_and_sample_entities(tmp_path: Path) -> None:
    nodes_path = tmp_path / "nodes.parquet"
    edges_path = tmp_path / "edges.parquet"
    pl.DataFrame(
        [
            {"node_id": "GENE:TP53", "node_label": "Gene", "name": "TP53"},
            {"node_id": "TCGA-BRCA", "node_label": "CancerType", "name": "TCGA-BRCA"},
            {"node_id": "PATIENT:case-1", "node_label": "Patient", "name": "case-1"},
            {"node_id": "SAMPLE:sample-1", "node_label": "Sample", "name": "sample-1"},
        ]
    ).write_parquet(nodes_path)
    pl.DataFrame(
        [
            {
                "edge_id": "public",
                "source_node_id": "GENE:TP53",
                "target_node_id": "TCGA-BRCA",
                "edge_type": "MUTATED_IN_CANCER",
                "weight": 0.5,
                "evidence_source": "TCGA",
            },
            {
                "edge_id": "individual",
                "source_node_id": "PATIENT:case-1",
                "target_node_id": "SAMPLE:sample-1",
                "edge_type": "HAS_SAMPLE",
                "weight": 1.0,
                "evidence_source": "TCGA",
            },
        ]
    ).write_parquet(edges_path)

    output_dir = tmp_path / "neo4j"
    stale_bulk = output_dir / "bulk" / "nodes_patient.csv"
    stale_bulk.parent.mkdir(parents=True)
    stale_bulk.write_text("id\nPATIENT:stale\n", encoding="utf-8")
    summary = export_neo4j_from_gold_graph_tables(nodes_path, edges_path, output_dir)
    nodes = pl.read_csv(summary["nodes_csv"])
    edges = pl.read_csv(summary["edges_csv"])

    assert summary["public_safe"] is True
    assert summary["public_filter_audit"]["excluded_nodes"] == 2
    assert summary["public_filter_audit"]["excluded_edges"] == 1
    assert set(nodes.get_column("node_label")) == {"CancerType", "Gene"}
    assert edges.get_column("edge_id").to_list() == ["public"]
    assert not stale_bulk.exists()
