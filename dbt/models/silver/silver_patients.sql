select distinct
  cast(project_id as varchar) as project_id,
  cast(case_id as varchar) as case_id,
  cast(submitter_id as varchar) as submitter_id
from {{ ref('stg_silver_patients') }}
where project_id is not null and case_id is not null
