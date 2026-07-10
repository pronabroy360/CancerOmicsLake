with base as (
  select
    cancer_type,
    gene_symbol,
    ln(median_tcga_tumor_expression + 1.0) / ln(2.0) as tumor_log2_median,
    ln(median_gtex_normal_expression + 1.0) / ln(2.0) as normal_log2_median
  from {{ ref('gold_tumor_vs_normal_expression') }}
),
rank_stats as (
  select
    *,
    rank() over (partition by cancer_type order by tumor_log2_median) as tumor_rank_min,
    count(*) over (partition by cancer_type, tumor_log2_median) as tumor_tie_count,
    rank() over (partition by cancer_type order by normal_log2_median) as normal_rank_min,
    count(*) over (partition by cancer_type, normal_log2_median) as normal_tie_count,
    count(*) over (partition by cancer_type) as gene_count
  from base
),
expected as (
  select
    cancer_type,
    gene_symbol,
    round(case when gene_count > 1 then
      (tumor_rank_min + (tumor_tie_count - 1) / 2.0 - 1.0) / (gene_count - 1.0)
    else 0.5 end, 6) as tumor_expression_percentile,
    round(case when gene_count > 1 then
      (normal_rank_min + (normal_tie_count - 1) / 2.0 - 1.0) / (gene_count - 1.0)
    else 0.5 end, 6) as normal_expression_percentile
  from rank_stats
)
select
  actual.cancer_type,
  actual.gene_symbol
from {{ ref('gold_batch_effect_sensitivity') }} actual
join expected using (cancer_type, gene_symbol)
where abs(actual.tumor_expression_percentile - expected.tumor_expression_percentile) > 0.000001
   or abs(actual.normal_expression_percentile - expected.normal_expression_percentile) > 0.000001
