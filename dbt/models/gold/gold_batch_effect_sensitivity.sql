with base as (
  select
    cancer_type,
    gene_symbol,
    ln(median_tcga_tumor_expression + 1.0) / ln(2.0) as tumor_log2_median,
    ln(median_gtex_normal_expression + 1.0) / ln(2.0) as normal_log2_median,
    sample_count_tumor,
    sample_count_normal
  from {{ ref('gold_tumor_vs_normal_expression') }}
),
ranked as (
  select
    *,
    percent_rank() over (
      partition by cancer_type
      order by tumor_log2_median
    ) as tumor_expression_percentile,
    percent_rank() over (
      partition by cancer_type
      order by normal_log2_median
    ) as normal_expression_percentile,
    median(tumor_log2_median) over (partition by cancer_type) as tumor_cohort_median,
    median(normal_log2_median) over (partition by cancer_type) as normal_cohort_median
  from base
),
deviations as (
  select
    *,
    abs(tumor_log2_median - tumor_cohort_median) as tumor_abs_deviation,
    abs(normal_log2_median - normal_cohort_median) as normal_abs_deviation
  from ranked
),
scaled as (
  select
    *,
    median(tumor_abs_deviation) over (partition by cancer_type) as tumor_mad,
    median(normal_abs_deviation) over (partition by cancer_type) as normal_mad
  from deviations
),
scored as (
  select
    cancer_type,
    gene_symbol,
    round(tumor_log2_median, 6) as tumor_log2_median,
    round(normal_log2_median, 6) as normal_log2_median,
    round(tumor_expression_percentile, 6) as tumor_expression_percentile,
    round(normal_expression_percentile, 6) as normal_expression_percentile,
    round(tumor_expression_percentile - normal_expression_percentile, 6) as percentile_delta,
    round(
      case
        when tumor_mad > 0 then (tumor_log2_median - tumor_cohort_median) / (tumor_mad * 1.4826)
        else 0.0
      end,
      6
    ) as tumor_robust_z,
    round(
      case
        when normal_mad > 0 then (normal_log2_median - normal_cohort_median) / (normal_mad * 1.4826)
        else 0.0
      end,
      6
    ) as normal_robust_z,
    sample_count_tumor,
    sample_count_normal
  from scaled
)
select
  cancer_type,
  gene_symbol,
  tumor_log2_median,
  normal_log2_median,
  tumor_expression_percentile,
  normal_expression_percentile,
  percentile_delta,
  tumor_robust_z,
  normal_robust_z,
  round(tumor_robust_z - normal_robust_z, 6) as robust_z_delta,
  sample_count_tumor,
  sample_count_normal,
  case
    when sample_count_tumor >= 30 and sample_count_normal >= 30 then 'high'
    when sample_count_tumor >= 10 and sample_count_normal >= 10 then 'moderate'
    else 'limited'
  end as support_tier,
  case
    when percentile_delta >= 0.20 or (tumor_robust_z - normal_robust_z) >= 1.0 then 'rank_up'
    when percentile_delta <= -0.20 or (tumor_robust_z - normal_robust_z) <= -1.0 then 'rank_down'
    else 'stable'
  end as sensitivity_direction,
  'within_cohort_rank_and_robust_z' as batch_method,
  'Exploratory sensitivity analysis only; rank and robust-z scaling reduce scale dependence but do not remove TCGA-GTEx study effects.' as batch_effect_caveat
from scored
