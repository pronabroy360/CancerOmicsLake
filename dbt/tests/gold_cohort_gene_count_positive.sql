select *
from {{ ref('gold_cohort_summary') }}
where gene_count <= 0
