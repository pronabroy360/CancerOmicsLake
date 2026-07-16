select *
from {{ ref('gold_mutation_frequency_by_gene') }}
where mutation_frequency < 0.0
   or mutation_frequency > 1.0
   or mutated_sample_count > total_profiled_sample_count
   or upper(top_variant_classification) = 'SILENT'
   or protein_altering_event_count > all_somatic_event_count
