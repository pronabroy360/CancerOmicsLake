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
make run-dbt
make test-dbt
make run-project-completion
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

## Aggressive Capped Live Profile

Use this when we want to complete ingestion quickly over a few days:

```bash
make run-download-tcga-aggressive
make run-download-tcga-normals
make run-metadata-strict
make run-download-tcga-paired
make run-silver
make run-bootstrap-stability
make run-recount3-expression
make run-external-validation
make run-expression-statistics
make run-paired-expression
make run-consensus-candidates
make run-pathway-enrichment
make run-flow-aggressive
make run-demo-aggressive
```

Aggressive cap:

- TCGA projects: `TCGA-BRCA`, `TCGA-LUAD`, `TCGA-COAD`
- Expression files: `100/project`
- Mutation files: `40/project`
- Access mode: open-access only
- Download workers: `8` for aggressive Make targets

Aggressive flow and demo targets force downloads (`--force-download`) so runs do not silently skip file pulling when `tcga.metadata_only: true`.
Aggressive flow and demo targets also scope downloads to `expression,mutations` via `--data-subdirs` so clinical/biospecimen categories do not create avoidable failures during rapid completion.
The downloader persists the exact selected file list in `outputs/reports/tcga_download_report.json`; quality checks validate those selected files rather than treating unselected capped candidates as missing data.
The expanded local run produces 37,002,600 TCGA expression rows and 45,588 mutation records. Reference
triangulation has 60 BRCA, 59 LUAD, and 41 COAD adjacent-normal samples alongside 95/94/96 primary tumors.
The silver build also writes `silver_mutation_profile.parquet` from mutation files physically present in bronze.
Gold mutation frequencies use this downloaded profile as the denominator and protein-altering events as the numerator.

## Reviewer Demo Check

Use the demo verifier after a pipeline run:

```bash
make run-demo-check
make run-demo-check-strict
```

`make run-demo-check` validates:

- required silver and gold parquet tables are readable and non-empty
- downloaded mutation-profile denominator and mutation marts are available
- latest quality report has a passing or warning-only status
- Graphify and Neo4j exports exist and contain rows
- FastAPI `/health` responds
- dashboard data loaders can read overview, cohort, mutation, graph, and quality data

`make run-demo-check-strict` additionally rejects stub/demo-origin rows and requires the latest GDC audit source mode to be `live`.

## CI And Scheduled Runs

- CI runs on push and pull request.
- Daily scheduled automation runs from `.github/workflows/ci.yml`.
- Manual high-throughput runs are available through `.github/workflows/manual_ingestion.yml`.
- Python `3.11` is the source-of-truth runtime for dbt in CI.
- Local Python `3.14` remains acceptable for non-dbt pipeline commands.
- Local dbt commands now auto-select execution mode:
  - local `.venv` dbt when the active Python is supported
  - Docker Compose `dbt` service when local Python is `3.14+`
- CI executes `make test`, metadata, `make run-download-tcga-ci-smoke`, silver/gold/quality stages, `dbt run`, `dbt test`, `make run-graph-export`, and `make run-demo-check`.
- The CI smoke download is intentionally tiny: one expression file and one mutation file per TCGA MVP project, capped at six attempted downloads.
- CI uploads operational artifacts so run state is reviewable without committing generated outputs.

## Manual GitHub Ingestion Workflow

Workflow: `CancerOmicsLake Manual Ingestion`

Inputs:

- `profile`: `medium` or `aggressive`
- `strict_no_stub`: run strict no-stub verifier after the selected profile
- `run_metadata_strict`: require live GDC metadata query

Behavior:

- runs tests and metadata stage first
- executes `make run-demo` (medium) or `make run-demo-aggressive` (aggressive)
- optionally executes `make run-demo-check-strict`
- uploads reports and graph exports as artifacts

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
- `dbt_execution_report.json`
- `project_completion_report.json`

Reports include `run_mode` where available:

- `manual`
- `push`
- `scheduled`
- `unknown`

## Data Locations

- TCGA files: `data/bronze/tcga/**/expression/*.tsv|*.csv|*.txt`
- TCGA mutation files: `data/bronze/tcga/**/mutations/*.maf|*.tsv|*.csv|*.txt`
- GTEx expression files: `data/bronze/gtex/expression/*.tsv|*.csv|*.txt`
- Live GTEx V8 profile: `make run-gtex-live` downloads official tissue GCT files and open sample annotations,
  verifies object size/MD5, selects 50 samples per tissue deterministically, validates tissue labels, and
  atomically writes `data/silver/silver_expression_gtex.parquet`.
- The live profile currently produces 11,240,000 rows from 200 samples. Re-running skips checksum-matching
  source files and rebuilds the harmonized Parquet reproducibly.
- Uniform recount3 validation profile: `make run-recount3-expression` downloads public tissue-level TCGA/GTEx
  gene-sum, metadata, QC, and GENCODE v26 files, selects 30 samples per cohort deterministically, applies 40-million
  AUC scaling, and writes `data/silver/silver_expression_recount3.parquet` plus a provenance report.
- The current recount3 extract contains 11,494,080 rows from 180 samples and occupies approximately 108 MB.
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
- Run `make run-recount3-expression` followed by `make run-external-validation` for the real external validation.
- Run `make run-expression-statistics` before rebuilding consensus candidates to add sample-level effect sizes and FDR support.
- Run `make run-metadata-strict`, `make run-download-tcga-paired`, and `make run-silver` to maximize matched cases before `make run-paired-expression`.
- Run `make fetch-reactome-gmt` to acquire pinned Reactome release 97 with checksums and provenance, then run `make run-pathway-enrichment`. The enrichment target performs the fetch automatically unless `SKIP_GMT_FETCH=1` is set.
- CI tests pathway analytics with synthetic GMT fixtures and does not require network acquisition. Offline runs may use
  `SKIP_GMT_FETCH=1`; the analytics layer then retains its empty, schema-valid missing-input contract.
- Generated raw data, credentials, and controlled-access files must not be committed.
