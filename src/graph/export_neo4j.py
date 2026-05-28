from __future__ import annotations

import csv
from pathlib import Path
import re

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


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")


def _write_bulk_node_files(nodes_df: pl.DataFrame, bulk_dir: Path) -> dict[str, str]:
    if nodes_df.is_empty() or "node_label" not in nodes_df.columns:
        return {}

    files: dict[str, str] = {}
    labels = sorted({str(v) for v in nodes_df.get_column("node_label").drop_nulls().unique().to_list()})
    for label in labels:
        subset = (
            nodes_df.filter(pl.col("node_label") == label)
            .select(
                [
                    pl.col("node_id").cast(pl.Utf8).alias("id"),
                    (pl.col("name").cast(pl.Utf8) if "name" in nodes_df.columns else pl.lit("Unknown")).alias("name"),
                    (
                        pl.col("primary_site").cast(pl.Utf8)
                        if "primary_site" in nodes_df.columns
                        else pl.lit("Unknown")
                    ).alias("primary_site"),
                    (pl.col("source").cast(pl.Utf8) if "source" in nodes_df.columns else pl.lit("Unknown")).alias("source"),
                ]
            )
            .unique(subset=["id"])
        )
        out = bulk_dir / f"nodes_{_slug(label)}.csv"
        subset.write_csv(out)
        files[label] = out.name
    return files


def _write_bulk_edge_files(edges_df: pl.DataFrame, bulk_dir: Path) -> dict[str, str]:
    if edges_df.is_empty() or "edge_type" not in edges_df.columns:
        return {}

    files: dict[str, str] = {}
    edge_types = sorted({str(v) for v in edges_df.get_column("edge_type").drop_nulls().unique().to_list()})
    for edge_type in edge_types:
        subset = edges_df.filter(pl.col("edge_type") == edge_type).select(
            [
                pl.col("source_node_id").cast(pl.Utf8).alias("source_id"),
                pl.col("target_node_id").cast(pl.Utf8).alias("target_id"),
                pl.col("weight").cast(pl.Float64, strict=False).alias("weight"),
                (
                    pl.col("evidence_source").cast(pl.Utf8)
                    if "evidence_source" in edges_df.columns
                    else pl.lit("Unknown")
                ).alias("evidence_source"),
            ]
        )
        out = bulk_dir / f"edges_{_slug(edge_type)}.csv"
        subset.write_csv(out)
        files[edge_type] = out.name
    return files


def _write_import_cypher(node_files: dict[str, str], edge_files: dict[str, str], output_path: Path) -> Path:
    lines: list[str] = [
        "// CancerOmicsLake Neo4j bulk import script",
        "// Assumes CSV files are copied into Neo4j import directory.",
        "",
    ]

    for label, filename in sorted(node_files.items()):
        lines.extend(
            [
                f"LOAD CSV WITH HEADERS FROM 'file:///{filename}' AS row",
                f"MERGE (n:Entity:{label} {{node_id: row.id}})",
                "SET n.name = row.name,",
                "    n.primary_site = row.primary_site,",
                "    n.source = row.source;",
                "",
            ]
        )

    for edge_type, filename in sorted(edge_files.items()):
        lines.extend(
            [
                f"LOAD CSV WITH HEADERS FROM 'file:///{filename}' AS row",
                "MATCH (s:Entity {node_id: row.source_id})",
                "MATCH (t:Entity {node_id: row.target_id})",
                f"MERGE (s)-[r:{edge_type}]->(t)",
                "SET r.weight = toFloat(row.weight),",
                "    r.evidence_source = row.evidence_source;",
                "",
            ]
        )

    output_path.write_text("\n".join(lines), encoding="utf-8")
    return output_path


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

    bulk_dir = output_root / "bulk"
    bulk_dir.mkdir(parents=True, exist_ok=True)
    node_files = _write_bulk_node_files(nodes_df=nodes_df, bulk_dir=bulk_dir)
    edge_files = _write_bulk_edge_files(edges_df=edges_df, bulk_dir=bulk_dir)
    import_cypher = _write_import_cypher(
        node_files=node_files,
        edge_files=edge_files,
        output_path=output_root / "import_bulk.cypher",
    )

    return {
        "nodes_csv": str(nodes_csv),
        "edges_csv": str(edges_csv),
        "nodes_count": len(nodes_rows),
        "edges_count": len(edges_rows),
        "bulk_dir": str(bulk_dir),
        "bulk_node_file_count": len(node_files),
        "bulk_edge_file_count": len(edge_files),
        "import_cypher": str(import_cypher),
    }
