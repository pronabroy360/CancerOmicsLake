# Sample Queries

These SQL examples are safe to publish because they query local marts and aggregate outputs. Run the pipeline first:

```bash
make run-flow-medium
make run-graph-export
make run-demo-check
```

For DuckDB, either query dbt models or read parquet files directly from `data/gold/`.

## Cohort Summary

```sql
SELECT
    tcga_project_count,
    tcga_patient_count,
    tcga_sample_count,
    tcga_file_count,
    gtex_expression_sample_count,
    tcga_expression_row_count,
    gtex_expression_row_count,
    gene_count,
    mutation_record_count,
    generated_at
FROM read_parquet('data/gold/gold_cohort_summary/*.parquet');
```

## Top Overexpressed Genes In BRCA

```sql
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
```

## Top Mutated Genes In LUAD

```sql
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
```

## Cancer-Gene Graph Edges

```sql
SELECT
    source_node_id,
    target_node_id,
    edge_type,
    weight,
    evidence_source
FROM read_parquet('data/gold/gold_graph_edges/*.parquet')
WHERE edge_type IN ('EXPRESSED_IN_TISSUE', 'MUTATED_IN_CANCER')
ORDER BY weight DESC
LIMIT 100;
```

## Genes With Expression And Mutation Signals

```sql
WITH expression_signal AS (
    SELECT
        cancer_type,
        gene_symbol,
        log2_fold_change
    FROM read_parquet('data/gold/gold_tumor_vs_normal_expression/*.parquet')
    WHERE log2_fold_change IS NOT NULL
),
mutation_signal AS (
    SELECT
        cancer_type,
        gene_symbol,
        mutation_frequency
    FROM read_parquet('data/gold/gold_mutation_frequency_by_gene/*.parquet')
)
SELECT
    e.cancer_type,
    e.gene_symbol,
    e.log2_fold_change,
    m.mutation_frequency
FROM expression_signal e
JOIN mutation_signal m
    ON e.cancer_type = m.cancer_type
   AND e.gene_symbol = m.gene_symbol
ORDER BY e.log2_fold_change DESC, m.mutation_frequency DESC
LIMIT 25;
```

## Candidate Cancer-Gene Prioritization

```sql
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
```

## Top Graph Hub Nodes

```sql
SELECT
    node_id,
    node_label,
    name,
    total_degree,
    in_degree,
    out_degree,
    weighted_degree,
    edge_type_count,
    degree_rank
FROM read_parquet('data/gold/gold_graph_node_metrics/*.parquet')
ORDER BY total_degree DESC, weighted_degree DESC
LIMIT 25;
```

## Evidence-Calibrated Candidate Genes

```sql
SELECT
    cancer_type,
    gene_symbol,
    priority_score,
    overall_confidence,
    confidence_tier,
    batch_concordance,
    batch_sensitivity_confidence,
    batch_effect_risk,
    caveat_summary
FROM read_parquet('data/gold/gold_cancer_gene_evidence_confidence.parquet')
WHERE confidence_tier IN ('high', 'moderate')
  AND batch_concordance = 'concordant'
ORDER BY overall_confidence DESC, priority_score DESC
LIMIT 50;
```

This mart deliberately separates candidate importance from evidence reliability. Directional
concordance is a sensitivity guardrail, not batch correction; cross-study expression remains limited.

## Batch-Effect Sensitivity Ranking

```sql
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
```

This mart compares within-cohort expression ranks and robust z-scores. It is a sensitivity analysis,
not a substitute for full batch correction.

## Reference-Triangulated Candidate Stability

```sql
SELECT
    cancer_type,
    gene_symbol,
    log2_fc_tumor_vs_tcga_normal,
    log2_fc_tumor_vs_gtex,
    log2_fc_tcga_normal_vs_gtex,
    reference_concordance,
    tcga_normal_support_tier,
    reference_stability_score
FROM read_parquet('data/gold/gold_reference_triangulation.parquet')
WHERE reference_concordance IN ('concordant_up', 'concordant_down')
ORDER BY reference_stability_score DESC, reference_effect_delta ASC
LIMIT 50;
```

This mart uses adjacent normal as a bridge reference. It does not treat adjacent normal as healthy tissue.

## Bootstrap-Stable High-Confidence Candidates

```sql
SELECT
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
FROM read_parquet('data/gold/gold_candidate_bootstrap_stability.parquet')
WHERE evidence_confidence_tier = 'high'
ORDER BY bootstrap_stability_score DESC
LIMIT 50;
```

## Externally Validated Expression Candidates

```sql
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
```

This mart is populated only after adding a normalized recount3 extract. It is an external reproducibility
check over a uniformly processed source, not clinical validation.

## Consensus Candidate Genes

```sql
SELECT
    cancer_type,
    gene_symbol,
    consensus_score,
    consensus_decision,
    publication_tier,
    rejection_reasons,
    validation_score,
    reference_concordance,
    bootstrap_stability_tier
FROM read_parquet('data/gold/gold_consensus_candidate_genes.parquet')
WHERE consensus_decision = 'prioritized'
ORDER BY consensus_score DESC
LIMIT 50;
```

Use this mart for manuscript triage only. It is designed to reject candidates with external discordance,
reference sensitivity, or weak stability before biological interpretation.

## Replicated Sample-Level Statistical Support

```sql
SELECT
    cancer_type,
    gene_symbol,
    native_fdr_q_value,
    recount3_fdr_q_value,
    native_rank_biserial,
    recount3_rank_biserial,
    statistical_support_score
FROM read_parquet('data/gold/gold_expression_statistical_support.parquet')
WHERE statistical_support_tier = 'replicated_fdr'
ORDER BY statistical_support_score DESC
LIMIT 50;
```

This table provides FDR-controlled association support. It does not remove source/disease confounding or establish causality.

## Matched TCGA Tumor-Normal Support

```sql
SELECT
    cancer_type,
    gene_symbol,
    matched_case_count,
    paired_log2_fold_change,
    paired_fdr_q_value,
    paired_rank_biserial,
    paired_direction_agreement,
    paired_support_score
FROM read_parquet('data/gold/gold_paired_tcga_expression_support.parquet')
WHERE paired_support_tier = 'paired_replicated'
ORDER BY paired_support_score DESC, paired_fdr_q_value ASC
LIMIT 50;
```

This table uses exact TCGA case matching between primary tumor and adjacent normal samples. It reduces source
confounding but still should not be treated as a clinical or causal result.

## Candidate Pathway Enrichment

```sql
SELECT
    cancer_type,
    candidate_set,
    pathway_id,
    pathway_name,
    overlap_gene_count,
    overlap_genes,
    enrichment_ratio,
    fdr_q_value,
    enrichment_score
FROM read_parquet('data/gold/gold_pathway_enrichment.parquet')
WHERE enrichment_tier = 'fdr_enriched'
ORDER BY enrichment_score DESC, fdr_q_value ASC
LIMIT 50;
```

This table summarizes pathway-level hypotheses over consensus candidate sets. It depends on the tested
background and should not be interpreted as mechanistic proof.

## Quality Checks That Need Attention

```sql
SELECT
    check_name,
    status,
    failed_rows,
    message
FROM read_json_auto('outputs/reports/silver_data_quality_report.json')
WHERE status IN ('failed', 'warning')
ORDER BY status, check_name;
```

## Caveat

Tumor-vs-normal expression comparisons join TCGA tumor data to GTEx normal tissue references. These are useful for demonstrating data engineering and exploratory analytics, but batch effects mean they are not clinical or validated biological claims.
