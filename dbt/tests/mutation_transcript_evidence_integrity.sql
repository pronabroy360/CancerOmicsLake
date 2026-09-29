select *
from {{ ref('gold_mutation_transcript_evidence') }}
where sample_fraction < 0.0
   or sample_fraction > 1.0
   or distinct_sample_count > profiled_sample_count
   or hgvsc_annotation_event_count > event_count
   or hgvsp_annotation_event_count > event_count
   or all_effects_annotation_event_count > event_count
   or annotation_scope != 'gdc_maf_reported_transcript'
   or impact_interpretation != 'source_vep_category_not_driver_classification'
