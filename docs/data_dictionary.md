# Data Dictionary

This file will define table schemas for silver and gold layers.

Initial target tables are documented in `PRD.md`.

Current implemented silver outputs:

- `silver_projects.parquet`
  - `project_id`, `primary_site`, `disease_type`
- `silver_patients.parquet`
  - `project_id`, `case_id`, `submitter_id`
- `silver_samples.parquet`
  - `project_id`, `case_id`, `sample_id`, `sample_type`
- `silver_file_manifest.parquet`
  - `project_id`, `case_id`, `sample_id`, `file_id`, `file_name`, `data_category`, `data_type`, `experimental_strategy`, `workflow_type`, `access`, `file_size`, `md5sum`, `ingested_at`
- `silver_expression_tcga.parquet`
  - `project_id`, `case_id`, `sample_id`, `sample_type`, `gene_id`, `gene_symbol`, `expression_value`, `expression_unit`, `log2_expression`, `pipeline_workflow`, `data_origin`, `ingested_at`
- `silver_expression_gtex.parquet`
  - `gtex_sample_id`, `tissue_site`, `tissue_detail`, `gene_id`, `gene_symbol`, `expression_value`, `expression_unit`, `log2_expression`, `source_version`, `data_origin`, `ingested_at`

Current implemented gold outputs:

- `gold_cohort_summary.parquet`
  - `tcga_project_count`, `tcga_patient_count`, `tcga_sample_count`, `tcga_file_count`, `gtex_expression_sample_count`, `tcga_expression_row_count`, `gtex_expression_row_count`, `gene_count`, `mutation_record_count`, `generated_at`
