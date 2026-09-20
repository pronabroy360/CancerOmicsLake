with protein_events as (
  select
    project_id as cancer_type,
    sample_id,
    gene_symbol,
    chromosome,
    start_position,
    reference_allele,
    tumor_seq_allele,
    case
      when upper(variant_classification) in (
        'FRAME_SHIFT_DEL', 'FRAME_SHIFT_INS', 'NONSENSE_MUTATION',
        'NONSTOP_MUTATION', 'SPLICE_SITE', 'TRANSLATION_START_SITE'
      ) then 'putative_loss_of_function'
      when upper(variant_classification) = 'MISSENSE_MUTATION' then 'missense'
      when upper(variant_classification) in (
        'DE_NOVO_START_INFRAME', 'IN_FRAME_DEL', 'IN_FRAME_INS',
        'START_CODON_DEL', 'START_CODON_INS', 'STOP_CODON_DEL', 'STOP_CODON_INS'
      ) then 'inframe'
      else 'other_protein_altering'
    end as functional_impact_group
  from {{ ref('silver_mutations') }}
  where is_protein_altering
),
sample_counts as (
  select project_id as cancer_type, count(distinct sample_id) as total_profiled_sample_count
  from {{ ref('silver_mutation_profile') }}
  group by 1
),
gene_counts as (
  select
    cancer_type,
    gene_symbol,
    count(distinct sample_id) as protein_altering_mutated_sample_count,
    count(distinct case when functional_impact_group = 'putative_loss_of_function' then sample_id end)
      as putative_loss_of_function_sample_count,
    count(distinct case when functional_impact_group = 'missense' then sample_id end) as missense_sample_count,
    count(distinct case when functional_impact_group = 'inframe' then sample_id end) as inframe_sample_count,
    count(distinct case when functional_impact_group = 'other_protein_altering' then sample_id end)
      as other_protein_altering_sample_count
  from protein_events
  group by 1, 2
),
locus_counts as (
  select
    cancer_type, gene_symbol, chromosome, start_position, reference_allele, tumor_seq_allele,
    count(distinct sample_id) as locus_sample_count
  from protein_events
  group by 1, 2, 3, 4, 5, 6
  having count(distinct sample_id) >= 2
),
recurrent_summary as (
  select
    cancer_type,
    gene_symbol,
    count(*) as recurrent_locus_count,
    max(locus_sample_count) as max_locus_sample_count
  from locus_counts
  group by 1, 2
),
recurrent_samples as (
  select
    p.cancer_type,
    p.gene_symbol,
    count(distinct p.sample_id) as samples_with_recurrent_locus_count
  from protein_events p
  inner join locus_counts l
    on p.cancer_type = l.cancer_type
    and p.gene_symbol = l.gene_symbol
    and p.chromosome = l.chromosome
    and p.start_position = l.start_position
    and p.reference_allele = l.reference_allele
    and p.tumor_seq_allele = l.tumor_seq_allele
  group by 1, 2
)
select
  g.gene_symbol,
  g.cancer_type,
  coalesce(s.total_profiled_sample_count, 0) as total_profiled_sample_count,
  g.protein_altering_mutated_sample_count,
  g.putative_loss_of_function_sample_count,
  g.missense_sample_count,
  g.inframe_sample_count,
  g.other_protein_altering_sample_count,
  coalesce(r.recurrent_locus_count, 0) as recurrent_locus_count,
  coalesce(r.max_locus_sample_count, 0) as max_locus_sample_count,
  coalesce(rs.samples_with_recurrent_locus_count, 0) as samples_with_recurrent_locus_count,
  case
    when coalesce(s.total_profiled_sample_count, 0) = 0 then 0.0
    else cast(coalesce(rs.samples_with_recurrent_locus_count, 0) as double)
      / cast(s.total_profiled_sample_count as double)
  end as recurrent_locus_sample_fraction,
  2 as recurrence_threshold_samples,
  'consequence_and_exact_locus_recurrence' as driver_evidence_scope,
  'not_assessed' as driver_classification
from gene_counts g
left join sample_counts s using (cancer_type)
left join recurrent_summary r using (cancer_type, gene_symbol)
left join recurrent_samples rs using (cancer_type, gene_symbol)
