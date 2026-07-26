with project_counts as (
  select count(distinct project_id) as tcga_project_count
  from {{ ref('silver_projects') }}
),
patient_counts as (
  select count(distinct case_id) as tcga_patient_count
  from {{ ref('silver_patients') }}
),
sample_counts as (
  select count(distinct sample_id) as tcga_sample_count
  from {{ ref('silver_samples') }}
),
file_counts as (
  select count(distinct file_id) as tcga_file_count
  from {{ ref('silver_file_manifest') }}
),
gtex_sample_counts as (
  select count(distinct gtex_sample_id) as gtex_expression_sample_count
  from {{ ref('silver_expression_gtex') }}
),
tcga_expr_rows as (
  select count(*) as tcga_expression_row_count
  from {{ ref('silver_expression_tcga') }}
),
gtex_expr_rows as (
  select count(*) as gtex_expression_row_count
  from {{ ref('silver_expression_gtex') }}
),
gene_counts as (
  select count(distinct gene_id) as gene_count
  from (
    select gene_id
    from {{ ref('silver_expression_tcga') }}
    where gene_id is not null
    union all
    select gene_id
    from {{ ref('silver_expression_gtex') }}
    where gene_id is not null
  ) expression_genes
),
mutation_rows as (
  select
    count(*) as mutation_record_count,
    sum(case when is_protein_altering then 1 else 0 end) as protein_altering_mutation_record_count
  from {{ ref('silver_mutations') }}
),
mutation_profile_counts as (
  select count(distinct sample_id) as mutation_profiled_sample_count
  from {{ ref('silver_mutation_profile') }}
)
select
  p.tcga_project_count,
  pa.tcga_patient_count,
  s.tcga_sample_count,
  f.tcga_file_count,
  g.gtex_expression_sample_count,
  te.tcga_expression_row_count,
  ge.gtex_expression_row_count,
  gn.gene_count,
  m.mutation_record_count,
  m.protein_altering_mutation_record_count,
  mp.mutation_profiled_sample_count,
  current_timestamp as generated_at
from project_counts p
cross join patient_counts pa
cross join sample_counts s
cross join file_counts f
cross join gtex_sample_counts g
cross join tcga_expr_rows te
cross join gtex_expr_rows ge
cross join gene_counts gn
cross join mutation_rows m
cross join mutation_profile_counts mp
