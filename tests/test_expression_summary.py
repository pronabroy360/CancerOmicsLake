from pathlib import Path

import polars as pl

from src.analytics.expression_summary import expression_by_gene


def test_expression_by_gene_reads_silver_tables(tmp_path: Path) -> None:
    silver_dir = tmp_path / "silver"
    silver_dir.mkdir(parents=True, exist_ok=True)

    pl.DataFrame(
        {
            "project_id": ["TCGA-BRCA", "TCGA-BRCA", "TCGA-LUAD"],
            "case_id": ["c1", "c2", "c3"],
            "sample_id": ["s1", "s2", "s3"],
            "sample_type": ["Primary Tumor", "Primary Tumor", "Primary Tumor"],
            "gene_id": ["ENSG1", "ENSG1", "ENSG1"],
            "gene_symbol": ["TP53", "TP53", "TP53"],
            "expression_value": [8.0, 12.0, 6.0],
            "expression_unit": ["TPM", "TPM", "TPM"],
            "log2_expression": [3.17, 3.70, 2.81],
            "pipeline_workflow": ["STAR", "STAR", "STAR"],
            "data_origin": ["stub", "stub", "stub"],
            "ingested_at": ["x", "x", "x"],
        }
    ).write_parquet(silver_dir / "silver_expression_tcga.parquet")

    pl.DataFrame(
        {
            "gtex_sample_id": ["g1", "g2"],
            "tissue_site": ["Lung", "Breast - Mammary Tissue"],
            "tissue_detail": ["Lung", "Breast - Mammary Tissue"],
            "gene_id": ["ENSG1", "ENSG1"],
            "gene_symbol": ["TP53", "TP53"],
            "expression_value": [2.0, 4.0],
            "expression_unit": ["TPM", "TPM"],
            "log2_expression": [1.58, 2.32],
            "source_version": ["v8", "v8"],
            "data_origin": ["stub", "stub"],
            "ingested_at": ["x", "x"],
        }
    ).write_parquet(silver_dir / "silver_expression_gtex.parquet")

    payload = expression_by_gene("tp53", silver_dir=silver_dir)
    assert payload["gene_symbol"] == "TP53"
    assert len(payload["rows"]) == 4
    assert {row["source"] for row in payload["rows"]} == {"TCGA", "GTEx"}


def test_expression_by_gene_falls_back_when_silver_missing(tmp_path: Path) -> None:
    payload = expression_by_gene("tp53", silver_dir=tmp_path / "missing")
    assert payload["gene_symbol"] == "TP53"
    assert len(payload["rows"]) >= 1
