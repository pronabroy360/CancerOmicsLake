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
make run-demo
```

Default cap:

- TCGA projects: `TCGA-BRCA`, `TCGA-LUAD`, `TCGA-COAD`
- Expression files: `25/project`
- Mutation files: `10/project`
- Access mode: open-access only

Selection is deterministic so repeated runs choose the same files unless source metadata changes. Reports include requested cap, candidate count, selected count, downloaded count, skipped-existing count, and failed count.

## Reviewer Demo Check

Use the demo verifier after a pipeline run:

```bash
make run-demo-check
make run-demo-check-strict
```

`make run-demo-check` validates:

- required silver and gold parquet tables are readable and non-empty
- mutation marts are available
- latest quality report has a passing or warning-only status
- Graphify and Neo4j exports exist and contain rows
- FastAPI `/health` responds
- dashboard data loaders can read overview, cohort, mutation, graph, and quality data

`make run-demo-check-strict` additionally rejects stub/demo-origin rows and requires the latest GDC audit source mode to be `live`.

## CI And Scheduled Runs

- CI runs on push and pull request.
- Daily scheduled automation runs from `.github/workflows/ci.yml`.
- Python `3.11` is the source-of-truth runtime for dbt in CI.
- Local Python `3.14` remains acceptable for non-dbt pipeline commands.
- CI executes `make test`, metadata/silver/gold/quality stages, `dbt run`, `dbt test`, `make run-graph-export`, and `make run-demo-check`.
- CI uploads operational artifacts so run state is reviewable without committing generated outputs.

## Run Metadata

Pipeline/report artifacts are written under `outputs/reports/`:

- `gdc_ingestion_audit.json`
- `tcga_download_report.json`
- `tcga_download_retry_log.json`
- `ingestion_traceability_report.json`
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
