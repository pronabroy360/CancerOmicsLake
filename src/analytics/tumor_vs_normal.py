from __future__ import annotations

from pathlib import Path

import polars as pl


def tumor_vs_normal_stub(gene_symbol: str) -> dict[str, object]:
    return {
        "gene_symbol": gene_symbol.upper(),
        "warning": "Exploratory cross-dataset comparison; batch effects may be present.",
        "rows": [
            {
                "cancer_type": "TCGA-BRCA",
                "median_tcga_tumor_expression": 2.3,
                "median_gtex_normal_expression": 1.9,
                "log2_fold_change": 0.4,
            }
        ],
    }


def tumor_vs_normal_by_gene(
    gene_symbol: str,
    gold_path: str | Path = "data/gold/gold_tumor_vs_normal_expression.parquet",
) -> dict[str, object]:
    path = Path(gold_path)
    if not path.exists():
        return tumor_vs_normal_stub(gene_symbol)

    df = pl.read_parquet(path)
    if df.is_empty() or "gene_symbol" not in df.columns:
        return tumor_vs_normal_stub(gene_symbol)

    filtered = df.filter(pl.col("gene_symbol").cast(pl.Utf8).str.to_uppercase() == gene_symbol.upper())
    rows = filtered.sort("log2_fold_change", descending=True).to_dicts() if not filtered.is_empty() else []
    return {
        "gene_symbol": gene_symbol.upper(),
        "warning": "Exploratory cross-dataset comparison; batch effects may be present.",
        "rows": rows,
    }
