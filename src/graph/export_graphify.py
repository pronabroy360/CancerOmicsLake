from __future__ import annotations

from pathlib import Path

from src.graph.export_neo4j import export_neo4j_csv


def export_graphify_csv(rows: list[dict[str, str]], output_path: str | Path) -> Path:
    return export_neo4j_csv(rows, output_path)
