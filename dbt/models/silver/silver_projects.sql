select distinct
  cast(project_id as varchar) as project_id,
  cast(primary_site as varchar) as primary_site,
  cast(disease_type as varchar) as disease_type
from {{ ref('stg_silver_projects') }}
where project_id is not null
