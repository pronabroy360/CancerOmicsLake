select
  cast(project_id as varchar) as project_id,
  cast(case_id as varchar) as case_id,
  cast(sample_id as varchar) as sample_id,
  cast(file_id as varchar) as file_id,
  cast(file_name as varchar) as file_name,
  cast(data_category as varchar) as data_category,
  cast(data_type as varchar) as data_type,
  cast(experimental_strategy as varchar) as experimental_strategy,
  cast(workflow_type as varchar) as workflow_type,
  cast(access as varchar) as access,
  cast(file_size as bigint) as file_size,
  cast(md5sum as varchar) as md5sum,
  cast(ingested_at as varchar) as ingested_at
from {{ ref('stg_silver_file_manifest') }}
