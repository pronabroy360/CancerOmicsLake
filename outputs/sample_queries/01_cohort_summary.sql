SELECT
    tcga_project_count,
    tcga_patient_count,
    tcga_sample_count,
    tcga_file_count,
    gtex_expression_sample_count,
    tcga_expression_row_count,
    gtex_expression_row_count,
    gene_count,
    mutation_record_count,
    generated_at
FROM read_parquet('data/gold/gold_cohort_summary/*.parquet');
