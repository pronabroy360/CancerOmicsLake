select
    cancer_type,
    gene_symbol,
    log2_fc_tumor_vs_tcga_normal,
    log2_fc_tumor_vs_gtex,
    log2_fc_tcga_normal_vs_gtex,
    reference_concordance,
    tcga_normal_support_tier,
    reference_stability_score
from read_parquet('data/gold/gold_reference_triangulation.parquet')
where reference_concordance in ('concordant_up', 'concordant_down')
order by reference_stability_score desc, reference_effect_delta asc
limit 50;
