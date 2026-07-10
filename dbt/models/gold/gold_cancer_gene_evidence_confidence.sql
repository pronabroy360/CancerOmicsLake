with tissue_mapping(cancer_type, tissue_site) as (
  values
    ('TCGA-BRCA', 'Breast - Mammary Tissue'),
    ('TCGA-BRCA', 'Breast'),
    ('TCGA-LUAD', 'Lung'),
    ('TCGA-COAD', 'Colon - Transverse'),
    ('TCGA-COAD', 'Colon - Sigmoid'),
    ('TCGA-COAD', 'Colon')
),
expression_counts as (
  select cancer_type, gene_symbol, sample_count_tumor, sample_count_normal
  from {{ ref('gold_tumor_vs_normal_expression') }}
),
batch_sensitivity as (
  select
    cancer_type,
    gene_symbol,
    sensitivity_direction,
    support_tier as sensitivity_support_tier,
    percentile_delta,
    robust_z_delta
  from {{ ref('gold_batch_effect_sensitivity') }}
),
graph_degree as (
  select replace(node_id, 'GENE:', '') as gene_symbol, count(*) as gene_graph_degree
  from (
    select source_node_id as node_id from {{ ref('gold_graph_edges') }}
    union all
    select target_node_id as node_id from {{ ref('gold_graph_edges') }}
  ) edges
  where node_id like 'GENE:%'
  group by 1
),
pair_edges as (
  select distinct
    replace(source_node_id, 'GENE:', '') as gene_symbol,
    target_node_id as cancer_type,
    true as graph_pair_edge
  from {{ ref('gold_graph_edges') }}
  where edge_type in ('MUTATED_IN_CANCER', 'OVEREXPRESSED_IN')
),
mutation_provenance as (
  select
    project_id as cancer_type,
    gene_symbol,
    avg(case
      when data_origin is not null
        and trim(data_origin) != ''
        and lower(data_origin) not like '%stub%'
        and lower(data_origin) not like '%placeholder%'
        and lower(data_origin) not like '%demo%'
      then 1.0 else 0.0 end
    ) as mutation_provenance
  from {{ ref('silver_mutations') }}
  group by 1, 2
),
tcga_expression_provenance as (
  select
    project_id as cancer_type,
    gene_symbol,
    avg(case
      when data_origin is not null
        and trim(data_origin) != ''
        and lower(data_origin) not like '%stub%'
        and lower(data_origin) not like '%placeholder%'
        and lower(data_origin) not like '%demo%'
      then 1.0 else 0.0 end
    ) as tcga_expression_provenance
  from {{ ref('silver_expression_tcga') }}
  group by 1, 2
),
gtex_expression_provenance as (
  select
    mapping.cancer_type,
    expression.gene_symbol,
    avg(case
      when expression.data_origin is not null
        and trim(expression.data_origin) != ''
        and lower(expression.data_origin) not like '%stub%'
        and lower(expression.data_origin) not like '%placeholder%'
        and lower(expression.data_origin) not like '%demo%'
      then 1.0 else 0.0 end
    ) as gtex_expression_provenance
  from {{ ref('silver_expression_gtex') }} expression
  join tissue_mapping mapping on expression.tissue_site = mapping.tissue_site
  group by 1, 2
),
joined as (
  select
    candidate.*,
    coalesce(counts.sample_count_tumor, 0) as sample_count_tumor,
    coalesce(counts.sample_count_normal, 0) as sample_count_normal,
    coalesce(degree.gene_graph_degree, 0) as gene_graph_degree,
    coalesce(pair.graph_pair_edge, false) as graph_pair_edge,
    mutation_provenance.mutation_provenance,
    tcga_expression_provenance.tcga_expression_provenance,
    gtex_expression_provenance.gtex_expression_provenance,
    coalesce(sensitivity.sensitivity_direction, 'unavailable') as sensitivity_direction,
    coalesce(sensitivity.sensitivity_support_tier, 'unavailable') as sensitivity_support_tier,
    sensitivity.percentile_delta,
    sensitivity.robust_z_delta,
    candidate.mutated_sample_count > 0 as mutation_evidence,
    coalesce(counts.sample_count_tumor, 0) > 0
      and coalesce(counts.sample_count_normal, 0) > 0 as expression_evidence,
    case
      when candidate.log2_fold_change >= 1.0 then 'raw_up'
      when candidate.log2_fold_change <= -1.0 then 'raw_down'
      else 'raw_stable'
    end as raw_expression_direction
  from {{ ref('gold_candidate_gene_priority') }} candidate
  left join expression_counts counts using (cancer_type, gene_symbol)
  left join batch_sensitivity sensitivity using (cancer_type, gene_symbol)
  left join graph_degree degree using (gene_symbol)
  left join pair_edges pair using (cancer_type, gene_symbol)
  left join mutation_provenance using (cancer_type, gene_symbol)
  left join tcga_expression_provenance using (cancer_type, gene_symbol)
  left join gtex_expression_provenance using (cancer_type, gene_symbol)
),
concordance as (
  select *,
    case
      when not expression_evidence then 'not_applicable'
      when sensitivity_direction = 'unavailable' then 'unavailable'
      when (raw_expression_direction = 'raw_up' and sensitivity_direction = 'rank_up')
        or (raw_expression_direction = 'raw_down' and sensitivity_direction = 'rank_down')
        or (raw_expression_direction = 'raw_stable' and sensitivity_direction = 'stable')
      then 'concordant'
      when (raw_expression_direction = 'raw_up' and sensitivity_direction = 'rank_down')
        or (raw_expression_direction = 'raw_down' and sensitivity_direction = 'rank_up')
      then 'discordant'
      else 'inconclusive'
    end as batch_concordance
  from joined
),
batch_scored as (
  select *,
    case
      when batch_concordance = 'concordant' and sensitivity_support_tier = 'high' then 1.0
      when batch_concordance = 'concordant' and sensitivity_support_tier = 'moderate' then 0.8
      when batch_concordance = 'concordant' then 0.6
      when batch_concordance = 'inconclusive' and sensitivity_support_tier = 'high' then 0.5
      when batch_concordance = 'inconclusive' and sensitivity_support_tier = 'moderate' then 0.4
      when batch_concordance = 'inconclusive' then 0.3
      else 0.0
    end as batch_sensitivity_confidence
  from concordance
),
components as (
  select *,
    case when mutation_evidence then
      0.55 * least(greatest(total_profiled_sample_count / 100.0, 0.0), 1.0)
      + 0.45 * least(greatest(mutated_sample_count / 20.0, 0.0), 1.0)
    else 0.0 end as mutation_confidence,
    case when expression_evidence then
      (
        0.5 * least(greatest(sample_count_tumor / 30.0, 0.0), 1.0)
        + 0.5 * least(greatest(sample_count_normal / 30.0, 0.0), 1.0)
      ) * 0.5 * (0.5 + 0.5 * batch_sensitivity_confidence)
    else 0.0 end as expression_confidence,
    cast(graph_pair_edge as integer) * 0.5
      + least(greatest(gene_graph_degree / 5.0, 0.0), 1.0) * 0.5 as graph_confidence,
    case when mutation_frequency between 0.0 and 1.0
      and mutated_sample_count <= total_profiled_sample_count
      and (not expression_evidence or (sample_count_tumor > 0 and sample_count_normal > 0))
    then 1.0 else 0.0 end as quality_confidence,
    case
      when mutation_evidence and expression_evidence then
        (coalesce(mutation_provenance, 0.0)
          + (coalesce(tcga_expression_provenance, 0.0) + coalesce(gtex_expression_provenance, 0.0)) / 2.0) / 2.0
      when mutation_evidence then coalesce(mutation_provenance, 0.0)
      when expression_evidence then
        (coalesce(tcga_expression_provenance, 0.0) + coalesce(gtex_expression_provenance, 0.0)) / 2.0
      else 0.0
    end as traceability_confidence
  from batch_scored
),
biological as (
  select *,
    case
      when mutation_evidence and expression_evidence then mutation_confidence * 0.6 + expression_confidence * 0.4
      when mutation_evidence then mutation_confidence
      when expression_evidence then expression_confidence
      else 0.0
    end as biological_confidence
  from components
),
scored as (
  select *, round(least(greatest(
    biological_confidence * 0.75
      + graph_confidence * 0.10
      + quality_confidence * 0.075
      + traceability_confidence * 0.075,
    0.0), 1.0), 6) as overall_confidence
  from biological
)
select
  cancer_type,
  gene_symbol,
  priority_score,
  priority_tier,
  mutation_frequency,
  mutated_sample_count,
  total_profiled_sample_count,
  log2_fold_change,
  abs_log2_fold_change,
  cast(sample_count_tumor as bigint) as sample_count_tumor,
  cast(sample_count_normal as bigint) as sample_count_normal,
  cast(gene_graph_degree as bigint) as gene_graph_degree,
  mutation_evidence,
  expression_evidence,
  mutation_confidence,
  expression_confidence,
  batch_sensitivity_confidence,
  graph_confidence,
  quality_confidence,
  traceability_confidence,
  biological_confidence,
  overall_confidence,
  case
    when overall_confidence >= 0.75 then 'high'
    when overall_confidence >= 0.50 then 'moderate'
    when overall_confidence >= 0.25 then 'limited'
    else 'low'
  end as confidence_tier,
  raw_expression_direction,
  sensitivity_direction,
  sensitivity_support_tier,
  batch_concordance,
  percentile_delta,
  robust_z_delta,
  case
    when not expression_evidence then 'not_applicable'
    when batch_concordance in ('discordant', 'unavailable') then 'high'
    else 'elevated'
  end as batch_effect_risk,
  case when quality_confidence = 1.0 then 'passed' else 'failed' end as quality_status,
  case
    when traceability_confidence >= 0.999 then 'passed'
    when traceability_confidence > 0.0 then 'warning'
    else 'failed'
  end as traceability_status,
  concat_ws(';',
    case when expression_evidence then 'cross_study_batch_effect_unadjusted' end,
    case when expression_evidence and batch_concordance = 'discordant' then 'batch_sensitivity_direction_discordant' end,
    case when expression_evidence and batch_concordance = 'inconclusive' then 'batch_sensitivity_direction_inconclusive' end,
    case when expression_evidence and batch_concordance = 'unavailable' then 'batch_sensitivity_unavailable' end,
    case when expression_evidence and sample_count_normal < 30 then 'gtex_normal_support_below_30' end,
    case when expression_evidence and sample_count_tumor < 30 then 'tcga_tumor_support_below_30' end,
    case when mutation_evidence and total_profiled_sample_count < 100 then 'mutation_profiled_support_below_100' end,
    case when cast(mutation_evidence as integer) + cast(expression_evidence as integer) < 2 then 'single_biological_modality' end,
    case when traceability_confidence < 1.0 then 'source_provenance_incomplete' end,
    case when graph_confidence = 0.0 then 'graph_support_absent' end
  ) as caveat_summary
from scored
