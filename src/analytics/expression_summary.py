from __future__ import annotations

from pathlib import Path

import polars as pl


def expression_by_gene_stub(gene_symbol: str) -> dict[str, object]:
    return {
        "gene_symbol": gene_symbol.upper(),
        "rows": [
            {"project_id": "TCGA-BRCA", "median_expression": 2.31},
            {"project_id": "TCGA-LUAD", "median_expression": 2.02},
            {"project_id": "TCGA-COAD", "median_expression": 1.89},
        ],
    }


def expression_by_gene(
    gene_symbol: str,
    silver_dir: str | Path = "data/silver",
) -> dict[str, object]:
    root = Path(silver_dir)
    tcga_path = root / "silver_expression_tcga.parquet"
    gtex_path = root / "silver_expression_gtex.parquet"
    if not tcga_path.exists() and not gtex_path.exists():
        return expression_by_gene_stub(gene_symbol)

    rows: list[dict[str, object]] = []
    target = gene_symbol.upper()

    if tcga_path.exists():
        tcga = pl.read_parquet(tcga_path)
        if not tcga.is_empty() and {"gene_symbol", "project_id", "expression_value"}.issubset(set(tcga.columns)):
            tcga_rows = (
                tcga.filter(pl.col("gene_symbol").cast(pl.Utf8).str.to_uppercase() == target)
                .group_by("project_id")
                .agg(
                    [
                        pl.col("expression_value").median().alias("median_expression"),
                        pl.col("expression_value").mean().alias("mean_expression"),
                        pl.col("sample_id").n_unique().cast(pl.Int64).alias("sample_count"),
                    ]
                )
                .sort("median_expression", descending=True)
                .to_dicts()
            )
            rows.extend(
                [
                    {
                        "source": "TCGA",
                        "project_id": r["project_id"],
                        "tissue_site": None,
                        "median_expression": float(r["median_expression"]),
                        "mean_expression": float(r["mean_expression"]),
                        "sample_count": int(r["sample_count"]),
                    }
                    for r in tcga_rows
                ]
            )

    if gtex_path.exists():
        gtex = pl.read_parquet(gtex_path)
        if not gtex.is_empty() and {"gene_symbol", "tissue_site", "expression_value"}.issubset(set(gtex.columns)):
            gtex_rows = (
                gtex.filter(pl.col("gene_symbol").cast(pl.Utf8).str.to_uppercase() == target)
                .group_by("tissue_site")
                .agg(
                    [
                        pl.col("expression_value").median().alias("median_expression"),
                        pl.col("expression_value").mean().alias("mean_expression"),
                        pl.col("gtex_sample_id").n_unique().cast(pl.Int64).alias("sample_count"),
                    ]
                )
                .sort("median_expression", descending=True)
                .to_dicts()
            )
            rows.extend(
                [
                    {
                        "source": "GTEx",
                        "project_id": None,
                        "tissue_site": r["tissue_site"],
                        "median_expression": float(r["median_expression"]),
                        "mean_expression": float(r["mean_expression"]),
                        "sample_count": int(r["sample_count"]),
                    }
                    for r in gtex_rows
                ]
            )

    return {"gene_symbol": target, "rows": rows}
