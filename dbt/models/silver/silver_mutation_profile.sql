select
  cast(project_id as varchar) as project_id,
  cast(case_id as varchar) as case_id,
  cast(sample_id as varchar) as sample_id,
  cast(file_id as varchar) as file_id,
  cast(file_name as varchar) as file_name,
  cast(file_size as bigint) as file_size,
  cast(md5sum as varchar) as md5sum,
  cast(data_origin as varchar) as data_origin,
  cast(profile_status as varchar) as profile_status,
  cast(ingested_at as varchar) as ingested_at
from {{ ref('stg_silver_mutation_profile') }}
where coalesce(trim(project_id), '') <> ''
  and coalesce(trim(sample_id), '') <> ''
  and profile_status = 'downloaded'
