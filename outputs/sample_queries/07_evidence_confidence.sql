select
    cancer_type,
    gene_symbol,
    priority_score,
    overall_confidence,
    confidence_tier,
    mutation_confidence,
    expression_confidence,
    batch_sensitivity_confidence,
    batch_concordance,
    graph_confidence,
    traceability_confidence,
    batch_effect_risk,
    caveat_summary
from read_parquet('data/gold/gold_cancer_gene_evidence_confidence.parquet')
where confidence_tier in ('high', 'moderate')
  and batch_concordance = 'concordant'
order by overall_confidence desc, priority_score desc
limit 50;
