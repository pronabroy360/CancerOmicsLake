with tcga_normal as (
  select
    project_id as cancer_type,
    gene_symbol,
    median(expression_value) as median_tcga_normal_expression,
    count(distinct sample_id) as sample_count_tcga_normal
  from {{ ref('silver_expression_tcga') }}
  where upper(expression_unit) = 'TPM'
    and gene_id like 'ENSG%'
    and lower(sample_type) = 'solid tissue normal'
    and (
      lower(pipeline_workflow) like '%star%'
      or lower(data_origin) like '%rna_seq.augmented_star_gene_counts%'
    )
  group by 1, 2
),
combined as (
  select
    comparison.cancer_type,
    comparison.gene_symbol,
    comparison.median_tcga_tumor_expression,
    tcga_normal.median_tcga_normal_expression,
    comparison.median_gtex_normal_expression,
    comparison.sample_count_tumor,
    tcga_normal.sample_count_tcga_normal,
    comparison.sample_count_normal as sample_count_gtex_normal,
    ln((comparison.median_tcga_tumor_expression + 1.0) / (tcga_normal.median_tcga_normal_expression + 1.0))
      / ln(2.0) as log2_fc_tumor_vs_tcga_normal,
    comparison.log2_fold_change as log2_fc_tumor_vs_gtex,
    ln((tcga_normal.median_tcga_normal_expression + 1.0) / (comparison.median_gtex_normal_expression + 1.0))
      / ln(2.0) as log2_fc_tcga_normal_vs_gtex
  from {{ ref('gold_tumor_vs_normal_expression') }} comparison
  join tcga_normal using (cancer_type, gene_symbol)
),
directions as (
  select
    *,
    abs(log2_fc_tumor_vs_tcga_normal - log2_fc_tumor_vs_gtex) as reference_effect_delta,
    case
      when log2_fc_tumor_vs_tcga_normal >= 1.0 then 'up'
      when log2_fc_tumor_vs_tcga_normal <= -1.0 then 'down'
      else 'stable'
    end as tcga_reference_direction,
    case
      when log2_fc_tumor_vs_gtex >= 1.0 then 'up'
      when log2_fc_tumor_vs_gtex <= -1.0 then 'down'
      else 'stable'
    end as gtex_reference_direction
  from combined
),
concordance as (
  select
    *,
    case
      when tcga_reference_direction = gtex_reference_direction then 'concordant_' || tcga_reference_direction
      when tcga_reference_direction in ('up', 'down') and gtex_reference_direction in ('up', 'down') then 'discordant'
      else 'reference_sensitive'
    end as reference_concordance,
    case
      when sample_count_tcga_normal >= 30 then 'high'
      when sample_count_tcga_normal >= 10 then 'moderate'
      else 'limited'
    end as tcga_normal_support_tier
  from directions
)
select
  cancer_type,
  gene_symbol,
  median_tcga_tumor_expression,
  median_tcga_normal_expression,
  median_gtex_normal_expression,
  cast(sample_count_tumor as bigint) as sample_count_tumor,
  cast(sample_count_tcga_normal as bigint) as sample_count_tcga_normal,
  cast(sample_count_gtex_normal as bigint) as sample_count_gtex_normal,
  log2_fc_tumor_vs_tcga_normal,
  log2_fc_tumor_vs_gtex,
  log2_fc_tcga_normal_vs_gtex,
  reference_effect_delta,
  tcga_reference_direction,
  gtex_reference_direction,
  reference_concordance,
  tcga_normal_support_tier,
  round(
    least(greatest(sample_count_tcga_normal / 30.0, 0.0), 1.0)
    * case
      when reference_concordance like 'concordant_%' then 1.0
      when reference_concordance = 'reference_sensitive' then 0.5
      else 0.0
    end
    * (1.0 - least(greatest(reference_effect_delta / 4.0, 0.0), 1.0)),
    6
  ) as reference_stability_score,
  'TCGA adjacent normal reduces cross-study dependence but may contain field effects; GTEx remains an independent healthy reference.'
    as triangulation_caveat
from concordance
