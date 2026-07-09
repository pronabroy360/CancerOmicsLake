with mutation_component as (
  select
    cancer_type,
    gene_symbol,
    mutation_frequency,
    mutated_sample_count,
    total_profiled_sample_count
  from {{ ref('gold_mutation_frequency_by_gene') }}
),
expression_component as (
  select
    cancer_type,
    gene_symbol,
    log2_fold_change,
    abs(log2_fold_change) as abs_log2_fold_change
  from {{ ref('gold_tumor_vs_normal_expression') }}
),
candidate_keys as (
  select cancer_type, gene_symbol from mutation_component
  union
  select cancer_type, gene_symbol from expression_component
),
joined as (
  select
    k.cancer_type,
    k.gene_symbol,
    coalesce(m.mutation_frequency, 0.0) as mutation_frequency,
    coalesce(m.mutated_sample_count, 0) as mutated_sample_count,
    coalesce(m.total_profiled_sample_count, 0) as total_profiled_sample_count,
    coalesce(e.abs_log2_fold_change, 0.0) as abs_log2_fold_change,
    coalesce(e.log2_fold_change, 0.0) as log2_fold_change
  from candidate_keys k
  left join mutation_component m
    on k.cancer_type = m.cancer_type
    and k.gene_symbol = m.gene_symbol
  left join expression_component e
    on k.cancer_type = e.cancer_type
    and k.gene_symbol = e.gene_symbol
),
max_values as (
  select
    case
      when max(abs_log2_fold_change) > 0 then max(abs_log2_fold_change)
      else 1.0
    end as max_abs_log2_fold_change
  from joined
)
select
  j.cancer_type,
  j.gene_symbol,
  j.mutation_frequency,
  j.mutated_sample_count,
  j.total_profiled_sample_count,
  j.abs_log2_fold_change,
  j.log2_fold_change,
  (
    case when j.mutation_frequency > 0 then 1 else 0 end
    + case when j.abs_log2_fold_change > 0 then 1 else 0 end
  ) as graph_degree,
  (
    case when j.mutation_frequency > 0 then 1 else 0 end
    + case when j.abs_log2_fold_change > 0 then 1 else 0 end
  ) as evidence_count,
  round(
    (least(greatest(j.mutation_frequency, 0.0), 1.0) * 0.65)
    + (least(greatest(j.abs_log2_fold_change / m.max_abs_log2_fold_change, 0.0), 1.0) * 0.25)
    + (
      (
        case when j.mutation_frequency > 0 then 1 else 0 end
        + case when j.abs_log2_fold_change > 0 then 1 else 0 end
      ) / 2.0 * 0.10
    ),
    6
  ) as priority_score,
  case
    when (
      (least(greatest(j.mutation_frequency, 0.0), 1.0) * 0.65)
      + (least(greatest(j.abs_log2_fold_change / m.max_abs_log2_fold_change, 0.0), 1.0) * 0.25)
      + (
        (
          case when j.mutation_frequency > 0 then 1 else 0 end
          + case when j.abs_log2_fold_change > 0 then 1 else 0 end
        ) / 2.0 * 0.10
      )
    ) >= 0.50 then 'high'
    when (
      (least(greatest(j.mutation_frequency, 0.0), 1.0) * 0.65)
      + (least(greatest(j.abs_log2_fold_change / m.max_abs_log2_fold_change, 0.0), 1.0) * 0.25)
      + (
        (
          case when j.mutation_frequency > 0 then 1 else 0 end
          + case when j.abs_log2_fold_change > 0 then 1 else 0 end
        ) / 2.0 * 0.10
      )
    ) >= 0.20 then 'medium'
    else 'low'
  end as priority_tier,
  concat(
    'mutation_frequency=',
    cast(round(j.mutation_frequency, 4) as varchar),
    ';abs_log2_fold_change=',
    cast(round(j.abs_log2_fold_change, 4) as varchar)
  ) as evidence_summary
from joined j
cross join max_values m
