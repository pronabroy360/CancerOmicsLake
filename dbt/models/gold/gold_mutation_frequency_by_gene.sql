with sample_counts as (
  select
    project_id as cancer_type,
    count(distinct sample_id) as total_profiled_sample_count
  from {{ ref('silver_mutation_profile') }}
  group by 1
),
mutation_counts as (
  select
    project_id as cancer_type,
    gene_symbol,
    count(distinct sample_id) as mutated_sample_count,
    count(*) as protein_altering_event_count
  from {{ ref('silver_mutations') }}
  where is_protein_altering
  group by 1, 2
),
all_event_counts as (
  select
    project_id as cancer_type,
    gene_symbol,
    count(*) as all_somatic_event_count,
    sum(case when upper(variant_classification) = 'SILENT' then 1 else 0 end) as synonymous_event_count
  from {{ ref('silver_mutations') }}
  group by 1, 2
),
variant_counts as (
  select
    project_id as cancer_type,
    gene_symbol,
    variant_classification,
    count(*) as variant_count
  from {{ ref('silver_mutations') }}
  where is_protein_altering
  group by 1, 2, 3
),
variant_ranked as (
  select
    *,
    row_number() over (
      partition by cancer_type, gene_symbol
      order by variant_count desc, variant_classification asc
    ) as rn
  from variant_counts
)
select
  m.gene_symbol,
  m.cancer_type,
  m.mutated_sample_count,
  coalesce(s.total_profiled_sample_count, 0) as total_profiled_sample_count,
  case
    when coalesce(s.total_profiled_sample_count, 0) = 0 then 0.0
    else cast(m.mutated_sample_count as double) / cast(s.total_profiled_sample_count as double)
  end as mutation_frequency,
  coalesce(v.variant_classification, 'Unknown') as top_variant_classification,
  m.protein_altering_event_count,
  coalesce(a.all_somatic_event_count, 0) as all_somatic_event_count,
  coalesce(a.synonymous_event_count, 0) as synonymous_event_count,
  'protein_altering_only' as mutation_scope
from mutation_counts m
left join sample_counts s
  on m.cancer_type = s.cancer_type
left join variant_ranked v
  on m.cancer_type = v.cancer_type
  and m.gene_symbol = v.gene_symbol
  and v.rn = 1
left join all_event_counts a
  on m.cancer_type = a.cancer_type
  and m.gene_symbol = a.gene_symbol
