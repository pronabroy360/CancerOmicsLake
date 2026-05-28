from pathlib import Path

import polars as pl

from src.analytics.gene_search import search_genes


def test_search_genes_from_silver_files(tmp_path: Path) -> None:
    silver = tmp_path / "silver"
    silver.mkdir(parents=True, exist_ok=True)

    pl.DataFrame(
        {
            "gene_id": ["ENSG00000141510", "ENSG00000146648"],
            "gene_symbol": ["TP53", "EGFR"],
            "project_id": ["TCGA-BRCA", "TCGA-LUAD"],
            "sample_id": ["s1", "s2"],
            "expression_value": [1.0, 2.0],
        }
    ).write_parquet(silver / "silver_expression_tcga.parquet")
    pl.DataFrame(
        {
            "gene_id": ["ENSG00000141510"],
            "gene_symbol": ["TP53"],
            "gtex_sample_id": ["g1"],
            "tissue_site": ["Lung"],
            "expression_value": [1.0],
        }
    ).write_parquet(silver / "silver_expression_gtex.parquet")
    pl.DataFrame(
        {
            "gene_id": ["ENSG00000157764"],
            "gene_symbol": ["BRAF"],
            "sample_id": ["m1"],
            "project_id": ["TCGA-COAD"],
            "start_position": [1],
            "end_position": [1],
        }
    ).write_parquet(silver / "silver_mutations.parquet")

    payload = search_genes("tp5", silver)
    assert payload["query"] == "tp5"
    assert len(payload["results"]) == 1
    assert payload["results"][0]["gene_symbol"] == "TP53"


def test_search_genes_fallback_when_missing(tmp_path: Path) -> None:
    payload = search_genes("tp53", tmp_path / "missing")
    assert payload["query"] == "tp53"
    assert len(payload["results"]) >= 1
