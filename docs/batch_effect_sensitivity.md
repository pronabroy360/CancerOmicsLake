# Batch-Effect Sensitivity Methodology

`gold_batch_effect_sensitivity` is an exploratory layer for reviewing TCGA tumor versus GTEx normal
expression without relying only on raw cross-study fold change.

## Problem

TCGA and GTEx expression values come from different projects and processing contexts. Raw TPM
comparisons are useful for engineering demonstrations, but they are not sufficient for biological
claims because study effects can dominate real tissue or tumor signals.

## Implemented Sensitivity Approach

For each cancer project and gene:

- Compute TCGA tumor and GTEx normal median TPM from the existing tumor-vs-normal mart.
- Convert medians to `log2(TPM + 1)`.
- Rank genes within each cancer/reference comparison separately using average ranks for tied values.
- Compute `percentile_delta = tumor_expression_percentile - normal_expression_percentile`.
- Compute robust z-scores within each comparison using median and MAD scaling.
- Compute `robust_z_delta = tumor_robust_z - normal_robust_z`.
- Label direction as `rank_up`, `rank_down`, or `stable`.
- Label sample support as `high`, `moderate`, or `limited`.

## Interpretation

This layer reduces dependence on absolute cross-study scale by comparing each gene to other genes
within the same cohort/reference context. It is useful for sensitivity review and candidate triage.

It is not full batch correction. A publication-grade biological claim still requires a harmonized
analysis strategy such as matched processing, explicit batch modeling, or an external recomputed
TCGA-GTEx resource with documented methods.

## Current Output

- Python gold table: `data/gold/gold_batch_effect_sensitivity.parquet`
- dbt model: `dbt/models/gold/gold_batch_effect_sensitivity.sql`
- API: `GET /research/batch-effect-sensitivity`
- Dashboard: `Batch-Effect Sensitivity`
- Reviewer SQL: `outputs/sample_queries/08_batch_effect_sensitivity.sql`
