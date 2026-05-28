with has_sample as (
  select distinct
    concat('HAS_SAMPLE:', case_id, ':', sample_id) as edge_id,
    concat('PATIENT:', case_id) as source_node_id,
    concat('SAMPLE:', sample_id) as target_node_id,
    'HAS_SAMPLE' as edge_type,
    1.0 as weight,
    'TCGA' as evidence_source
  from {{ ref('silver_samples') }}
),
belongs_to_cancer as (
  select distinct
    concat('BELONGS_TO_CANCER:', sample_id, ':', project_id) as edge_id,
    concat('SAMPLE:', sample_id) as source_node_id,
    project_id as target_node_id,
    'BELONGS_TO_CANCER' as edge_type,
    1.0 as weight,
    'TCGA' as evidence_source
  from {{ ref('silver_samples') }}
),
mutated_in_cancer as (
  select
    concat('MUTATED_IN_CANCER:', gene_symbol, ':', cancer_type) as edge_id,
    concat('GENE:', gene_symbol) as source_node_id,
    cancer_type as target_node_id,
    'MUTATED_IN_CANCER' as edge_type,
    mutation_frequency as weight,
    'TCGA' as evidence_source
  from {{ ref('gold_mutation_frequency_by_gene') }}
),
expressed_in_tissue as (
  select
    concat('EXPRESSED_IN_TISSUE:', gene_symbol, ':', tissue_site) as edge_id,
    concat('GENE:', gene_symbol) as source_node_id,
    concat('TISSUE:', tissue_site) as target_node_id,
    'EXPRESSED_IN_TISSUE' as edge_type,
    avg(log2_expression) as weight,
    'GTEx' as evidence_source
  from {{ ref('silver_expression_gtex') }}
  group by 1, 2, 3, 4, 6
)
select * from has_sample
union all select * from belongs_to_cancer
union all select * from mutated_in_cancer
union all select * from expressed_in_tissue
