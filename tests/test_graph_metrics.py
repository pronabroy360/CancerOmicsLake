from __future__ import annotations

import json
from pathlib import Path

import polars as pl

from src.graph.graph_metrics import build_graph_node_metrics, graph_size_summary


def test_graph_size_summary_counts_nodes_and_edges() -> None:
    assert graph_size_summary([{"node_id": "n1"}], [{"edge_id": "e1"}, {"edge_id": "e2"}]) == {
        "node_count": 1,
        "edge_count": 2,
    }


def test_build_graph_node_metrics_computes_degree_and_report(tmp_path: Path) -> None:
    nodes = tmp_path / "nodes.parquet"
    edges = tmp_path / "edges.parquet"
    metrics_out = tmp_path / "metrics.parquet"
    report_out = tmp_path / "report.json"

    pl.DataFrame(
        [
            {"node_id": "GENE:TP53", "node_label": "Gene", "name": "TP53", "primary_site": "Unknown", "source": "TCGA"},
            {"node_id": "TCGA-BRCA", "node_label": "CancerType", "name": "TCGA-BRCA", "primary_site": "Breast", "source": "TCGA"},
            {"node_id": "SAMPLE:S1", "node_label": "Sample", "name": "S1", "primary_site": "TCGA-BRCA", "source": "TCGA"},
        ]
    ).write_parquet(nodes)
    pl.DataFrame(
        [
            {
                "edge_id": "e1",
                "source_node_id": "GENE:TP53",
                "target_node_id": "TCGA-BRCA",
                "edge_type": "MUTATED_IN_CANCER",
                "weight": 0.4,
                "evidence_source": "TCGA",
            },
            {
                "edge_id": "e2",
                "source_node_id": "SAMPLE:S1",
                "target_node_id": "TCGA-BRCA",
                "edge_type": "BELONGS_TO_CANCER",
                "weight": 1.0,
                "evidence_source": "TCGA",
            },
        ]
    ).write_parquet(edges)

    summary = build_graph_node_metrics(nodes, edges, metrics_out, report_out)
    metrics = pl.read_parquet(metrics_out)
    brca = metrics.filter(pl.col("node_id") == "TCGA-BRCA").row(0, named=True)
    report = json.loads(report_out.read_text(encoding="utf-8"))

    assert summary["status"] == "passed"
    assert summary["metric_rows"] == 2
    assert brca["in_degree"] == 1
    assert brca["out_degree"] == 0
    assert brca["total_degree"] == 1
    assert brca["weighted_degree"] == 0.4
    assert report["edge_count"] == 1
    assert report["public_safe"] is True
    assert report["public_filter_audit"]["excluded_nodes"] == 1


def test_build_graph_node_metrics_handles_missing_nodes(tmp_path: Path) -> None:
    summary = build_graph_node_metrics(
        graph_nodes_path=tmp_path / "missing_nodes.parquet",
        graph_edges_path=tmp_path / "missing_edges.parquet",
        output_path=tmp_path / "metrics.parquet",
        report_path=tmp_path / "report.json",
    )

    report = json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))
    metrics = pl.read_parquet(tmp_path / "metrics.parquet")

    assert summary["status"] == "warning"
    assert metrics.is_empty()
    assert report["status"] == "warning"
