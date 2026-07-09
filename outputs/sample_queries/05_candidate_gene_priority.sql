SELECT
    cancer_type,
    gene_symbol,
    priority_score,
    priority_tier,
    mutation_frequency,
    abs_log2_fold_change,
    evidence_count,
    evidence_summary
FROM read_parquet('data/gold/gold_candidate_gene_priority/*.parquet')
ORDER BY priority_score DESC, mutation_frequency DESC
LIMIT 25;
