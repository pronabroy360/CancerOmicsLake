from __future__ import annotations

from src.processing.normalize_gene_ids import normalize_gene_id


def normalize_gtex_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    normalized_rows: list[dict[str, str]] = []
    for row in rows:
        mapped = normalize_gene_id(row["gene_id"])
        normalized_rows.append(
            {
                **row,
                **mapped,
            }
        )
    return normalized_rows
