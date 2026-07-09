from pathlib import Path

import polars as pl

from src.analytics.build_gold_tables import build_gold_cohort_summary
from src.analytics.cohort_summary import cohort_summary_from_gold


def test_build_gold_cohort_summary_from_silver(tmp_path: Path) -> None:
    silver_dir = tmp_path / "silver"
    gold_dir = tmp_path / "gold"
    silver_dir.mkdir(parents=True, exist_ok=True)

    pl.DataFrame(
        {
            "project_id": ["TCGA-BRCA", "TCGA-LUAD"],
            "primary_site": ["Breast", "Lung"],
            "disease_type": ["Adeno", "Adeno"],
        }
    ).write_parquet(silver_dir / "silver_projects.parquet")
    pl.DataFrame(
        {
            "project_id": ["TCGA-BRCA", "TCGA-LUAD"],
            "case_id": ["case-1", "case-2"],
            "submitter_id": ["sub-1", "sub-2"],
        }
    ).write_parquet(silver_dir / "silver_patients.parquet")
    pl.DataFrame(
        {
            "project_id": ["TCGA-BRCA", "TCGA-LUAD"],
            "case_id": ["case-1", "case-2"],
            "sample_id": ["sample-1", "sample-2"],
            "sample_type": ["Primary Tumor", "Primary Tumor"],
        }
    ).write_parquet(silver_dir / "silver_samples.parquet")
    pl.DataFrame(
        {
            "project_id": ["TCGA-BRCA", "TCGA-LUAD"],
            "case_id": ["case-1", "case-2"],
            "sample_id": ["sample-1", "sample-2"],
            "file_id": ["file-1", "file-2"],
            "file_name": ["f1.tsv", "f2.tsv"],
            "data_category": ["Transcriptome Profiling", "Clinical"],
            "data_type": ["Gene Expression Quantification", "Clinical Supplement"],
            "experimental_strategy": ["RNA-Seq", "RNA-Seq"],
            "workflow_type": ["STAR", "STAR"],
            "access": ["open", "open"],
            "file_size": [100, 200],
            "md5sum": ["a", "b"],
            "ingested_at": ["x", "x"],
        }
    ).write_parquet(silver_dir / "silver_file_manifest.parquet")
    pl.DataFrame(
        {
            "gtex_sample_id": ["GTEX-AAA-1", "GTEX-BBB-1"],
            "tissue_site": ["Lung", "Breast"],
            "tissue_detail": ["Lung", "Breast"],
            "gene_id": ["ENSG1", "ENSG2"],
            "gene_symbol": ["TP53", "BRCA1"],
            "expression_value": [1.0, 2.0],
            "expression_unit": ["TPM", "TPM"],
            "log2_expression": [1.0, 1.58],
            "source_version": ["v8", "v8"],
            "data_origin": ["stub", "stub"],
            "ingested_at": ["x", "x"],
        }
    ).write_parquet(silver_dir / "silver_expression_gtex.parquet")
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
    ).write_parquet(silver_dir / "silver_expression_tcga.parquet")
    pl.DataFrame(
        {
            "project_id": ["TCGA-BRCA", "TCGA-LUAD"],
            "case_id": ["case-1", "case-2"],
            "sample_id": ["sample-1", "sample-2"],
            "gene_id": ["ENSG1", "ENSG2"],
            "gene_symbol": ["TP53", "EGFR"],
            "variant_classification": ["Missense_Mutation", "Nonsense_Mutation"],
            "variant_type": ["SNP", "SNP"],
            "chromosome": ["17", "7"],
            "start_position": [7673803, 55242465],
            "end_position": [7673803, 55242465],
            "reference_allele": ["C", "G"],
            "tumor_seq_allele": ["T", "A"],
            "data_origin": ["stub", "stub"],
            "ingested_at": ["x", "x"],
        }
    ).write_parquet(silver_dir / "silver_mutations.parquet")

    summary = build_gold_cohort_summary(silver_dir=silver_dir, gold_dir=gold_dir)
    assert summary["tcga_project_count"] == 2
    assert summary["tcga_patient_count"] == 2
    assert summary["tcga_sample_count"] == 2
    assert summary["tcga_file_count"] == 2
    assert summary["gtex_expression_sample_count"] == 2
    assert summary["mutation_record_count"] == 2
    assert (gold_dir / "gold_cohort_summary.parquet").exists()
    assert (gold_dir / "gold_mutation_frequency_by_gene.parquet").exists()
    assert (gold_dir / "gold_mutation_frequency_by_cancer.parquet").exists()
    assert (gold_dir / "gold_tumor_vs_normal_expression.parquet").exists()
    assert (gold_dir / "gold_candidate_gene_priority.parquet").exists()


def test_build_gold_tumor_vs_normal_expression_rows(tmp_path: Path) -> None:
    silver_dir = tmp_path / "silver"
    gold_dir = tmp_path / "gold"
    silver_dir.mkdir(parents=True, exist_ok=True)

    pl.DataFrame(
        {
            "project_id": ["TCGA-BRCA"],
            "primary_site": ["Breast"],
            "disease_type": ["Adeno"],
        }
    ).write_parquet(silver_dir / "silver_projects.parquet")
    pl.DataFrame(
        {"project_id": ["TCGA-BRCA"], "case_id": ["case-1"], "submitter_id": ["sub-1"]}
    ).write_parquet(silver_dir / "silver_patients.parquet")
    pl.DataFrame(
        {
            "project_id": ["TCGA-BRCA", "TCGA-BRCA"],
            "case_id": ["case-1", "case-2"],
            "sample_id": ["sample-1", "sample-2"],
            "sample_type": ["Primary Tumor", "Primary Tumor"],
        }
    ).write_parquet(silver_dir / "silver_samples.parquet")
    pl.DataFrame(
        {
            "project_id": ["TCGA-BRCA"],
            "case_id": ["case-1"],
            "sample_id": ["sample-1"],
            "file_id": ["file-1"],
            "file_name": ["f1.tsv"],
            "data_category": ["Transcriptome Profiling"],
            "data_type": ["Gene Expression Quantification"],
            "experimental_strategy": ["RNA-Seq"],
            "workflow_type": ["STAR"],
            "access": ["open"],
            "file_size": [100],
            "md5sum": ["a"],
            "ingested_at": ["x"],
        }
    ).write_parquet(silver_dir / "silver_file_manifest.parquet")
    pl.DataFrame(
        {
            "project_id": ["TCGA-BRCA", "TCGA-BRCA"],
            "case_id": ["case-1", "case-2"],
            "sample_id": ["sample-1", "sample-2"],
            "sample_type": ["Primary Tumor", "Primary Tumor"],
            "gene_id": ["ENSG00000141510", "ENSG00000141510"],
            "gene_symbol": ["TP53", "TP53"],
            "expression_value": [8.0, 12.0],
            "expression_unit": ["TPM", "TPM"],
            "log2_expression": [3.17, 3.70],
            "pipeline_workflow": ["STAR", "STAR"],
            "data_origin": ["stub", "stub"],
            "ingested_at": ["x", "x"],
        }
    ).write_parquet(silver_dir / "silver_expression_tcga.parquet")
    pl.DataFrame(
        {
            "gtex_sample_id": ["GTEX-BR-1", "GTEX-BR-2"],
            "tissue_site": ["Breast - Mammary Tissue", "Breast - Mammary Tissue"],
            "tissue_detail": ["Breast - Mammary Tissue", "Breast - Mammary Tissue"],
            "gene_id": ["ENSG00000141510", "ENSG00000141510"],
            "gene_symbol": ["TP53", "TP53"],
            "expression_value": [2.0, 2.0],
            "expression_unit": ["TPM", "TPM"],
            "log2_expression": [1.58, 1.58],
            "source_version": ["v8", "v8"],
            "data_origin": ["stub", "stub"],
            "ingested_at": ["x", "x"],
        }
    ).write_parquet(silver_dir / "silver_expression_gtex.parquet")
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
    ).write_parquet(silver_dir / "silver_mutations.parquet")

    summary = build_gold_cohort_summary(silver_dir=silver_dir, gold_dir=gold_dir)
    assert summary["tumor_vs_normal_rows"] == 1

    tvn = pl.read_parquet(gold_dir / "gold_tumor_vs_normal_expression.parquet")
    assert tvn.height == 1
    row = tvn.row(0, named=True)
    assert row["gene_symbol"] == "TP53"
    assert row["cancer_type"] == "TCGA-BRCA"
    assert row["sample_count_tumor"] == 2
    assert row["sample_count_normal"] == 2


def test_build_gold_candidate_gene_priority_ranks_multi_evidence_genes(tmp_path: Path) -> None:
    silver_dir = tmp_path / "silver"
    gold_dir = tmp_path / "gold"
    silver_dir.mkdir(parents=True, exist_ok=True)

    pl.DataFrame(
        {
            "project_id": ["TCGA-BRCA"],
            "primary_site": ["Breast"],
            "disease_type": ["Adeno"],
        }
    ).write_parquet(silver_dir / "silver_projects.parquet")
    pl.DataFrame(
        {
            "project_id": ["TCGA-BRCA"],
            "case_id": ["case-1"],
            "submitter_id": ["sub-1"],
        }
    ).write_parquet(silver_dir / "silver_patients.parquet")
    pl.DataFrame(
        {
            "project_id": ["TCGA-BRCA", "TCGA-BRCA"],
            "case_id": ["case-1", "case-2"],
            "sample_id": ["sample-1", "sample-2"],
            "sample_type": ["Primary Tumor", "Primary Tumor"],
        }
    ).write_parquet(silver_dir / "silver_samples.parquet")
    pl.DataFrame(
        {
            "project_id": ["TCGA-BRCA"],
            "case_id": ["case-1"],
            "sample_id": ["sample-1"],
            "file_id": ["file-1"],
            "file_name": ["f1.tsv"],
            "data_category": ["Transcriptome Profiling"],
            "data_type": ["Gene Expression Quantification"],
            "experimental_strategy": ["RNA-Seq"],
            "workflow_type": ["STAR"],
            "access": ["open"],
            "file_size": [100],
            "md5sum": ["a"],
            "ingested_at": ["x"],
        }
    ).write_parquet(silver_dir / "silver_file_manifest.parquet")
    pl.DataFrame(
        {
            "project_id": ["TCGA-BRCA", "TCGA-BRCA", "TCGA-BRCA"],
            "case_id": ["case-1", "case-2", "case-2"],
            "sample_id": ["sample-1", "sample-2", "sample-2"],
            "sample_type": ["Primary Tumor", "Primary Tumor", "Primary Tumor"],
            "gene_id": ["ENSG1", "ENSG1", "ENSG2"],
            "gene_symbol": ["TP53", "TP53", "BRCA1"],
            "expression_value": [8.0, 10.0, 20.0],
            "expression_unit": ["TPM", "TPM", "TPM"],
            "log2_expression": [3.17, 3.46, 4.39],
            "pipeline_workflow": ["STAR", "STAR", "STAR"],
            "data_origin": ["stub", "stub", "stub"],
            "ingested_at": ["x", "x", "x"],
        }
    ).write_parquet(silver_dir / "silver_expression_tcga.parquet")
    pl.DataFrame(
        {
            "gtex_sample_id": ["GTEX-BR-1", "GTEX-BR-1"],
            "tissue_site": ["Breast - Mammary Tissue", "Breast - Mammary Tissue"],
            "tissue_detail": ["Breast - Mammary Tissue", "Breast - Mammary Tissue"],
            "gene_id": ["ENSG1", "ENSG2"],
            "gene_symbol": ["TP53", "BRCA1"],
            "expression_value": [2.0, 2.0],
            "expression_unit": ["TPM", "TPM"],
            "log2_expression": [1.58, 1.58],
            "source_version": ["v8", "v8"],
            "data_origin": ["stub", "stub"],
            "ingested_at": ["x", "x"],
        }
    ).write_parquet(silver_dir / "silver_expression_gtex.parquet")
    pl.DataFrame(
        {
            "project_id": ["TCGA-BRCA"],
            "case_id": ["case-1"],
            "sample_id": ["sample-1"],
            "gene_id": ["ENSG1"],
            "gene_symbol": ["TP53"],
            "variant_classification": ["Missense_Mutation"],
            "variant_type": ["SNP"],
            "chromosome": ["17"],
            "start_position": [7673803],
            "end_position": [7673803],
            "reference_allele": ["C"],
            "tumor_seq_allele": ["T"],
            "data_origin": ["stub"],
            "ingested_at": ["x"],
        }
    ).write_parquet(silver_dir / "silver_mutations.parquet")

    summary = build_gold_cohort_summary(silver_dir=silver_dir, gold_dir=gold_dir)
    assert summary["candidate_gene_priority_rows"] == 2

    priority = pl.read_parquet(gold_dir / "gold_candidate_gene_priority.parquet")
    top = priority.sort("priority_score", descending=True).row(0, named=True)
    assert top["gene_symbol"] == "TP53"
    assert top["evidence_count"] == 2
    assert top["priority_tier"] in {"medium", "high"}


def test_cohort_summary_from_gold_or_fallback(tmp_path: Path) -> None:
    fallback = cohort_summary_from_gold(tmp_path / "does_not_exist.parquet")
    assert "tcga_projects" in fallback

    gold_file = tmp_path / "gold_cohort_summary.parquet"
    pl.DataFrame(
        [
            {
                "tcga_project_count": 3,
                "tcga_patient_count": 10,
                "tcga_sample_count": 12,
                "tcga_file_count": 30,
                "gtex_expression_sample_count": 4,
                "tcga_expression_row_count": 0,
                "gtex_expression_row_count": 4,
                "gene_count": 0,
                "mutation_record_count": 0,
                "generated_at": "2026-05-27T00:00:00Z",
            }
        ]
    ).write_parquet(gold_file)
    from_gold = cohort_summary_from_gold(gold_file)
    assert from_gold["tcga_projects"] == 3
    assert from_gold["tcga_samples"] == 12
    assert from_gold["gtex_samples"] == 4
