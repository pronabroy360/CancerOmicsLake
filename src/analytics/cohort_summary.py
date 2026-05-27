from __future__ import annotations

from pathlib import Path

import polars as pl


def cohort_summary_stub() -> dict[str, int]:
    return {
        "tcga_projects": 3,
        "tcga_samples": 12,
        "gtex_samples": 4,
        "genes": 1,
        "mutation_records": 1,
        "expression_records": 4,
    }


def cohort_summary_from_gold(gold_path: str | Path = "data/gold/gold_cohort_summary.parquet") -> dict[str, int]:
    path = Path(gold_path)
    if not path.exists():
        return cohort_summary_stub()
    df = pl.read_parquet(path)
    if df.is_empty():
        return cohort_summary_stub()

    row = df.row(0, named=True)
    return {
        "tcga_projects": int(row.get("tcga_project_count", 0)),
        "tcga_samples": int(row.get("tcga_sample_count", 0)),
        "gtex_samples": int(row.get("gtex_expression_sample_count", 0)),
        "genes": int(row.get("gene_count", 0)),
        "mutation_records": int(row.get("mutation_record_count", 0)),
        "expression_records": int(
            row.get("gtex_expression_row_count", 0) + row.get("tcga_expression_row_count", 0)
        ),
    }
