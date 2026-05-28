from pathlib import Path

import polars as pl

from src.analytics.tumor_vs_normal import tumor_vs_normal_by_gene


def test_tumor_vs_normal_by_gene_reads_gold_table(tmp_path: Path) -> None:
    gold_file = tmp_path / "gold_tumor_vs_normal_expression.parquet"
    pl.DataFrame(
        {
            "gene_symbol": ["TP53", "TP53", "EGFR"],
            "cancer_type": ["TCGA-BRCA", "TCGA-LUAD", "TCGA-LUAD"],
            "median_tcga_tumor_expression": [10.0, 8.0, 6.0],
            "median_gtex_normal_expression": [2.0, 2.0, 2.0],
            "mean_tcga_tumor_expression": [10.0, 8.0, 6.0],
            "mean_gtex_normal_expression": [2.0, 2.0, 2.0],
            "log2_fold_change": [1.87, 1.58, 1.22],
            "sample_count_tumor": [10, 8, 7],
            "sample_count_normal": [20, 20, 20],
        }
    ).write_parquet(gold_file)

    payload = tumor_vs_normal_by_gene("tp53", gold_file)
    assert payload["gene_symbol"] == "TP53"
    assert len(payload["rows"]) == 2
    assert payload["rows"][0]["log2_fold_change"] >= payload["rows"][1]["log2_fold_change"]


def test_tumor_vs_normal_by_gene_falls_back_to_stub(tmp_path: Path) -> None:
    payload = tumor_vs_normal_by_gene("tp53", tmp_path / "missing.parquet")
    assert payload["gene_symbol"] == "TP53"
    assert len(payload["rows"]) >= 1
