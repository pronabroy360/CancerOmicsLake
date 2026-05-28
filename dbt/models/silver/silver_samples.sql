select distinct
  cast(project_id as varchar) as project_id,
  cast(case_id as varchar) as case_id,
  cast(sample_id as varchar) as sample_id,
  cast(sample_type as varchar) as sample_type
from {{ ref('stg_silver_samples') }}
where project_id is not null and sample_id is not null
