SELECT
    gene_symbol,
    cancer_type,
    median_tumor_expression,
    median_normal_expression,
    log2_fold_change,
    sample_count_tumor,
    sample_count_normal
FROM read_parquet('data/gold/gold_tumor_vs_normal_expression/*.parquet')
WHERE cancer_type = 'TCGA-BRCA'
ORDER BY log2_fold_change DESC
LIMIT 20;
