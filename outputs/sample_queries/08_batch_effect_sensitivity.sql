SELECT
    cancer_type,
    gene_symbol,
    percentile_delta,
    robust_z_delta,
    support_tier,
    sensitivity_direction,
    batch_method
FROM read_parquet('data/gold/gold_batch_effect_sensitivity.parquet')
WHERE support_tier = 'high'
ORDER BY abs(percentile_delta) DESC, abs(robust_z_delta) DESC
LIMIT 50;
