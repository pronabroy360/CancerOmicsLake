from __future__ import annotations

from pathlib import Path

import polars as pl


def _stub_results(query: str) -> dict[str, object]:
    return {
        "query": query,
        "results": [
            {
                "gene_id": "ENSG00000141510",
                "gene_symbol": "TP53",
                "gene_name": "tumor protein p53",
                "chromosome": "Unknown",
            }
        ],
    }


def search_genes(
    query: str,
    silver_dir: str | Path = "data/silver",
    limit: int = 20,
) -> dict[str, object]:
    term = query.strip().upper()
    if not term:
        return {"query": query, "results": []}

    root = Path(silver_dir)
    sources = [
        root / "silver_expression_tcga.parquet",
        root / "silver_expression_gtex.parquet",
        root / "silver_mutations.parquet",
    ]
    frames: list[pl.DataFrame] = []
    for path in sources:
        if not path.exists():
            continue
        df = pl.read_parquet(path)
        has_cols = {"gene_id", "gene_symbol"}.issubset(set(df.columns))
        if not df.is_empty() and has_cols:
            frames.append(
                df.select(
                    [
                        pl.col("gene_id").cast(pl.Utf8).alias("gene_id"),
                        pl.col("gene_symbol").cast(pl.Utf8).alias("gene_symbol"),
                    ]
                )
            )

    if not frames:
        return _stub_results(query)

    genes = pl.concat(frames, how="vertical").unique(subset=["gene_id", "gene_symbol"])
    filtered = genes.filter(
        pl.col("gene_symbol").str.to_uppercase().str.contains(term)
        | pl.col("gene_id").str.to_uppercase().str.contains(term)
    )
    if filtered.is_empty():
        return {"query": query, "results": []}

    rows = (
        filtered.sort("gene_symbol")
        .head(limit)
        .with_columns(
            [
                pl.col("gene_symbol").alias("gene_name"),
                pl.lit("Unknown").alias("chromosome"),
            ]
        )
        .select(["gene_id", "gene_symbol", "gene_name", "chromosome"])
        .to_dicts()
    )
    return {"query": query, "results": rows}
