with sample_counts as (
  select
    project_id as cancer_type,
    count(distinct sample_id) as total_profiled_sample_count
  from {{ ref('silver_samples') }}
  group by 1
),
mutation_counts as (
  select
    project_id as cancer_type,
    count(distinct sample_id) as mutated_sample_count,
    count(*) as mutation_event_count
  from {{ ref('silver_mutations') }}
  group by 1
)
select
  s.cancer_type,
  s.total_profiled_sample_count,
  coalesce(m.mutated_sample_count, 0) as mutated_sample_count,
  coalesce(m.mutation_event_count, 0) as mutation_event_count,
  case
    when s.total_profiled_sample_count = 0 then 0.0
    else cast(coalesce(m.mutation_event_count, 0) as double) / cast(s.total_profiled_sample_count as double)
  end as mutation_event_rate
from sample_counts s
left join mutation_counts m
  on s.cancer_type = m.cancer_type
