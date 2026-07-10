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
            "expression_unit": ["TPM", "RPKM"],
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
            "expression_unit": ["TPM", "UNKNOWN"],
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
    assert status_by_name["silver_expression_tcga_unit_supported"] == "failed"
    assert status_by_name["silver_expression_gtex_unit_supported"] == "failed"
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


def test_run_silver_quality_checks_download_integrity_warns_in_partial_mode(tmp_path: Path) -> None:
    silver = tmp_path / "silver"
    bronze_tcga = tmp_path / "bronze" / "tcga"
    outputs = tmp_path / "outputs" / "reports"
    silver.mkdir(parents=True, exist_ok=True)
    bronze_tcga.mkdir(parents=True, exist_ok=True)
    outputs.mkdir(parents=True, exist_ok=True)

    pl.DataFrame(
        {"project_id": ["TCGA-BRCA"], "primary_site": ["Breast"], "disease_type": ["Adeno"]}
    ).write_parquet(silver / "silver_projects.parquet")
    pl.DataFrame(
        {"project_id": ["TCGA-BRCA"], "case_id": ["c1"], "submitter_id": ["sub-1"]}
    ).write_parquet(silver / "silver_patients.parquet")
    pl.DataFrame(
        {"project_id": ["TCGA-BRCA"], "case_id": ["c1"], "sample_id": ["s1"], "sample_type": ["Primary Tumor"]}
    ).write_parquet(silver / "silver_samples.parquet")
    pl.DataFrame(
        {
            "project_id": ["TCGA-BRCA"],
            "case_id": ["c1"],
            "sample_id": ["s1"],
            "file_id": ["f1"],
            "file_name": ["missing.tsv"],
            "data_category": ["Transcriptome Profiling"],
            "data_type": ["Gene Expression Quantification"],
            "experimental_strategy": ["RNA-Seq"],
            "workflow_type": ["STAR"],
            "access": ["open"],
            "file_size": [10],
            "md5sum": ["abc"],
            "ingested_at": ["x"],
        }
    ).write_parquet(silver / "silver_file_manifest.parquet")
    pl.DataFrame(schema={"gtex_sample_id": pl.Utf8, "tissue_site": pl.Utf8, "tissue_detail": pl.Utf8, "gene_id": pl.Utf8, "gene_symbol": pl.Utf8, "expression_value": pl.Float64, "expression_unit": pl.Utf8, "log2_expression": pl.Float64, "source_version": pl.Utf8, "data_origin": pl.Utf8, "ingested_at": pl.Utf8}).write_parquet(silver / "silver_expression_gtex.parquet")
    pl.DataFrame(schema={"project_id": pl.Utf8, "case_id": pl.Utf8, "sample_id": pl.Utf8, "sample_type": pl.Utf8, "gene_id": pl.Utf8, "gene_symbol": pl.Utf8, "expression_value": pl.Float64, "expression_unit": pl.Utf8, "log2_expression": pl.Float64, "pipeline_workflow": pl.Utf8, "data_origin": pl.Utf8, "ingested_at": pl.Utf8}).write_parquet(silver / "silver_expression_tcga.parquet")
    pl.DataFrame(schema={"project_id": pl.Utf8, "case_id": pl.Utf8, "sample_id": pl.Utf8, "gene_id": pl.Utf8, "gene_symbol": pl.Utf8, "variant_classification": pl.Utf8, "variant_type": pl.Utf8, "chromosome": pl.Utf8, "start_position": pl.Int64, "end_position": pl.Int64, "reference_allele": pl.Utf8, "tumor_seq_allele": pl.Utf8, "data_origin": pl.Utf8, "ingested_at": pl.Utf8}).write_parquet(silver / "silver_mutations.parquet")

    report = outputs / "tcga_download_report.json"
    report.write_text(
        json.dumps(
            {
                "pipeline_run_id": "x",
                "status": "completed_with_failures",
                "total_candidates": 100,
                "attempted_downloads": 3,
                "max_downloads": 3,
            }
        ),
        encoding="utf-8",
    )

    results = run_silver_quality_checks(
        silver_dir=silver,
        bronze_tcga_root=bronze_tcga,
        download_report_path=report,
    )
    by_name = {r.check_name: r for r in results}
    assert by_name["bronze_tcga_download_file_presence"].status == "warning"


def test_run_silver_quality_checks_download_integrity_warns_when_download_completed_with_failures(tmp_path: Path) -> None:
    silver = tmp_path / "silver"
    bronze_tcga = tmp_path / "bronze" / "tcga"
    outputs = tmp_path / "outputs" / "reports"
    silver.mkdir(parents=True, exist_ok=True)
    bronze_tcga.mkdir(parents=True, exist_ok=True)
    outputs.mkdir(parents=True, exist_ok=True)

    pl.DataFrame(
        {"project_id": ["TCGA-BRCA"], "primary_site": ["Breast"], "disease_type": ["Adeno"]}
    ).write_parquet(silver / "silver_projects.parquet")
    pl.DataFrame(
        {"project_id": ["TCGA-BRCA"], "case_id": ["c1"], "submitter_id": ["sub-1"]}
    ).write_parquet(silver / "silver_patients.parquet")
    pl.DataFrame(
        {"project_id": ["TCGA-BRCA"], "case_id": ["c1"], "sample_id": ["s1"], "sample_type": ["Primary Tumor"]}
    ).write_parquet(silver / "silver_samples.parquet")
    pl.DataFrame(
        {
            "project_id": ["TCGA-BRCA"],
            "case_id": ["c1"],
            "sample_id": ["s1"],
            "file_id": ["f1"],
            "file_name": ["missing.tsv"],
            "data_category": ["Transcriptome Profiling"],
            "data_type": ["Gene Expression Quantification"],
            "experimental_strategy": ["RNA-Seq"],
            "workflow_type": ["STAR"],
            "access": ["open"],
            "file_size": [10],
            "md5sum": [""],
            "ingested_at": ["x"],
        }
    ).write_parquet(silver / "silver_file_manifest.parquet")
    pl.DataFrame(schema={"gtex_sample_id": pl.Utf8, "tissue_site": pl.Utf8, "tissue_detail": pl.Utf8, "gene_id": pl.Utf8, "gene_symbol": pl.Utf8, "expression_value": pl.Float64, "expression_unit": pl.Utf8, "log2_expression": pl.Float64, "source_version": pl.Utf8, "data_origin": pl.Utf8, "ingested_at": pl.Utf8}).write_parquet(silver / "silver_expression_gtex.parquet")
    pl.DataFrame(schema={"project_id": pl.Utf8, "case_id": pl.Utf8, "sample_id": pl.Utf8, "sample_type": pl.Utf8, "gene_id": pl.Utf8, "gene_symbol": pl.Utf8, "expression_value": pl.Float64, "expression_unit": pl.Utf8, "log2_expression": pl.Float64, "pipeline_workflow": pl.Utf8, "data_origin": pl.Utf8, "ingested_at": pl.Utf8}).write_parquet(silver / "silver_expression_tcga.parquet")
    pl.DataFrame(schema={"project_id": pl.Utf8, "case_id": pl.Utf8, "sample_id": pl.Utf8, "gene_id": pl.Utf8, "gene_symbol": pl.Utf8, "variant_classification": pl.Utf8, "variant_type": pl.Utf8, "chromosome": pl.Utf8, "start_position": pl.Int64, "end_position": pl.Int64, "reference_allele": pl.Utf8, "tumor_seq_allele": pl.Utf8, "data_origin": pl.Utf8, "ingested_at": pl.Utf8}).write_parquet(silver / "silver_mutations.parquet")

    report = outputs / "tcga_download_report.json"
    report.write_text(
        json.dumps(
            {
                "pipeline_run_id": "x",
                "status": "completed_with_failures",
                "total_candidates": 1,
                "attempted_downloads": 1,
            }
        ),
        encoding="utf-8",
    )

    results = run_silver_quality_checks(
        silver_dir=silver,
        bronze_tcga_root=bronze_tcga,
        download_report_path=report,
    )
    by_name = {r.check_name: r for r in results}
    assert by_name["bronze_tcga_download_file_presence"].status == "warning"


def test_run_silver_quality_checks_download_integrity_respects_allowed_subdirs(tmp_path: Path) -> None:
    silver = tmp_path / "silver"
    bronze_tcga = tmp_path / "bronze" / "tcga"
    outputs = tmp_path / "outputs" / "reports"
    silver.mkdir(parents=True, exist_ok=True)
    bronze_tcga.mkdir(parents=True, exist_ok=True)
    outputs.mkdir(parents=True, exist_ok=True)

    pl.DataFrame(
        {"project_id": ["TCGA-BRCA"], "primary_site": ["Breast"], "disease_type": ["Adeno"]}
    ).write_parquet(silver / "silver_projects.parquet")
    pl.DataFrame(
        {"project_id": ["TCGA-BRCA"], "case_id": ["c1"], "submitter_id": ["sub-1"]}
    ).write_parquet(silver / "silver_patients.parquet")
    pl.DataFrame(
        {"project_id": ["TCGA-BRCA"], "case_id": ["c1"], "sample_id": ["s1"], "sample_type": ["Primary Tumor"]}
    ).write_parquet(silver / "silver_samples.parquet")
    pl.DataFrame(
        {
            "project_id": ["TCGA-BRCA", "TCGA-BRCA"],
            "case_id": ["c1", "c1"],
            "sample_id": ["s1", "s1"],
            "file_id": ["f1", "f2"],
            "file_name": ["present.tsv", "missing_clinical.tsv"],
            "data_category": ["Transcriptome Profiling", "Clinical"],
            "data_type": ["Gene Expression Quantification", "Clinical Supplement"],
            "experimental_strategy": ["RNA-Seq", "NA"],
            "workflow_type": ["STAR", "NA"],
            "access": ["open", "open"],
            "file_size": [10, 10],
            "md5sum": ["", ""],
            "ingested_at": ["x", "x"],
        }
    ).write_parquet(silver / "silver_file_manifest.parquet")
    pl.DataFrame(schema={"gtex_sample_id": pl.Utf8, "tissue_site": pl.Utf8, "tissue_detail": pl.Utf8, "gene_id": pl.Utf8, "gene_symbol": pl.Utf8, "expression_value": pl.Float64, "expression_unit": pl.Utf8, "log2_expression": pl.Float64, "source_version": pl.Utf8, "data_origin": pl.Utf8, "ingested_at": pl.Utf8}).write_parquet(silver / "silver_expression_gtex.parquet")
    pl.DataFrame(schema={"project_id": pl.Utf8, "case_id": pl.Utf8, "sample_id": pl.Utf8, "sample_type": pl.Utf8, "gene_id": pl.Utf8, "gene_symbol": pl.Utf8, "expression_value": pl.Float64, "expression_unit": pl.Utf8, "log2_expression": pl.Float64, "pipeline_workflow": pl.Utf8, "data_origin": pl.Utf8, "ingested_at": pl.Utf8}).write_parquet(silver / "silver_expression_tcga.parquet")
    pl.DataFrame(schema={"project_id": pl.Utf8, "case_id": pl.Utf8, "sample_id": pl.Utf8, "gene_id": pl.Utf8, "gene_symbol": pl.Utf8, "variant_classification": pl.Utf8, "variant_type": pl.Utf8, "chromosome": pl.Utf8, "start_position": pl.Int64, "end_position": pl.Int64, "reference_allele": pl.Utf8, "tumor_seq_allele": pl.Utf8, "data_origin": pl.Utf8, "ingested_at": pl.Utf8}).write_parquet(silver / "silver_mutations.parquet")

    (bronze_tcga / "TCGA-BRCA" / "expression").mkdir(parents=True, exist_ok=True)
    (bronze_tcga / "TCGA-BRCA" / "expression" / "present.tsv").write_text("ok", encoding="utf-8")

    report = outputs / "tcga_download_report.json"
    report.write_text(
        json.dumps(
            {
                "pipeline_run_id": "x",
                "status": "completed",
                "total_candidates": 1,
                "allowed_data_subdirs": ["expression", "mutations"],
            }
        ),
        encoding="utf-8",
    )

    results = run_silver_quality_checks(
        silver_dir=silver,
        bronze_tcga_root=bronze_tcga,
        download_report_path=report,
    )
    by_name = {r.check_name: r for r in results}
    assert by_name["bronze_tcga_download_file_presence"].status == "passed"
    assert by_name["bronze_tcga_download_file_presence"].failed_rows == 0


def test_run_silver_quality_checks_download_integrity_uses_selected_files_for_capped_runs(tmp_path: Path) -> None:
    silver = tmp_path / "silver"
    bronze_tcga = tmp_path / "bronze" / "tcga"
    outputs = tmp_path / "outputs" / "reports"
    silver.mkdir(parents=True, exist_ok=True)
    bronze_tcga.mkdir(parents=True, exist_ok=True)
    outputs.mkdir(parents=True, exist_ok=True)

    pl.DataFrame(
        {"project_id": ["TCGA-BRCA"], "primary_site": ["Breast"], "disease_type": ["Adeno"]}
    ).write_parquet(silver / "silver_projects.parquet")
    pl.DataFrame(
        {"project_id": ["TCGA-BRCA"], "case_id": ["c1"], "submitter_id": ["sub-1"]}
    ).write_parquet(silver / "silver_patients.parquet")
    pl.DataFrame(
        {"project_id": ["TCGA-BRCA"], "case_id": ["c1"], "sample_id": ["s1"], "sample_type": ["Primary Tumor"]}
    ).write_parquet(silver / "silver_samples.parquet")
    pl.DataFrame(
        {
            "project_id": ["TCGA-BRCA", "TCGA-BRCA"],
            "case_id": ["c1", "c1"],
            "sample_id": ["s1", "s1"],
            "file_id": ["selected", "unselected"],
            "file_name": ["selected.tsv", "unselected.tsv"],
            "data_category": ["Transcriptome Profiling", "Transcriptome Profiling"],
            "data_type": ["Gene Expression Quantification", "Gene Expression Quantification"],
            "experimental_strategy": ["RNA-Seq", "RNA-Seq"],
            "workflow_type": ["STAR", "STAR"],
            "access": ["open", "open"],
            "file_size": [10, 10],
            "md5sum": ["", ""],
            "ingested_at": ["x", "x"],
        }
    ).write_parquet(silver / "silver_file_manifest.parquet")
    pl.DataFrame(schema={"gtex_sample_id": pl.Utf8, "tissue_site": pl.Utf8, "tissue_detail": pl.Utf8, "gene_id": pl.Utf8, "gene_symbol": pl.Utf8, "expression_value": pl.Float64, "expression_unit": pl.Utf8, "log2_expression": pl.Float64, "source_version": pl.Utf8, "data_origin": pl.Utf8, "ingested_at": pl.Utf8}).write_parquet(silver / "silver_expression_gtex.parquet")
    pl.DataFrame(schema={"project_id": pl.Utf8, "case_id": pl.Utf8, "sample_id": pl.Utf8, "sample_type": pl.Utf8, "gene_id": pl.Utf8, "gene_symbol": pl.Utf8, "expression_value": pl.Float64, "expression_unit": pl.Utf8, "log2_expression": pl.Float64, "pipeline_workflow": pl.Utf8, "data_origin": pl.Utf8, "ingested_at": pl.Utf8}).write_parquet(silver / "silver_expression_tcga.parquet")
    pl.DataFrame(schema={"project_id": pl.Utf8, "case_id": pl.Utf8, "sample_id": pl.Utf8, "gene_id": pl.Utf8, "gene_symbol": pl.Utf8, "variant_classification": pl.Utf8, "variant_type": pl.Utf8, "chromosome": pl.Utf8, "start_position": pl.Int64, "end_position": pl.Int64, "reference_allele": pl.Utf8, "tumor_seq_allele": pl.Utf8, "data_origin": pl.Utf8, "ingested_at": pl.Utf8}).write_parquet(silver / "silver_mutations.parquet")

    (bronze_tcga / "TCGA-BRCA" / "expression").mkdir(parents=True, exist_ok=True)
    (bronze_tcga / "TCGA-BRCA" / "expression" / "selected.tsv").write_text("ok", encoding="utf-8")

    report = outputs / "tcga_download_report.json"
    report.write_text(
        json.dumps(
            {
                "pipeline_run_id": "x",
                "status": "completed",
                "total_candidates": 2,
                "selected_candidates": 1,
                "allowed_data_subdirs": ["expression"],
                "selected_files": [
                    {
                        "project_id": "TCGA-BRCA",
                        "file_name": "selected.tsv",
                        "data_subdir": "expression",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    results = run_silver_quality_checks(
        silver_dir=silver,
        bronze_tcga_root=bronze_tcga,
        download_report_path=report,
    )
    by_name = {r.check_name: r for r in results}
    assert by_name["bronze_tcga_download_file_presence"].status == "passed"
    assert by_name["bronze_tcga_download_file_presence"].failed_rows == 0


def test_run_silver_quality_checks_ignores_unknown_sample_id_duplicates(tmp_path: Path) -> None:
    silver = tmp_path / "silver"
    silver.mkdir(parents=True, exist_ok=True)

    pl.DataFrame(
        {"project_id": ["TCGA-BRCA"], "primary_site": ["Breast"], "disease_type": ["Adeno"]}
    ).write_parquet(silver / "silver_projects.parquet")
    pl.DataFrame(
        {"project_id": ["TCGA-BRCA"], "case_id": ["c1"], "submitter_id": ["sub-1"]}
    ).write_parquet(silver / "silver_patients.parquet")
    pl.DataFrame(
        {
            "project_id": ["TCGA-BRCA", "TCGA-BRCA", "TCGA-BRCA"],
            "case_id": ["c1", "c2", "c3"],
            "sample_id": ["Unknown", "unknown", "  "],
            "sample_type": ["Unknown", "Unknown", "Unknown"],
        }
    ).write_parquet(silver / "silver_samples.parquet")
    pl.DataFrame(
        schema={
            "project_id": pl.Utf8,
            "case_id": pl.Utf8,
            "sample_id": pl.Utf8,
            "file_id": pl.Utf8,
            "file_name": pl.Utf8,
            "data_category": pl.Utf8,
            "data_type": pl.Utf8,
            "experimental_strategy": pl.Utf8,
            "workflow_type": pl.Utf8,
            "access": pl.Utf8,
            "file_size": pl.Int64,
            "md5sum": pl.Utf8,
            "ingested_at": pl.Utf8,
        }
    ).write_parquet(silver / "silver_file_manifest.parquet")
    pl.DataFrame(schema={"gtex_sample_id": pl.Utf8, "tissue_site": pl.Utf8, "tissue_detail": pl.Utf8, "gene_id": pl.Utf8, "gene_symbol": pl.Utf8, "expression_value": pl.Float64, "expression_unit": pl.Utf8, "log2_expression": pl.Float64, "source_version": pl.Utf8, "data_origin": pl.Utf8, "ingested_at": pl.Utf8}).write_parquet(silver / "silver_expression_gtex.parquet")
    pl.DataFrame(schema={"project_id": pl.Utf8, "case_id": pl.Utf8, "sample_id": pl.Utf8, "sample_type": pl.Utf8, "gene_id": pl.Utf8, "gene_symbol": pl.Utf8, "expression_value": pl.Float64, "expression_unit": pl.Utf8, "log2_expression": pl.Float64, "pipeline_workflow": pl.Utf8, "data_origin": pl.Utf8, "ingested_at": pl.Utf8}).write_parquet(silver / "silver_expression_tcga.parquet")
    pl.DataFrame(schema={"project_id": pl.Utf8, "case_id": pl.Utf8, "sample_id": pl.Utf8, "gene_id": pl.Utf8, "gene_symbol": pl.Utf8, "variant_classification": pl.Utf8, "variant_type": pl.Utf8, "chromosome": pl.Utf8, "start_position": pl.Int64, "end_position": pl.Int64, "reference_allele": pl.Utf8, "tumor_seq_allele": pl.Utf8, "data_origin": pl.Utf8, "ingested_at": pl.Utf8}).write_parquet(silver / "silver_mutations.parquet")

    results = run_silver_quality_checks(silver_dir=silver)
    by_name = {r.check_name: r for r in results}
    assert by_name["silver_samples_duplicate_sample_id"].status == "passed"


def test_run_silver_quality_checks_warns_on_tcga_workflow_unit_mismatch(tmp_path: Path) -> None:
    silver = tmp_path / "silver"
    silver.mkdir(parents=True, exist_ok=True)
    pl.DataFrame({"project_id": ["TCGA-BRCA"], "primary_site": ["Breast"], "disease_type": ["Adeno"]}).write_parquet(
        silver / "silver_projects.parquet"
    )
    pl.DataFrame({"project_id": ["TCGA-BRCA"], "case_id": ["c1"], "submitter_id": ["sub-1"]}).write_parquet(
        silver / "silver_patients.parquet"
    )
    pl.DataFrame({"project_id": ["TCGA-BRCA"], "case_id": ["c1"], "sample_id": ["s1"], "sample_type": ["Primary Tumor"]}).write_parquet(
        silver / "silver_samples.parquet"
    )
    pl.DataFrame(
        schema={
            "project_id": pl.Utf8,
            "case_id": pl.Utf8,
            "sample_id": pl.Utf8,
            "file_id": pl.Utf8,
            "file_name": pl.Utf8,
            "data_category": pl.Utf8,
            "data_type": pl.Utf8,
            "experimental_strategy": pl.Utf8,
            "workflow_type": pl.Utf8,
            "access": pl.Utf8,
            "file_size": pl.Int64,
            "md5sum": pl.Utf8,
            "ingested_at": pl.Utf8,
        }
    ).write_parquet(silver / "silver_file_manifest.parquet")
    pl.DataFrame(schema={"gtex_sample_id": pl.Utf8, "tissue_site": pl.Utf8, "tissue_detail": pl.Utf8, "gene_id": pl.Utf8, "gene_symbol": pl.Utf8, "expression_value": pl.Float64, "expression_unit": pl.Utf8, "log2_expression": pl.Float64, "source_version": pl.Utf8, "data_origin": pl.Utf8, "ingested_at": pl.Utf8}).write_parquet(silver / "silver_expression_gtex.parquet")
    pl.DataFrame(
        {
            "project_id": ["TCGA-BRCA"],
            "case_id": ["c1"],
            "sample_id": ["s1"],
            "sample_type": ["Primary Tumor"],
            "gene_id": ["ENSG00000141510"],
            "gene_symbol": ["TP53"],
            "expression_value": [2.0],
            "expression_unit": ["TPM"],
            "log2_expression": [1.58],
            "pipeline_workflow": ["HTSeq - Counts"],
            "data_origin": ["x"],
            "ingested_at": ["x"],
        }
    ).write_parquet(silver / "silver_expression_tcga.parquet")
    pl.DataFrame(schema={"project_id": pl.Utf8, "case_id": pl.Utf8, "sample_id": pl.Utf8, "gene_id": pl.Utf8, "gene_symbol": pl.Utf8, "variant_classification": pl.Utf8, "variant_type": pl.Utf8, "chromosome": pl.Utf8, "start_position": pl.Int64, "end_position": pl.Int64, "reference_allele": pl.Utf8, "tumor_seq_allele": pl.Utf8, "data_origin": pl.Utf8, "ingested_at": pl.Utf8}).write_parquet(silver / "silver_mutations.parquet")
    results = run_silver_quality_checks(silver_dir=silver)
    by_name = {r.check_name: r for r in results}
    assert by_name["silver_expression_tcga_workflow_unit_compatibility"].status == "warning"


def test_run_silver_quality_checks_live_mode_non_zero_sanity(tmp_path: Path) -> None:
    silver = tmp_path / "silver"
    bronze_tcga = tmp_path / "bronze" / "tcga"
    outputs = tmp_path / "outputs" / "reports"
    silver.mkdir(parents=True, exist_ok=True)
    bronze_tcga.mkdir(parents=True, exist_ok=True)
    outputs.mkdir(parents=True, exist_ok=True)

    pl.DataFrame(
        {"project_id": ["TCGA-BRCA"], "primary_site": ["Breast"], "disease_type": ["Adeno"]}
    ).write_parquet(silver / "silver_projects.parquet")
    pl.DataFrame(
        {"project_id": ["TCGA-BRCA"], "case_id": ["c1"], "submitter_id": ["sub-1"]}
    ).write_parquet(silver / "silver_patients.parquet")
    pl.DataFrame(
        {"project_id": ["TCGA-BRCA"], "case_id": ["c1"], "sample_id": ["s1"], "sample_type": ["Primary Tumor"]}
    ).write_parquet(silver / "silver_samples.parquet")
    pl.DataFrame(
        schema={
            "project_id": pl.Utf8,
            "case_id": pl.Utf8,
            "sample_id": pl.Utf8,
            "file_id": pl.Utf8,
            "file_name": pl.Utf8,
            "data_category": pl.Utf8,
            "data_type": pl.Utf8,
            "experimental_strategy": pl.Utf8,
            "workflow_type": pl.Utf8,
            "access": pl.Utf8,
            "file_size": pl.Int64,
            "md5sum": pl.Utf8,
            "ingested_at": pl.Utf8,
        }
    ).write_parquet(silver / "silver_file_manifest.parquet")
    pl.DataFrame(schema={"gtex_sample_id": pl.Utf8, "tissue_site": pl.Utf8, "tissue_detail": pl.Utf8, "gene_id": pl.Utf8, "gene_symbol": pl.Utf8, "expression_value": pl.Float64, "expression_unit": pl.Utf8, "log2_expression": pl.Float64, "source_version": pl.Utf8, "data_origin": pl.Utf8, "ingested_at": pl.Utf8}).write_parquet(silver / "silver_expression_gtex.parquet")
    pl.DataFrame(schema={"project_id": pl.Utf8, "case_id": pl.Utf8, "sample_id": pl.Utf8, "sample_type": pl.Utf8, "gene_id": pl.Utf8, "gene_symbol": pl.Utf8, "expression_value": pl.Float64, "expression_unit": pl.Utf8, "log2_expression": pl.Float64, "pipeline_workflow": pl.Utf8, "data_origin": pl.Utf8, "ingested_at": pl.Utf8}).write_parquet(silver / "silver_expression_tcga.parquet")
    pl.DataFrame(schema={"project_id": pl.Utf8, "case_id": pl.Utf8, "sample_id": pl.Utf8, "gene_id": pl.Utf8, "gene_symbol": pl.Utf8, "variant_classification": pl.Utf8, "variant_type": pl.Utf8, "chromosome": pl.Utf8, "start_position": pl.Int64, "end_position": pl.Int64, "reference_allele": pl.Utf8, "tumor_seq_allele": pl.Utf8, "data_origin": pl.Utf8, "ingested_at": pl.Utf8}).write_parquet(silver / "silver_mutations.parquet")

    report = outputs / "tcga_download_report.json"
    report.write_text(
        json.dumps(
            {
                "pipeline_run_id": "x",
                "status": "completed",
                "source_metadata_file": "data/bronze/tcga/metadata/tcga_metadata_live.csv",
                "total_candidates": 1,
                "selected_candidates": 1,
                "attempted_downloads": 1,
            }
        ),
        encoding="utf-8",
    )

    results = run_silver_quality_checks(
        silver_dir=silver,
        bronze_tcga_root=bronze_tcga,
        download_report_path=report,
        gold_dir=tmp_path / "gold",
    )
    by_name = {r.check_name: r for r in results}
    assert by_name["live_mode_non_zero_row_sanity"].status == "failed"
