select *
from {{ ref('gold_mutation_functional_evidence') }}
where recurrent_locus_sample_fraction < 0.0
   or recurrent_locus_sample_fraction > 1.0
   or protein_altering_mutated_sample_count > total_profiled_sample_count
   or samples_with_recurrent_locus_count > protein_altering_mutated_sample_count
   or max_locus_sample_count > protein_altering_mutated_sample_count
   or recurrence_threshold_samples < 2
   or driver_evidence_scope != 'consequence_and_exact_locus_recurrence'
   or driver_classification != 'not_assessed'
