select
  cast(gtex_sample_id as varchar) as gtex_sample_id,
  cast(donor_id as varchar) as donor_id,
  cast(tissue_site as varchar) as tissue_site,
  cast(tissue_detail as varchar) as tissue_detail,
  cast(gene_id as varchar) as gene_id,
  cast(gene_symbol as varchar) as gene_symbol,
  cast(expression_value as double) as expression_value,
  cast(expression_unit as varchar) as expression_unit,
  cast(log2_expression as double) as log2_expression,
  cast(source_version as varchar) as source_version,
  cast(data_origin as varchar) as data_origin,
  cast(ingested_at as varchar) as ingested_at
from {{ ref('stg_silver_expression_gtex') }}
where coalesce(trim(gene_id), '') <> ''
  and cast(expression_value as double) >= 0
