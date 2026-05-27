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
