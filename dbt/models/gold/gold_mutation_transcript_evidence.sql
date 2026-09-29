with profile_counts as (
  select project_id as cancer_type, count(distinct sample_id) as profiled_sample_count
  from {{ ref('silver_mutation_profile') }}
  group by 1
),
transcript_counts as (
  select
    project_id as cancer_type,
    gene_symbol,
    coalesce(nullif(trim(transcript_id), ''), 'Unknown') as transcript_id,
    coalesce(nullif(trim(vep_consequence), ''), 'Unknown') as vep_consequence,
    coalesce(nullif(upper(trim(vep_impact)), ''), 'Unknown') as vep_impact,
    coalesce(nullif(trim(variant_classification), ''), 'Unknown') as variant_classification,
    count(distinct sample_id) as distinct_sample_count,
    count(*) as event_count,
    count(*) filter (where coalesce(trim(hgvsc), '') <> '') as hgvsc_annotation_event_count,
    count(*) filter (where coalesce(trim(hgvsp), '') <> '') as hgvsp_annotation_event_count,
    count(*) filter (where coalesce(trim(all_effects), '') <> '') as all_effects_annotation_event_count
  from {{ ref('silver_mutations') }}
  where coalesce(trim(gene_symbol), '') <> ''
  group by 1, 2, 3, 4, 5, 6
)
select
  t.cancer_type,
  t.gene_symbol,
  t.transcript_id,
  t.vep_consequence,
  t.vep_impact,
  t.variant_classification,
  coalesce(p.profiled_sample_count, 0) as profiled_sample_count,
  t.distinct_sample_count,
  t.event_count,
  case
    when coalesce(p.profiled_sample_count, 0) = 0 then 0.0
    else cast(t.distinct_sample_count as double) / cast(p.profiled_sample_count as double)
  end as sample_fraction,
  t.hgvsc_annotation_event_count,
  t.hgvsp_annotation_event_count,
  t.all_effects_annotation_event_count,
  'gdc_maf_reported_transcript' as annotation_scope,
  'source_vep_category_not_driver_classification' as impact_interpretation
from transcript_counts t
left join profile_counts p using (cancer_type)
