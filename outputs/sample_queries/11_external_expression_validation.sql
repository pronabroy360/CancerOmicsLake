SELECT
    cancer_type,
    gene_symbol,
    native_log2_fold_change,
    recount3_log2_fold_change,
    effect_delta,
    direction_agreement,
    validation_score,
    validation_tier,
    top_k_overlap
FROM read_parquet('data/gold/gold_external_expression_validation.parquet')
WHERE direction_agreement = 'concordant'
ORDER BY validation_score DESC, effect_delta ASC
LIMIT 50;
