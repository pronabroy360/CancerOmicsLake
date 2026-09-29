with mutation_samples as (
  select distinct project_id, case_id, sample_id
  from {{ ref('silver_mutations') }}
),
profile_samples as (
  select distinct project_id, case_id, sample_id
  from {{ ref('silver_mutation_profile') }}
)
select m.*
from mutation_samples m
left join profile_samples p
  on m.project_id = p.project_id
  and m.case_id = p.case_id
  and m.sample_id = p.sample_id
where p.sample_id is null
