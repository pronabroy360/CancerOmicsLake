select
  cast(project_id as varchar) as project_id,
  cast(case_id as varchar) as case_id,
  cast(sample_id as varchar) as sample_id,
  cast(sample_type as varchar) as sample_type,
  cast(gene_id as varchar) as gene_id,
  cast(gene_symbol as varchar) as gene_symbol,
  cast(expression_value as double) as expression_value,
  cast(expression_unit as varchar) as expression_unit,
  cast(log2_expression as double) as log2_expression,
  cast(pipeline_workflow as varchar) as pipeline_workflow,
  cast(data_origin as varchar) as data_origin,
  cast(ingested_at as varchar) as ingested_at
from {{ ref('stg_silver_expression_tcga') }}
where coalesce(trim(gene_id), '') <> ''
  and cast(expression_value as double) >= 0
