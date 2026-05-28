# Reproducibility

CancerOmicsLake is designed so the same pipeline can run in lightweight local mode, medium capped real-ingestion mode, and scheduled CI mode without changing code.

## Local Setup

```bash
make setup
make validate-config
make run-metadata
make run-metadata-strict
make run-metadata-strict-smoke
make run-silver
make run-gold
make run-quality
make test
```

## Medium Capped Live Profile

Use the medium profile when you want a bounded real-data run:

```bash
make run-download-tcga-medium
make run-flow-medium
```

Default cap:

- TCGA projects: `TCGA-BRCA`, `TCGA-LUAD`, `TCGA-COAD`
- Expression files: `25/project`
- Mutation files: `10/project`
- Access mode: open-access only

Selection is deterministic so repeated runs choose the same files unless source metadata changes. Reports include requested cap, candidate count, selected count, downloaded count, skipped-existing count, and failed count.

## CI And Scheduled Runs

- CI runs on push and pull request.
- Daily scheduled automation runs from `.github/workflows/ci.yml`.
- Python `3.11` is the source-of-truth runtime for dbt in CI.
- Local Python `3.14` remains acceptable for non-dbt pipeline commands.
- CI executes `make test`, metadata/silver/gold/quality stages, `dbt run`, and `dbt test`.
- CI uploads operational artifacts so run state is reviewable without committing generated outputs.

## Run Metadata

Pipeline/report artifacts are written under `outputs/reports/`:

- `gdc_ingestion_audit.json`
- `tcga_download_report.json`
- `tcga_download_retry_log.json`
- `silver_data_quality_report.json`
- `data_quality_report.json`
- `pipeline_run_metadata.json`
- `pipeline_run_history.json`

Reports include `run_mode` where available:

- `manual`
- `push`
- `scheduled`
- `unknown`

## Data Locations

- TCGA files: `data/bronze/tcga/**/expression/*.tsv|*.csv|*.txt`
- TCGA mutation files: `data/bronze/tcga/**/mutations/*.maf|*.tsv|*.csv|*.txt`
- GTEx expression files: `data/bronze/gtex/expression/*.tsv|*.csv|*.txt`
- Silver parquet tables: `data/silver/**`
- Gold parquet tables: `data/gold/**`
- Graph exports: `outputs/graph_exports/**`

## Notes

- Public mode is open-access-only.
- Use synthetic or aggregate outputs for GitHub publishing.
- Metadata runs write GDC ingestion audit details to `outputs/reports/gdc_ingestion_audit.json`.
- Set `tcga.require_live_gdc: true` to fail fast if live GDC query is unavailable.
- Silver quality checks write `outputs/reports/silver_data_quality_report.json`.
- Tumor-vs-normal comparisons are exploratory because TCGA and GTEx have cross-study and pipeline batch effects.
- Generated raw data, credentials, and controlled-access files must not be committed.
