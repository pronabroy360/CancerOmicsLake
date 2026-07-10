with cancer_nodes as (
  select distinct
    project_id as node_id,
    'CancerType' as node_label,
    project_id as name,
    primary_site,
    'TCGA' as source
  from {{ ref('silver_projects') }}
),
gene_symbols as (
  select gene_symbol from {{ ref('silver_mutations') }}
  union
  select gene_symbol from {{ ref('silver_expression_gtex') }}
),
gene_nodes as (
  select distinct
    concat('GENE:', gene_symbol) as node_id,
    'Gene' as node_label,
    gene_symbol as name,
    cast(null as varchar) as primary_site,
    'TCGA/GTEx' as source
  from gene_symbols
  where coalesce(trim(gene_symbol), '') <> ''
),
sample_nodes as (
  select distinct
    concat('SAMPLE:', sample_id) as node_id,
    'Sample' as node_label,
    sample_id as name,
    project_id as primary_site,
    'TCGA' as source
  from {{ ref('silver_samples') }}
),
patient_nodes as (
  select distinct
    concat('PATIENT:', case_id) as node_id,
    'Patient' as node_label,
    case_id as name,
    project_id as primary_site,
    'TCGA' as source
  from {{ ref('silver_patients') }}
),
tissue_nodes as (
  select distinct
    concat('TISSUE:', tissue_site) as node_id,
    'Tissue' as node_label,
    tissue_site as name,
    tissue_site as primary_site,
    'GTEx' as source
  from {{ ref('silver_expression_gtex') }}
),
dataset_nodes as (
  select 'DATASET:TCGA' as node_id, 'Dataset' as node_label, 'TCGA' as name, 'Multi' as primary_site, 'TCGA' as source
  union all
  select 'DATASET:GTEX', 'Dataset', 'GTEx', 'Multi', 'GTEx'
)
select * from cancer_nodes
union all select * from gene_nodes
union all select * from sample_nodes
union all select * from patient_nodes
union all select * from tissue_nodes
union all select * from dataset_nodes
