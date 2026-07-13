-- Top pathway enrichment hits per cancer and candidate set.
-- Source: data/gold/gold_pathway_enrichment.parquet
-- Interpretation: hypothesis generation only; not mechanistic or clinical proof.

SELECT
    cancer_type,
    candidate_set,
    pathway_id,
    pathway_name,
    pathway_gene_count,
    overlap_gene_count,
    overlap_genes,
    enrichment_ratio,
    odds_ratio,
    p_value,
    fdr_q_value,
    enrichment_score,
    enrichment_tier
FROM read_parquet('data/gold/gold_pathway_enrichment.parquet')
WHERE enrichment_tier = 'fdr_enriched'
ORDER BY cancer_type, candidate_set, enrichment_score DESC, fdr_q_value ASC
LIMIT 50;
