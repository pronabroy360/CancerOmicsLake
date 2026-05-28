from __future__ import annotations

from pathlib import Path

import polars as pl


def mutation_frequency_by_gene_stub(gene_symbol: str) -> dict[str, object]:
    return {
        "gene_symbol": gene_symbol.upper(),
        "rows": [
            {"cancer_type": "TCGA-LUAD", "mutation_frequency": 0.25},
            {"cancer_type": "TCGA-COAD", "mutation_frequency": 0.18},
        ],
    }


def mutation_frequency_by_gene(
    gene_symbol: str,
    gold_path: str | Path = "data/gold/gold_mutation_frequency_by_gene.parquet",
) -> dict[str, object]:
    path = Path(gold_path)
    if not path.exists():
        return mutation_frequency_by_gene_stub(gene_symbol)

    df = pl.read_parquet(path)
    if df.is_empty() or "gene_symbol" not in df.columns:
        return mutation_frequency_by_gene_stub(gene_symbol)

    filtered = df.filter(pl.col("gene_symbol").cast(pl.Utf8).str.to_uppercase() == gene_symbol.upper())
    if filtered.is_empty():
        return {"gene_symbol": gene_symbol.upper(), "rows": []}

    rows = filtered.sort("mutation_frequency", descending=True).to_dicts()
    return {"gene_symbol": gene_symbol.upper(), "rows": rows}


def mutation_frequency_by_cancer(
    project_id: str,
    gold_path: str | Path = "data/gold/gold_mutation_frequency_by_gene.parquet",
    limit: int = 20,
) -> dict[str, object]:
    path = Path(gold_path)
    if not path.exists():
        return {"project_id": project_id, "top_genes": mutation_frequency_by_gene_stub("TP53")["rows"]}

    df = pl.read_parquet(path)
    if df.is_empty() or "cancer_type" not in df.columns:
        return {"project_id": project_id, "top_genes": []}

    filtered = df.filter(pl.col("cancer_type") == project_id).sort("mutation_frequency", descending=True).head(limit)
    return {"project_id": project_id, "top_genes": filtered.to_dicts()}
