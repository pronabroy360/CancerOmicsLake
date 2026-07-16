select
  cast(project_id as varchar) as project_id,
  cast(case_id as varchar) as case_id,
  cast(sample_id as varchar) as sample_id,
  cast(gene_id as varchar) as gene_id,
  cast(gene_symbol as varchar) as gene_symbol,
  cast(variant_classification as varchar) as variant_classification,
  cast(consequence_group as varchar) as consequence_group,
  cast(is_protein_altering as boolean) as is_protein_altering,
  cast(variant_type as varchar) as variant_type,
  cast(chromosome as varchar) as chromosome,
  cast(start_position as bigint) as start_position,
  cast(end_position as bigint) as end_position,
  cast(reference_allele as varchar) as reference_allele,
  cast(tumor_seq_allele as varchar) as tumor_seq_allele,
  cast(data_origin as varchar) as data_origin,
  cast(ingested_at as varchar) as ingested_at
from {{ ref('stg_silver_mutations') }}
where coalesce(trim(gene_symbol), '') <> ''
  and cast(start_position as bigint) is not null
  and cast(end_position as bigint) is not null
