select
    cancer_type,
    gene_symbol,
    candidate_priority_rank,
    candidate_selection_reason,
    bootstrap_stability_score,
    bootstrap_stability_tier,
    reference_concordance_rate,
    opposite_direction_rate,
    tcga_median_rank,
    gtex_median_rank
from read_parquet('data/gold/gold_candidate_bootstrap_stability.parquet')
where evidence_confidence_tier = 'high'
order by bootstrap_stability_score desc
limit 50;
