select *
from {{ ref('silver_mutations') }}
where is_protein_altering != (consequence_group = 'protein_altering')
