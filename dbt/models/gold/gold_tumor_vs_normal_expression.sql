with tissue_map as (
  select 'TCGA-BRCA' as project_id, 'Breast - Mammary Tissue' as tissue_site
  union all select 'TCGA-BRCA', 'Breast'
  union all select 'TCGA-LUAD', 'Lung'
  union all select 'TCGA-COAD', 'Colon - Transverse'
  union all select 'TCGA-COAD', 'Colon - Sigmoid'
  union all select 'TCGA-COAD', 'Colon'
),
tcga_tumor as (
  select
    project_id,
    gene_symbol,
    median(expression_value) as median_tcga_tumor_expression,
    avg(expression_value) as mean_tcga_tumor_expression,
    count(distinct sample_id) as sample_count_tumor
  from {{ ref('silver_expression_tcga') }}
  where lower(sample_type) like '%tumor%'
  group by 1, 2
),
gtex_normal as (
  select
    m.project_id,
    g.gene_symbol,
    median(g.expression_value) as median_gtex_normal_expression,
    avg(g.expression_value) as mean_gtex_normal_expression,
    count(distinct g.gtex_sample_id) as sample_count_normal
  from {{ ref('silver_expression_gtex') }} g
  join tissue_map m
    on g.tissue_site = m.tissue_site
  group by 1, 2
)
select
  t.gene_symbol,
  t.project_id as cancer_type,
  t.median_tcga_tumor_expression,
  n.median_gtex_normal_expression,
  t.mean_tcga_tumor_expression,
  n.mean_gtex_normal_expression,
  ln((t.median_tcga_tumor_expression + 1.0) / (n.median_gtex_normal_expression + 1.0)) / ln(2.0) as log2_fold_change,
  t.sample_count_tumor,
  n.sample_count_normal
from tcga_tumor t
join gtex_normal n
  on t.project_id = n.project_id
  and t.gene_symbol = n.gene_symbol
