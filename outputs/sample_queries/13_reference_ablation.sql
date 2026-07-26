-- Pairwise agreement among normal-reference methods.
SELECT
    cancer_type,
    method_a,
    method_b,
    top_k_jaccard,
    universe_direction_concordance,
    regulated_direction_concordance,
    spearman_abs_effect,
    agreement_tier
FROM read_parquet('data/gold/gold_reference_method_comparison.parquet')
ORDER BY cancer_type, top_k_jaccard DESC;

-- Consensus sensitivity after explicit evidence-component removal.
SELECT
    cancer_type,
    ablation_scenario,
    top_k_jaccard,
    spearman_consensus_score,
    fixed_threshold_retention_rate,
    sensitivity_tier
FROM read_parquet('data/gold/gold_consensus_ablation_stability.parquet')
ORDER BY cancer_type, ablation_scenario;
