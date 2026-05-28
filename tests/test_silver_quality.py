from pathlib import Path

import polars as pl

from src.quality.checks import run_silver_quality_checks


def test_run_silver_quality_checks_detects_failures(tmp_path: Path) -> None:
    silver = tmp_path / "silver"
    silver.mkdir(parents=True, exist_ok=True)

    pl.DataFrame(
        {
            "project_id": ["TCGA-BRCA", ""],
            "primary_site": ["Breast", "Lung"],
            "disease_type": ["Adeno", "Adeno"],
        }
    ).write_parquet(silver / "silver_projects.parquet")
    pl.DataFrame(
        {
            "project_id": ["TCGA-BRCA", "TCGA-BRCA"],
            "case_id": ["c1", "c2"],
            "sample_id": ["s1", "s1"],
            "sample_type": ["Primary Tumor", "Primary Tumor"],
        }
    ).write_parquet(silver / "silver_samples.parquet")
    pl.DataFrame(
        {
            "project_id": ["TCGA-BRCA"],
            "case_id": ["c1"],
            "sample_id": ["s1"],
            "file_id": ["f1"],
            "file_name": ["x.tsv"],
            "data_category": ["Clinical"],
            "data_type": ["Supplement"],
            "experimental_strategy": ["RNA-Seq"],
            "workflow_type": ["STAR"],
            "access": ["controlled"],
            "file_size": [10],
            "md5sum": ["abc"],
            "ingested_at": ["x"],
        }
    ).write_parquet(silver / "silver_file_manifest.parquet")
    pl.DataFrame(
        {
            "gtex_sample_id": ["g1", "g2"],
            "tissue_site": ["Lung", "Lung"],
            "tissue_detail": ["Lung", "Lung"],
            "gene_id": ["", "ENSG2"],
            "gene_symbol": ["TP53", "EGFR"],
            "expression_value": [1.0, -1.0],
            "expression_unit": ["TPM", "TPM"],
            "log2_expression": [1.0, 0.0],
            "source_version": ["v8", "v8"],
            "data_origin": ["stub", "stub"],
            "ingested_at": ["x", "x"],
        }
    ).write_parquet(silver / "silver_expression_gtex.parquet")

    results = run_silver_quality_checks(silver)
    status_by_name = {r.check_name: r.status for r in results}
    assert status_by_name["silver_projects_null_project_id"] == "failed"
    assert status_by_name["silver_samples_duplicate_sample_id"] == "failed"
    assert status_by_name["silver_manifest_access_open_only"] == "failed"
    assert status_by_name["silver_expression_gtex_null_gene_id"] == "failed"
    assert status_by_name["silver_expression_gtex_non_negative"] == "failed"
