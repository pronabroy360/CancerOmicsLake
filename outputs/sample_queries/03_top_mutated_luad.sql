SELECT
    gene_symbol,
    cancer_type,
    mutated_sample_count,
    total_profiled_sample_count,
    mutation_frequency,
    top_variant_classification
FROM read_parquet('data/gold/gold_mutation_frequency_by_gene/*.parquet')
WHERE cancer_type = 'TCGA-LUAD'
ORDER BY mutation_frequency DESC, mutated_sample_count DESC
LIMIT 20;
