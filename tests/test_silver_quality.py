from pathlib import Path

import json
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
            "submitter_id": ["sub-1"],
        }
    ).write_parquet(silver / "silver_patients.parquet")
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
            "md5sum": [""],
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
    pl.DataFrame(
        {
            "project_id": ["TCGA-BRCA", "TCGA-BRCA"],
            "case_id": ["c1", "c1"],
            "sample_id": ["s1", "s1"],
            "sample_type": ["Primary Tumor", "Primary Tumor"],
            "gene_id": ["", "ENSG2"],
            "gene_symbol": ["TP53", "EGFR"],
            "expression_value": [1.0, -1.0],
            "expression_unit": ["TPM", "TPM"],
            "log2_expression": [1.0, 0.0],
            "pipeline_workflow": ["STAR", "STAR"],
            "data_origin": ["stub", "stub"],
            "ingested_at": ["x", "x"],
        }
    ).write_parquet(silver / "silver_expression_tcga.parquet")
    pl.DataFrame(
        {
            "project_id": ["TCGA-BRCA", "TCGA-BRCA"],
            "case_id": ["c1", "c1"],
            "sample_id": ["s1", "s1"],
            "gene_id": ["ENSG1", "ENSG2"],
            "gene_symbol": ["", "TP53"],
            "variant_classification": ["Missense_Mutation", "Nonsense_Mutation"],
            "variant_type": ["SNP", "SNP"],
            "chromosome": ["17", "17"],
            "start_position": ["bad", "7673803"],
            "end_position": ["7673803", "bad"],
            "reference_allele": ["C", "G"],
            "tumor_seq_allele": ["T", "A"],
            "data_origin": ["stub", "stub"],
            "ingested_at": ["x", "x"],
        }
    ).write_parquet(silver / "silver_mutations.parquet")

    results = run_silver_quality_checks(silver)
    status_by_name = {r.check_name: r.status for r in results}
    assert status_by_name["silver_projects_null_project_id"] == "failed"
    assert status_by_name["silver_samples_duplicate_sample_id"] == "failed"
    assert status_by_name["silver_samples_patient_fk_integrity"] == "failed"
    assert status_by_name["silver_manifest_access_open_only"] == "failed"
    assert status_by_name["silver_manifest_md5_present"] == "failed"
    assert status_by_name["silver_expression_gtex_null_gene_id"] == "failed"
    assert status_by_name["silver_expression_gtex_non_negative"] == "failed"
    assert status_by_name["silver_expression_tcga_null_gene_id"] == "failed"
    assert status_by_name["silver_expression_tcga_non_negative"] == "failed"
    assert status_by_name["silver_mutations_null_gene_symbol"] == "failed"
    assert status_by_name["silver_mutations_start_position_valid_integer"] == "failed"
    assert status_by_name["silver_mutations_end_position_valid_integer"] == "failed"


def test_run_silver_quality_checks_download_integrity_detects_missing_and_md5_mismatch(tmp_path: Path) -> None:
    silver = tmp_path / "silver"
    bronze_tcga = tmp_path / "bronze" / "tcga"
    outputs = tmp_path / "outputs" / "reports"
    silver.mkdir(parents=True, exist_ok=True)
    bronze_tcga.mkdir(parents=True, exist_ok=True)
    outputs.mkdir(parents=True, exist_ok=True)

    pl.DataFrame(
        {
            "project_id": ["TCGA-BRCA", "TCGA-BRCA"],
            "primary_site": ["Breast", "Breast"],
            "disease_type": ["Adeno", "Adeno"],
        }
    ).write_parquet(silver / "silver_projects.parquet")
    pl.DataFrame(
        {
            "project_id": ["TCGA-BRCA"],
            "case_id": ["c1"],
            "submitter_id": ["sub-1"],
        }
    ).write_parquet(silver / "silver_patients.parquet")
    pl.DataFrame(
        {
            "project_id": ["TCGA-BRCA"],
            "case_id": ["c1"],
            "sample_id": ["s1"],
            "sample_type": ["Primary Tumor"],
        }
    ).write_parquet(silver / "silver_samples.parquet")
    pl.DataFrame(
        {
            "project_id": ["TCGA-BRCA", "TCGA-BRCA"],
            "case_id": ["c1", "c1"],
            "sample_id": ["s1", "s1"],
            "file_id": ["f1", "f2"],
            "file_name": ["missing.tsv", "mismatch.tsv"],
            "data_category": ["Transcriptome Profiling", "Transcriptome Profiling"],
            "data_type": ["Gene Expression Quantification", "Gene Expression Quantification"],
            "experimental_strategy": ["RNA-Seq", "RNA-Seq"],
            "workflow_type": ["STAR", "STAR"],
            "access": ["open", "open"],
            "file_size": [10, 10],
            "md5sum": ["abc", "00000000000000000000000000000000"],
            "ingested_at": ["x", "x"],
        }
    ).write_parquet(silver / "silver_file_manifest.parquet")
    pl.DataFrame(
        schema={
            "gtex_sample_id": pl.Utf8,
            "tissue_site": pl.Utf8,
            "tissue_detail": pl.Utf8,
            "gene_id": pl.Utf8,
            "gene_symbol": pl.Utf8,
            "expression_value": pl.Float64,
            "expression_unit": pl.Utf8,
            "log2_expression": pl.Float64,
            "source_version": pl.Utf8,
            "data_origin": pl.Utf8,
            "ingested_at": pl.Utf8,
        }
    ).write_parquet(silver / "silver_expression_gtex.parquet")
    pl.DataFrame(
        schema={
            "project_id": pl.Utf8,
            "case_id": pl.Utf8,
            "sample_id": pl.Utf8,
            "sample_type": pl.Utf8,
            "gene_id": pl.Utf8,
            "gene_symbol": pl.Utf8,
            "expression_value": pl.Float64,
            "expression_unit": pl.Utf8,
            "log2_expression": pl.Float64,
            "pipeline_workflow": pl.Utf8,
            "data_origin": pl.Utf8,
            "ingested_at": pl.Utf8,
        }
    ).write_parquet(silver / "silver_expression_tcga.parquet")
    pl.DataFrame(
        schema={
            "project_id": pl.Utf8,
            "case_id": pl.Utf8,
            "sample_id": pl.Utf8,
            "gene_id": pl.Utf8,
            "gene_symbol": pl.Utf8,
            "variant_classification": pl.Utf8,
            "variant_type": pl.Utf8,
            "chromosome": pl.Utf8,
            "start_position": pl.Int64,
            "end_position": pl.Int64,
            "reference_allele": pl.Utf8,
            "tumor_seq_allele": pl.Utf8,
            "data_origin": pl.Utf8,
            "ingested_at": pl.Utf8,
        }
    ).write_parquet(silver / "silver_mutations.parquet")

    mismatch_file = bronze_tcga / "TCGA-BRCA" / "expression" / "mismatch.tsv"
    mismatch_file.parent.mkdir(parents=True, exist_ok=True)
    mismatch_file.write_text("abc", encoding="utf-8")

    report = outputs / "tcga_download_report.json"
    report.write_text(
        json.dumps({"pipeline_run_id": "x", "status": "completed", "total_candidates": 2}),
        encoding="utf-8",
    )

    results = run_silver_quality_checks(
        silver_dir=silver,
        bronze_tcga_root=bronze_tcga,
        download_report_path=report,
    )
    by_name = {r.check_name: r for r in results}
    assert by_name["bronze_tcga_download_file_presence"].status == "failed"
    assert by_name["bronze_tcga_download_file_presence"].failed_rows == 1
    assert by_name["bronze_tcga_download_checksum_match"].status == "failed"
    assert by_name["bronze_tcga_download_checksum_match"].failed_rows == 1
