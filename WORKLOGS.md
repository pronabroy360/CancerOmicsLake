# WORKLOGS.md

Operational logbook for CancerOmicsLake.

Use this file to record milestone progress, pipeline runs, decisions, risks, and blockers.

## 1) Project Kickoff

- Kickoff date: `2026-05-27`
- Project mode: `open-access-only`
- MVP TCGA projects: `TCGA-BRCA`, `TCGA-LUAD`, `TCGA-COAD`
- MVP GTEx tissues:
  - `Breast - Mammary Tissue`
  - `Lung`
  - `Colon - Transverse`
  - `Colon - Sigmoid`
- Baseline stack:
  - Python + Polars
  - DuckDB
  - dbt Core
  - Prefect
  - Great Expectations (or equivalent)
  - FastAPI + Streamlit
  - Neo4j/Graphify export CSV

## 2) Milestone Tracker

| Milestone | Status | Owner | Start Date | Target Date | Acceptance Notes |
|---|---|---|---|---|---|
| M1 Project Setup | Done | pronabroy360 + Codex | 2026-05-27 | 2026-05-27 | Scaffold, configs, Makefile, Docker Compose, docs baseline, tests passing |
| M2 Metadata Ingestion | Done | pronabroy360 + Codex | 2026-05-27 | 2026-05-28 | Live GDC query path, manifest generation, audit output, strict live mode, capped download controls |
| M3 Expression Processing | Done | pronabroy360 + Codex | 2026-05-27 | 2026-05-29 | Silver TCGA/GTEx expression tables, file-based parsing, unit inference, tumor-vs-normal marts |
| M4 Mutation Processing | Done | pronabroy360 + Codex | 2026-05-27 | 2026-05-29 | MAF parsing, silver mutations, mutation-frequency marts, API integration |
| M5 dbt Warehouse | Done | pronabroy360 + Codex | 2026-05-28 | 2026-05-30 | dbt staging/silver/gold models, schema tests, CI dbt gate, local Docker fallback runner |
| M6 Data Quality Layer | Done | pronabroy360 + Codex | 2026-05-28 | 2026-05-30 | Silver quality checks, run history, live-mode sanity checks, report artifacts |
| M7 Knowledge Graph | Done | pronabroy360 + Codex | 2026-05-28 | 2026-05-30 | Gold graph marts, Graphify/Neo4j exports, bulk import scripts, traceability reporting |
| M8 Dashboard | Done | pronabroy360 + Codex | 2026-05-28 | 2026-05-31 | Streamlit explorer pages, dashboard data layer, API/demo verification |
| M9 Final Packaging | Done | pronabroy360 + Codex | 2026-05-28 | 2026-07-09 | Reviewer docs, manual/daily workflows, completion report, operational runbooks |

Status values:
- `Not Started`
- `In Progress`
- `Blocked`
- `Done`

## 3) Pipeline Run Log

| pipeline_run_id | Start Time | End Time | Status | Config Hash | Input Files | Output Tables | Errors | Warnings | Notes |
|---|---|---|---|---|---|---|---|---|---|
| 20260527T170126Z | 2026-05-27 23:01:26 +06 | 2026-05-27 23:01:26 +06 | passed_with_warnings | scaffold-stub | 12 metadata rows | 3 artifacts | 0 | 1 | Metadata-only dry run with stub data and quality JSON output |
| 20260527T171523Z | 2026-05-27 23:15:23 +06 | 2026-05-27 23:15:23 +06 | passed_with_warnings | m2-gdc-live-with-fallback | 12 metadata rows | 3 artifacts | 0 | 1 | Live GDC query attempted; fallback to stub in restricted network environment |
| 20260527T171623Z | 2026-05-27 23:16:23 +06 | 2026-05-27 23:16:23 +06 | passed_with_warnings | m2-gdc-live-with-fallback-v2 | 12 metadata rows | 3 artifacts | 0 | 1 | Added explicit fallback warning log and reran metadata pipeline |
| 20260527T173008Z | 2026-05-27 23:30:08 +06 | 2026-05-27 23:30:08 +06 | passed_with_warnings | m3-silver-bootstrap | 12 metadata rows | 7 artifacts | 0 | 1 | Metadata rerun before silver build; silver parquet tables generated successfully |
| 20260527T174339Z | 2026-05-27 23:43:39 +06 | 2026-05-27 23:43:39 +06 | passed_with_warnings | m3-silver-expression-bootstrap | 12 metadata rows | 9 artifacts | 0 | 1 | Added `silver_expression_tcga` and `silver_expression_gtex` outputs with stable schemas |
| 20260527T174843Z | 2026-05-27 23:48:43 +06 | 2026-05-27 23:48:43 +06 | passed_with_warnings | m4-gold-bootstrap | 12 metadata rows | 10 artifacts | 0 | 1 | Added `run-gold` and `gold_cohort_summary` build from silver tables |
| 20260527T174949Z | 2026-05-27 23:49:49 +06 | 2026-05-27 23:49:49 +06 | passed_with_warnings | m4-gold-bootstrap-v2 | 12 metadata rows | 10 artifacts | 0 | 1 | Sequential silver->gold run confirmed stable `gtex_expr_samples=4` |
| 20260527T190117Z | 2026-05-28 01:01:17 +06 | 2026-05-28 01:01:17 +06 | passed_with_warnings | m2-strict-live-and-audit | 12 metadata rows | 10 artifacts | 0 | 1 | Added strict live mode and persisted GDC ingestion audit report |
| 20260528T065035Z | 2026-05-28 12:50:35 +06 | 2026-05-28 12:50:35 +06 | failed | m2-strict-cli | 0 metadata rows | 0 artifacts | 1 | 0 | `run-metadata-strict` correctly failed fast and wrote strict-failure ingestion audit |
| 20260528T070225Z | 2026-05-28 13:02:25 +06 | 2026-05-28 13:02:25 +06 | success | m3-silver-quality-contracts | 12 metadata rows | 11 artifacts | 0 | 0 | Added silver table quality runner and generated `silver_data_quality_report.json` |
| 20260528T075406Z | 2026-05-28 13:54:06 +06 | 2026-05-28 13:54:06 +06 | success | m3-expression-loaders-file-based | 12 metadata rows | 11 artifacts | 0 | 0 | Added file-based TCGA/GTEx expression loaders and expanded quality checks to TCGA expression |
| 20260528T083656Z | 2026-05-28 14:36:56 +06 | 2026-05-28 14:36:56 +06 | success | m0-ci-automation | 0 metadata rows | 1 audit artifact | 0 | 0 | Added strict metadata smoke target and CI workflow pipeline with report artifact upload |

Template status values:
- `success`
- `passed_with_warnings`
- `failed`
- `failed_compliance`

## 4) Data Acquisition Log

| Date | Source | Scope | Manifest Count | Download Mode | Success Count | Failed Count | Retry File | Notes |
|---|---|---|---|---|---|---|---|---|
| 2026-05-27 | GDC/TCGA | BRCA, LUAD, COAD metadata stub | 12 | metadata_only | 12 | 0 | N/A | Manifest stub generated at `data/bronze/tcga/metadata/gdc_manifest_stub.tsv` |
| 2026-05-27 | GTEx | Tissue metadata stub | N/A | metadata_only | 4 | 0 | N/A | GTEx tissue stub rows generated in-memory for quality check pass |

Sources:
- `GDC/TCGA`
- `GTEx`
- `Reference`

Download mode:
- `metadata_only`
- `data_download`

## 5) Quality Check Summary Log

| Date | Run ID | Check Name | Status | Metric | Threshold | Failed Rows | Notes |
|---|---|---|---|---|---|---|---|
| 2026-05-27 | 20260527T170126Z | expression_values_non_negative | passed | N/A | N/A | 0 | Stub expression values all non-negative |
| 2026-05-27 | 20260527T170126Z | gene_mapping_rate | passed | 1.0 | 0.98 | 0 | Gene normalization mapping complete in stub sample |
| 2026-05-27 | 20260527T171523Z | expression_values_non_negative | passed | N/A | N/A | 0 | Metadata mode rerun after live GDC client integration |
| 2026-05-27 | 20260527T171523Z | gene_mapping_rate | passed | 1.0 | 0.98 | 0 | Fallback stub path preserved quality checks |
| 2026-05-27 | 20260527T171623Z | expression_values_non_negative | passed | N/A | N/A | 0 | Fallback warning log added to improve ingestion transparency |
| 2026-05-27 | 20260527T171623Z | gene_mapping_rate | passed | 1.0 | 0.98 | 0 | Pipeline behavior consistent after warning update |
| 2026-05-27 | 20260527T173008Z | expression_values_non_negative | passed | N/A | N/A | 0 | Metadata prerequisites for silver build passed |
| 2026-05-27 | 20260527T173008Z | gene_mapping_rate | passed | 1.0 | 0.98 | 0 | Silver bootstrap run kept quality baseline stable |
| 2026-05-27 | 20260527T174339Z | expression_values_non_negative | passed | N/A | N/A | 0 | Silver expression bootstrap run after schema expansion |
| 2026-05-27 | 20260527T174339Z | gene_mapping_rate | passed | 1.0 | 0.98 | 0 | GTEx expression stub mapping remained stable |
| 2026-05-27 | 20260527T174843Z | expression_values_non_negative | passed | N/A | N/A | 0 | Gold summary build executed after metadata/silver refresh |
| 2026-05-27 | 20260527T174843Z | gene_mapping_rate | passed | 1.0 | 0.98 | 0 | Quality baseline maintained while adding gold aggregation stage |
| 2026-05-28 | 20260527T190117Z | expression_values_non_negative | passed | N/A | N/A | 0 | Strict-mode/audit enhancement did not affect quality baseline |
| 2026-05-28 | 20260527T190117Z | gene_mapping_rate | passed | 1.0 | 0.98 | 0 | Mapping rate stable after ingestion control additions |

## 6) Decision Log (ADR-lite)

| Date | Decision ID | Context | Decision | Alternatives Considered | Impact | Owner |
|---|---|---|---|---|---|---|
| 2026-05-27 | DEC-001 | Dataframe stack for MVP | Start with Polars-compatible pipeline stubs and typed config models | Pandas-first | Keeps performance-oriented path while staying simple for MVP |
| 2026-05-27 | DEC-002 | Environment setup on macOS | Use local `.venv` for project commands | System Python install | Avoids PEP-668 conflicts and keeps dependencies isolated |
| 2026-05-27 | DEC-003 | Code navigation at scale | Enable `codeindex` and build symbol index early | Manual grep-only navigation | Faster iterative development and safer refactors |
| 2026-05-27 | DEC-004 | GDC ingestion resilience | Implement live API query with retry/backoff and configurable stub fallback | Hard fail on first network issue | Keeps local/dev workflow moving while preserving path to real metadata |
| 2026-05-27 | DEC-005 | Silver bootstrap strategy | Build first silver tables from bronze metadata CSV using Polars | Waiting for full modality pipelines first | Enables immediate warehouse progression and dashboard/API integration path |
| 2026-05-27 | DEC-006 | Expression schema stability | Emit stable silver expression tables before full file parsers are ready | Delay expression outputs until full parser stage | Unblocks downstream models/tests with explicit `data_origin` labeling |
| 2026-05-27 | DEC-007 | Gold bootstrap strategy | Build `gold_cohort_summary` directly from silver tables as first analysis mart | Waiting for full gold model suite | Enables immediate analytics surface and dashboard/API metric source |
| 2026-05-27 | DEC-008 | Stage execution order | Run `run-silver` then `run-gold` sequentially (not parallel) | Parallel stage execution | Avoids transient parquet read/write race conditions on local runtime |
| 2026-05-28 | DEC-009 | Live-ingestion control | Add `require_live_gdc` to block fallback when strict live metadata is required | Implicit fallback in all environments | Supports CI/prod fail-fast behavior and explicit compliance posture |
| 2026-05-28 | DEC-010 | Ingestion observability | Persist GDC ingestion audit JSON with retries, fallback reason, and project status | Log-only visibility | Improves debugging, traceability, and run explainability |
| 2026-05-28 | DEC-011 | Strict runtime ergonomics | Add CLI flag and Make target for strict live metadata mode | Editing config for each run | Makes CI/dev fail-fast invocation explicit and repeatable |
| 2026-05-28 | DEC-012 | Strict-failure traceability | Persist ingestion audit JSON even when strict live mode fails | Failure without persisted audit | Preserves diagnostics for CI and operations triage |
| 2026-05-28 | DEC-013 | Silver contract checks | Add explicit quality checks for null IDs, duplicates, access level, and expression constraints on silver outputs | Implicit trust in transforms | Improves data reliability and catches regressions before gold modeling |
| 2026-05-28 | DEC-014 | Expression ingestion strategy | Support file-based expression ingestion first, with safe stub fallback | Stub-only expression staging | Enables transition to real cohort processing without breaking current pipeline |
| 2026-05-28 | DEC-015 | CI strict smoke determinism | Add strict smoke command with explicit `--gdc-base-url` override to force controlled failure path | Strict smoke dependent on ambient network state | Ensures CI verifies fail-fast + audit behavior deterministically |
| 2026-05-28 | DEC-016 | CI responsibility expansion | Add GitHub Actions workflow for tests + pipeline smoke + report artifacts | Manual local validation only | Moves project toward reproducible reviewer-friendly engineering practice |

Example Decision IDs:
- `DEC-001`: Default dataframe engine = Polars
- `DEC-002`: Quality framework choice
- `DEC-003`: Graph density threshold policy

## 7) Risk Register

| Date | Risk ID | Risk | Likelihood | Impact | Mitigation | Owner | Status |
|---|---|---|---|---|---|---|---|

Likelihood values:
- `Low`
- `Medium`
- `High`

Impact values:
- `Low`
- `Medium`
- `High`

## 8) Blocker Log

| Date | Blocker ID | Description | Affected Milestone | Next Action | Owner | Status |
|---|---|---|---|---|---|---|

## 9) Weekly Summary

### Week of 2026-05-27

- Planned:
  - Initialize repository scaffold
  - Add configs and baseline make targets
  - Implement metadata-only ingestion for 3 TCGA projects
- Completed:
  - Added `AGENTS.md`, `GUARDRAILS.md`, `WORKLOGS.md`, `PRD.md`
  - Implemented Milestone 1 scaffold with configs, package structure, Makefile, docs, API/dashboard stubs
  - Added baseline tests and passed: `6 passed`
  - Executed metadata-only dry run and generated quality JSON report
  - Initialized `codeindex` and `symbolindex` for repository mapping
  - Implemented Milestone 2 live GDC metadata query path with retry/backoff and project/category/access filters
  - Added ingestion unit coverage for query payload and nested response mapping (`8 passed`)
  - Implemented first Milestone 3 silver-table builder and CLI (`run-silver`)
  - Generated `silver_projects`, `silver_patients`, `silver_samples`, `silver_file_manifest` parquet tables
  - Added `silver_expression_tcga` (schema-only, zero rows) and `silver_expression_gtex` (stub rows) parquet outputs
  - Implemented first gold mart builder and CLI (`run-gold`) producing `gold_cohort_summary.parquet`
  - Updated API cohort summary source to read from gold table with fallback to stub
  - Added strict live metadata mode (`require_live_gdc`) and GDC ingestion audit output
  - Extended ingestion tests to cover strict-mode failure and audit content shape
  - Added `run-metadata --require-live-gdc` and `make run-metadata-strict` for operational fail-fast runs
  - Added `run-quality` and silver contract checks with JSON report output
  - Implemented file-based TCGA and GTEx expression loaders with schema-safe fallback
  - Added manifest-aware TCGA expression discovery (expression files are now selected via metadata `data_category` + `data_type` + `file_name`, with safe fallback scan behavior)
  - Added regression test coverage for manifest-vs-non-expression file filtering in TCGA expression ingestion (`17 passed`)
  - Expanded quality checks to include TCGA expression null/non-negative checks
  - Implemented manifest-aware TCGA mutation loader (MAF/TSV) and integrated `silver_mutations.parquet` into the silver build
  - Added mutation quality contracts (`null_gene_symbol`, `start_position` integer validity, `end_position` integer validity), increasing silver checks to 10
  - Extended gold build to generate `gold_mutation_frequency_by_gene.parquet` and `gold_mutation_frequency_by_cancer.parquet`
  - Updated mutation API endpoints to read from gold marts with safe stub fallback when gold files are missing
  - Added mutation-focused test coverage for loader, gold marts, API service helpers, and silver contract checks (`20 passed`)
  - Replaced stub-only graph responses with real graph table builders from silver/gold (`gold_graph_nodes.parquet`, `gold_graph_edges.parquet`) executed during `run-gold`
  - Added graph table tests and fallback behavior checks for API graph endpoints (`22 passed`)
  - Added `run-graph-export` stage to produce Neo4j and Graphify CSV bundles from gold graph tables
  - Added graph export unit coverage and generated first local exports under `outputs/graph_exports/` (`23 passed`)
  - Added silver quality checks for sample-to-patient FK integrity and manifest MD5 presence, increasing silver checks from 10 to 12
  - Implemented gold `gold_tumor_vs_normal_expression.parquet` generation from silver TCGA tumor + mapped GTEx normal tissues (BRCA/LUAD/COAD mapping)
  - Updated `/expression/tumor-vs-normal/{gene_symbol}` API path to read gold tumor-vs-normal table with stub fallback
  - Added tumor-vs-normal integration and service tests (`26 passed`)
  - Replaced `/expression/gene/{gene_symbol}` stub path with silver-backed TCGA + GTEx summary query logic
  - Added expression summary tests for silver-backed reads and fallback behavior (`28 passed`)
  - Replaced metadata API stubs (`/metadata/projects`, `/metadata/samples`) with silver-backed query logic
  - Added metadata analytics tests for project/sample rollups and missing-file fallback (`31 passed`)
  - Implemented dbt scaffolding with bronze staging views, silver cleaned models, gold marts, and dbt schema tests for mutation/tumor-vs-normal/graph outputs
  - Added `make run-dbt` and `make test-dbt` targets plus `dbt/profiles.yml` for local DuckDB execution
  - Added dbt dependencies (`dbt-core`, `dbt-duckdb`) to `requirements.txt` (note: local Python 3.14 environment cannot execute dbt runtime; CI Python 3.11 remains the target runtime)
  - Implemented Prefect orchestration flow (`run-flow`) that executes metadata → silver → gold → quality → graph-export stages and writes `outputs/reports/pipeline_run_metadata.json`
  - Added resilient fallback execution when Prefect cannot start local ephemeral API (restricted-port environments)
  - Added orchestration unit tests and validated local flow command (`35 passed`)
  - Added FastAPI endpoint smoke tests for health, metadata, expression, tumor-vs-normal, and mutation routes (`40 passed`)
  - Replaced `/genes/search` stub with silver-backed gene search across expression/mutation tables
  - Replaced `/quality/latest` stub with report-backed quality payload reader plus cohort summary merge
  - Added analytics tests for gene search and quality-latest readers, and expanded API smoke coverage (`46 passed`)
  - Implemented manifest/metadata-driven TCGA file download stage with retry, checksum verification, project/category foldering, and report outputs
  - Added `run-download-tcga` CLI/Make target and integrated download stage into orchestration flow execution
  - Added downloader unit tests for metadata-only skip, successful expression/mutation placement, and checksum mismatch handling (`49 passed`)
  - Reduced CLI side effects by lazy-loading Prefect flow imports so non-flow commands run without Prefect initialization warnings
  - Added silver-quality reconciliation checks for downloaded TCGA file presence and manifest MD5 match (gated by download-report applicability)
  - Added targeted quality test coverage for missing-file and checksum-mismatch detection paths (`50 passed`)
  - Added workflow/column-aware TCGA expression unit inference (`TPM`/`FPKM`/`COUNT`) in expression loader path
  - Added silver quality unit-support contracts for TCGA and GTEx expression tables, increasing silver checks to 16
  - Added regression tests for count-unit inference and invalid-unit detection (`51 passed`)
  - Added safe live-smoke TCGA downloader controls: `--max-downloads` and `--data-subdirs` (`run-download-tcga-force-smoke`)
  - Executed strict live metadata fetch and capped live file smoke download (`3/3` successful) with open-access BRCA expression files
  - Extended TCGA expression parser to support real GDC single-sample STAR/miRNA formats by deriving sample metadata from manifest `file_name`
  - Fixed silver-build path isolation so tests don’t accidentally read global bronze expression folders
  - Added partial-download-aware integrity semantics: file presence/checksum checks become `warning` (not hard failure) under capped smoke mode
  - Added test coverage for downloader limits/subdir filters, real-format parser behavior, and partial-mode quality warnings (`54 passed`)
  - Added `run-metadata-strict-smoke` operational target and `.github/workflows/ci.yml` automation
  - Added gzip/comment-safe mutation parsing for real GDC `*.maf.gz` files and wired mutation loader root to the active bronze metadata root
  - Executed capped live mutation download smoke (`max_downloads=1`, mutations-only) and validated real BRCA mutation ingestion into silver (`mutations_count=48`)
  - Updated silver duplicate-sample quality rule to ignore placeholder IDs (`Unknown`/blank) while retaining strict checks for real IDs
  - Expanded tests for gzipped mutation parsing and placeholder duplicate handling; full suite now passing (`56 passed`)
  - Upgraded Neo4j export layer to generate bulk-import-friendly CSV bundles by node label and edge type under `outputs/graph_exports/neo4j/bulk/`
  - Added generated Neo4j import script output (`outputs/graph_exports/neo4j/import_bulk.cypher`) with no-APOC Cypher `LOAD CSV` workflow
  - Extended graph export logging and test coverage to validate bulk artifact generation
  - Expanded `docs/graph_schema.md` with concrete schema details, import instructions, and executable Cypher query examples
  - Added a dashboard analytics data layer (`src/analytics/dashboard_data.py`) for overview metrics, cohort distributions, expression views, mutation landscape, graph explorer, and quality report parsing
  - Replaced all Streamlit page placeholders with live parquet-backed interactive pages, including filters, tables, chart views, and CSV export buttons
  - Implemented graph explorer controls for edge-type filtering, node search, visible-node/edge metrics, and Neo4j bulk export file visibility
  - Added targeted unit tests for dashboard analytics coverage (`tests/test_dashboard_data.py`)
  - Revalidated test suite after dashboard integration (`60 passed`)
  - Added project-level modality download caps to config and downloader (`expression`/`mutations`) with deterministic selection and cap metadata in reports
  - Added CLI cap controls and medium-cap run targets (`run-download-tcga-medium`, `run-flow-medium`) while preserving open-access and checksum/retry behavior
  - Expanded silver quality checks with schema presence contracts, sample/project linkage checks, gold graph/node schema checks, graph edge-node FK checks, and live-mode non-zero row sanity checks
  - Added report context utilities for run-mode tagging and persistent run history (`pipeline_run_history.json`)
  - Updated orchestration metadata to include run-mode and cap settings in pipeline run metadata
  - Added daily scheduled CI trigger and dbt run/test gates in GitHub Actions
  - Added new test coverage for cap logic, reporting utilities, and live-mode quality sanity (`65 passed`)
  - Added workflow-aware TCGA expression parsing presets for STAR/HTSeq/FPKM-style files and improved expression unit inference for `tpm_*`/`fpkm_*` columns
  - Added filtering of STAR/HTSeq summary rows (for example `__no_feature`, `N_unmapped`) before silver expression write
  - Added TCGA workflow-vs-unit compatibility quality check to flag suspicious workflow/unit combinations
  - Expanded loader and quality tests for summary-row filtering and workflow-unit compatibility (`67 passed`)
- Next:
  - Replace stub-first TCGA expression path with real cohort expression files from manifest-driven ingestion
  - Add dashboard screenshots and README embeds from live pages for professor-facing presentation
  - Add a reviewer-facing demo script that runs API, dashboard, and graph export checks in one command

## 2026-05-28 - Reviewer Documentation And Query Packaging

- Expanded README with architecture, graph/dashboard/API entrypoints, medium-cap runtime notes, and example analytical questions.
- Added `docs/sample_queries.md` and publish-safe SQL files under `outputs/sample_queries/`.
- Expanded reproducibility documentation for medium capped runs, scheduled CI, dbt runtime expectations, and run artifact history.
- Expanded data dictionary coverage for implemented silver/gold, mutation, expression, and graph marts.
- Added documentation packaging tests so CI protects reviewer-facing project quality.

## 2026-07-09 - Completion And Release Readiness Pass

- Added local `dbt` execution orchestration through `src.operations.dbt_runner`, with automatic Docker Compose fallback when the active Python runtime is incompatible with dbt.
- Added `docker-compose` `dbt` service so local warehouse validation can use Python `3.11` without rebuilding the main project environment.
- Added `run-project-completion` CLI/Make target and `src.operations.project_completion` report generator.
- Added `outputs/reports/project_completion_report.json` as a milestone-level release-readiness artifact for CI and manual ingestion workflows.
- Updated CI and manual ingestion workflows to generate the completion report alongside existing reports and graph exports.
- Synced README, reproducibility docs, and API spec with the current implementation and local dbt execution behavior.
- Reconciled milestone tracker statuses so the worklog reflects the implemented state of the project rather than early scaffold placeholders.

## 2026-05-28 - Reviewer Demo Verification Gate

- Added `run-demo-check` CLI command and `make run-demo-check`/`make run-demo-check-strict` targets.
- Added `make run-demo` as a one-command capped pipeline plus demo-contract verification path.
- Implemented demo verification for silver/gold parquet readiness, quality report status, Graphify/Neo4j exports, API health, and dashboard data contracts.
- Added strict no-stub mode to reject stub/demo-origin rows and require live GDC audit provenance.
- Updated README/reproducibility/query docs so reviewers have a clear demo path.

## 2026-05-28 - CI Demo Gate Enforcement

- Updated CI workflow to run `make run-graph-export` and `make run-demo-check` after quality checks.
- Added graph export artifact upload bundle (`neo4j` + `graphify` outputs and Neo4j bulk import script/files).
- Added CI workflow contract test to prevent accidental removal of the demo gate and schedule/dbt checks.
- Synced README and reproducibility docs with the enforced CI demo-gate behavior.

## 2026-05-28 - Ingestion Traceability Reporting

- Added `run-ingestion-traceability` CLI command and `make run-ingestion-traceability` target.
- Implemented `outputs/reports/ingestion_traceability_report.json` to map candidate/selected/downloaded/skipped/failed file counts to silver parsed row/file coverage by project and modality.
- Added warning semantics for local-download-vs-silver parsing gaps and stub/demo-origin rows.
- Integrated traceability command into `make run-demo` and CI pipeline execution.
- Added unit coverage for traceability report generation and doc/CI contract assertions.

## 2026-05-28 - Aggressive Ingestion Profile

- Added explicit aggressive cap profile (`expression=100`, `mutations=40` per project) in `src/common/cap_profiles.py`.
- Added CLI support for `--use-aggressive-cap-profile` on both `run-download-tcga` and `run-flow`.
- Added dedicated manual fast-track targets:
  - `make run-download-tcga-aggressive`
  - `make run-flow-aggressive`
  - `make run-demo-aggressive`
- Added `--force-download` support to orchestration flow and wired medium/aggressive flow/demo targets to avoid silent metadata-only skip behavior.
- Added `--data-subdirs` support to orchestration flow and scoped medium/aggressive flow/demo targets to `expression,mutations` for stronger run stability.
- Updated README and reproducibility docs for the aggressive completion path.

## 2026-05-28 - Manual Workflow Dispatch Automation

- Added `.github/workflows/manual_ingestion.yml` for one-click manual ingestion runs in GitHub Actions.
- Added profile input (`medium`/`aggressive`) with optional strict no-stub and strict metadata toggles.
- Configured manual workflow to run tests, metadata, selected demo profile, optional strict verifier, and artifact uploads.
- Added workflow contract test coverage and docs updates for the manual dispatch path.

## 2026-07-09 - Codex Tooling Install

- Installed `codeindex` from `scheidydude/codeindex` into the project virtual environment.
- Installed `rtk` and `caveman` from PyPI after verifying they are publicly available packages.
- Refreshed local `codeindex.json` and `symbolindex.json` indexes for the repository.
- Added `.codeindex/` to `.gitignore` so the local index database stays untracked.

## 2026-07-09 - Candidate Gene Priority And Dockerized dbt Stability

- Added `gold_candidate_gene_priority` as a research-facing mart that combines mutation frequency, tumor-vs-normal signal, evidence coverage, and priority tiers for candidate cancer-gene ranking.
- Added matching dbt gold model, data dictionary entry, reviewer SQL query, and documentation packaging coverage.
- Switched Docker Compose services to a reusable project image so API, dashboard, and dbt runs no longer reinstall dependencies on every container invocation.
- Fixed Docker dbt profile path resolution and added regression tests for dbt runner/profile behavior.
- Tightened GDC sample ID extraction to use sample submitter IDs when GDC omits `sample_id`.
- Aligned dbt sample uniqueness tests with quality semantics by excluding placeholder `Unknown` sample IDs from uniqueness assertions.
- Verified gates: `make test` (`93 passed`), `make test-dbt` (`43 passed`), `make run-demo-check`, and `make run-project-completion`.

## 2026-07-10 - Candidate Priority API And Dashboard Surface

- Added `src.analytics.candidate_priority` query helpers for the `gold_candidate_gene_priority` research mart.
- Added `GET /research/candidate-genes` with filters for cancer type, gene query, priority tier, minimum score, and limit.
- Added Streamlit `Candidate Gene Priority` page for filtering, charting, table review, and CSV export of ranked cancer-gene pairs.
- Updated API docs and README with the research endpoint and dashboard page.
- Added tests for candidate-priority analytics, API contract, dashboard data helper, and docs packaging.
- Verified `make test` passes with `98 passed`.

## 2026-07-10 - Graph Metrics And Hub Node Analytics

- Replaced the placeholder graph metrics module with node-degree analytics over `gold_graph_nodes` and `gold_graph_edges`.
- Added `gold_graph_node_metrics.parquet` with total degree, in-degree, out-degree, weighted degree, edge-type count, and degree rank.
- Added `outputs/reports/graph_metrics_report.json` with graph size, top hub nodes, and edge-type summaries.
- Wired graph metrics into `run-graph-export`, added `run-graph-metrics`, and integrated metrics generation into the orchestration flow.
- Extended reviewer demo checks to require graph node metrics and graph metrics report outputs.
- Added top graph hub nodes to the Knowledge Graph dashboard page.
- Added reviewer SQL query `06_graph_node_metrics.sql` and updated graph/data-dictionary docs.
- Verified `make run-graph-export`, `make run-demo-check`, and `make test` (`102 passed`).

## 2026-07-10 - Provenance-Aware Evidence Confidence Layer

- Added `gold_cancer_gene_evidence_confidence` to distinguish candidate importance from evidence reliability.
- Calibrated mutation and expression support from contributing sample counts, with an explicit penalty and high-risk label for uncorrected TCGA-GTEx batch effects.
- Added graph-structure, row-integrity, and source-provenance components plus machine-readable caveats.
- Added matching dbt model, independent CLI/Make target, API endpoint, Streamlit page, reviewer SQL, and demo-gate coverage.
- Kept the model deliberately conservative: sparse GTEx normal coverage cannot produce high expression confidence.

## 2026-07-10 - Live GTEx V8 Expansion And Harmonization

- Added a config-driven open-access GTEx downloader with resumable streaming, remote size/MD5 verification, retry behavior, and audit reporting.
- Downloaded official V8 TPM GCT files for breast, lung, transverse colon, and sigmoid colon plus the open sample-annotation file (approximately 178 MB).
- Added streaming GCT-to-Parquet harmonization with deterministic 50-sample-per-tissue selection, tissue validation, Ensembl normalization, donor derivation, and atomic output replacement.
- Built 11,240,000 real GTEx rows from 200 samples and 56,200 source genes per tissue in a 92 MB silver Parquet.
- Tightened TCGA expression selection and fixed source-file metadata binding so retained expression rows are STAR TPM gene expression.
- Expanded graph gene nodes to include the GTEx expression universe, resolving 208,296 edge/node integrity failures.
- Rebuilt 108,012 tumor-vs-normal rows and restored quality status to `passed_with_warnings`.

## 2026-07-10 - Aggressive TCGA STAR Expansion And Parallel Downloader

- Added modality-aware live GDC metadata slices so each TCGA project now queries broad metadata plus targeted `STAR - Counts` gene expression and masked somatic mutation files.
- Increased live metadata coverage to 1,696 rows with 200 STAR expression candidates and 200 masked mutation candidates per BRCA/LUAD/COAD project.
- Added bounded parallel TCGA downloads (`--download-workers`) and wired Make/flow/demo aggressive targets to use 8 workers while preserving open-access, checksum, retry, and deterministic cap behavior.
- Extended TCGA download reports with the exact `selected_files` list and updated quality checks to validate selected capped files instead of flagging unselected candidates as missing.
- Completed aggressive download profile: 420 selected files, 394 downloaded, 26 checksum-skipped, 0 failed, approximately 1.19 GB newly downloaded.
- Rebuilt silver/gold outputs: 18,319,320 TCGA expression rows, 11,240,000 GTEx expression rows, 45,588 mutation records, 108,012 tumor-vs-normal rows, 57,599 graph nodes, and 243,834 graph edges.
- Improved tumor-vs-normal support to 95 BRCA, 94 LUAD, and 96 COAD TCGA tumor samples with 50/50/100 matched GTEx normal samples.
- Evidence confidence now contains 108,781 cancer-gene rows with 51 high-confidence rows after stronger TCGA coverage.
- Verified gates: silver quality `passed` across 30 checks, ingestion traceability `passed`, strict demo check `passed` (27 checks), dbt run (22 models), dbt test (50 tests), project completion 9/9, and pytest (`116 passed`).

## 2026-07-10 - Batch-Effect Sensitivity Layer

- Added `gold_batch_effect_sensitivity` to reduce dependence on raw TCGA-GTEx TPM fold changes during exploratory review.
- Implemented within-cancer/reference percentile ranks, robust z-score deltas, support tiers, and direction labels (`rank_up`, `rank_down`, `stable`).
- Added matching dbt model and schema tests, increasing dbt coverage to 23 models and 59 data tests.
- Added API endpoint `GET /research/batch-effect-sensitivity`, Streamlit `Batch-Effect Sensitivity` page, dashboard data helper, and reviewer SQL query `08_batch_effect_sensitivity.sql`.
- Added methodology documentation clarifying that this is sensitivity analysis, not full batch correction.
- Expanded quality guardrails with batch-sensitivity schema and accepted-value checks, increasing silver/gold quality checks to 32.

## 2026-07-10 - Batch-Sensitivity Concordance Calibration

- Integrated the batch-sensitivity mart into cancer-gene evidence confidence instead of treating every expression comparison identically.
- Added raw expression direction, sensitivity direction/support, concordance status, and a bounded sensitivity-confidence component.
- Kept the calibration conservative: concordance can retain the existing `0.5` expression ceiling, while directional discordance halves expression confidence.
- Added API/dashboard concordance filtering, dbt accepted-value contracts, quality checks, reviewer SQL, and regression coverage.
- Retained explicit high/elevated batch-risk labels because concordance analysis is not equivalent to harmonized processing or full batch correction.
- Standardized tied expression values to average-rank percentiles in Python and dbt; a dbt parity test prevents minimum-rank drift.
- Real-data result: 81,908 concordant, 26,104 inconclusive, and 769 not-applicable pairs; high-confidence candidates reduced from 51 to 42.
- Verified `make test` (`122 passed`), dbt run (`23 models`), dbt test (`64 tests`), quality (`34 checks`), and strict demo (`27 checks`).

## 2026-07-10 - Adjacent-Normal Reference Triangulation

- Added a dedicated GDC STAR expression query slice for `Solid Tissue Normal` and an independent deterministic `expression_normal` download cap.
- Added `make run-download-tcga-normals`, preserving open-access enforcement, retries, checksums, and existing-file skips.
- Ingested high-support adjacent-normal bridge cohorts: 60 BRCA, 59 LUAD, and 41 COAD samples; TCGA expression expanded to 27,054,360 silver rows.
- Added `gold_reference_triangulation` across TCGA tumor, TCGA adjacent normal, and GTEx healthy normal references.
- Added direction concordance, normal-reference shift, sample-support tiers, and a conservative reference-stability calibration.
- Real-data classifications across 108,012 rows: 85,965 concordant stable, 2,569 concordant down, 2,238 concordant up, 16,589 reference sensitive, and 651 directionally discordant.
- Added matching dbt model/contracts, quality checks, API endpoint, Streamlit page, methodology, data dictionary, and reviewer SQL.
- Optimized dbt to reuse `gold_tumor_vs_normal_expression`, avoiding concurrent duplicate scans that initially exceeded Docker memory.
- Python and dbt concordance counts match exactly. Verified pytest (`129 tests`), dbt run (`24 models`), dbt test (`71 tests`), quality (`37 checks`), and strict demo (`27 checks`).

## 2026-07-10 - Candidate Bootstrap Rank Stability

- Added deterministic nonparametric bootstrap resampling across TCGA tumor, TCGA adjacent normal, and GTEx normal cohorts.
- Default profile evaluates the union of top-500 priority candidates per cancer and every high-confidence candidate over 200 iterations.
- Added direction-retention, cross-reference concordance/opposition, top-k selection, rank intervals, effect intervals, rank precision, and stability tiers.
- Added `make run-bootstrap-stability`, JSON run report, API endpoint, Streamlit page, quality contracts, methodology, and reviewer SQL.
- Real output contains 1,536 candidates: 677 high, 841 moderate, and 18 limited stability.
- All 42 high-confidence candidates were evaluated: 26 high, 15 moderate, and one limited bootstrap-stability result.
- Verified pytest (`135 tests`), quality (`39 checks`), and strict demo (`27 checks`).

## 2026-07-10 - Real recount3 External Expression Validation

- Added a Python-native recount3 extractor over the public S3 release, avoiding a host R/Bioconductor dependency.
- Added resumable source caching, remote-size verification, SHA-256 provenance, deterministic sample selection, and
  GENCODE v26 gene-symbol mapping for TCGA BRCA/LUAD/COAD and GTEx breast/lung/colon projects.
- Reproduced recount3's documented AUC transformation at a 40-million-read target.
- Built 11,494,080 normalized expression rows from 180 samples across six source cohorts in a 108 MB Parquet.
- Completed external validation for 108,012 gene-cancer pairs: 84,531 high, 12,056 moderate, 9,610 limited, and
  1,815 discordant validation-tier rows.
- Added CLI/Make execution, unit coverage, reproducibility instructions, input data dictionary, and explicit
  non-clinical confounding caveats.

## 2026-07-10 - Consensus Candidate Publication Triage

- Added `gold_consensus_candidate_genes` as the final research-triage mart over candidate priority, evidence confidence,
  adjacent-normal triangulation, bootstrap stability, recount3 external validation, and mutation support.
- Implemented conservative score components and explicit rejection reasons for external discordance, reference sensitivity,
  weak bootstrap support, weak evidence confidence, and low consensus score.
- Added `make run-consensus-candidates`, CLI execution, API endpoint, dashboard data helper, JSON report output,
  data dictionary entries, reviewer SQL, and regression coverage.
- Kept the interpretation scope narrow: this layer ranks candidates for further research review and does not claim
  batch-corrected differential expression, clinical biomarker status, or causal biology.

## 2026-07-10 - Replicated Expression Statistical Support

- Added sample-level two-sided Mann-Whitney tests for native TCGA/GTEx and uniformly processed recount3 contrasts.
- Added signed rank-biserial effect sizes and Benjamini-Hochberg FDR correction within each cancer and source.
- Added conservative replication tiers; significant, material opposite-direction source effects are labeled `discordant` and receive zero statistical score.
- Real output contains 108,012 tested pairs: 35,600 replicated-FDR, 8,355 recount3-supported, 13,441 native-only, 48,008 limited, and 2,608 materially discordant.
- Integrated statistical support as a seventh consensus-ranking component with an explicit discordance rejection reason.
- Added CLI/Make execution, API and dashboard access, data contracts, reviewer SQL, and regression tests.
- Preserved the caveat that source and disease status remain confounded; these are association tests, not causal, clinical, or batch-corrected differential-expression claims.

## 2026-07-10 - Matched TCGA Tumor-Normal Validation

- Audited initial matched-case coverage and found acquisition-limited overlap despite strong adjacent-normal coverage.
- Added a dedicated GDC primary-tumor metadata slice and deterministic paired acquisition restricted to cases with downloaded adjacent normals.
- Added case-level tumor/normal aggregation, Wilcoxon signed-rank tests, paired rank-biserial effects, and cancer-wise Benjamini-Hochberg FDR.
- Added recount3 direction replication, paired support tiers, hard consensus rejection for material paired discordance, and an eighth consensus evidence component.
- Added CLI/Make execution, API, Streamlit page, quality contracts, documentation, reviewer SQL, and regression tests.
- Real paired acquisition selected 178 primary-tumor files for cases with adjacent-normal coverage; 150 downloaded, 28 already existed, and zero failed.
- Rebuilt silver/gold on the paired real-data profile: 37,002,600 TCGA expression rows, 11,240,000 GTEx expression rows, 45,588 mutation rows, and 108,012 tumor-vs-normal rows.
- Real paired output contains 178,281 tested cancer-gene rows with matched cases: BRCA 60, COAD 41, and LUAD 58.
- Paired support tiers: 25,544 paired-replicated, 33,912 paired-internal-FDR, 114,938 limited, and 3,887 paired-discordant rows.
- Consensus triage after paired evidence: 301 prioritized, 5,890 watchlist, and 102,590 deprioritized rows.
- Verified pytest (`159 passed`), quality (`48 checks`), and strict demo (`27 checks`). Local dbt remains CI/Docker-gated because this shell is Python 3.14 and the Docker daemon is not running.

## 2026-07-13 - Consensus Candidate Pathway Enrichment

- Added `gold_pathway_enrichment` as a pathway-level hypothesis-generation mart over consensus candidate sets.
- Implemented GMT parsing, Reactome-style pathway ID extraction, hypergeometric over-representation tests, and Benjamini-Hochberg FDR within cancer and candidate set.
- Added candidate sets for `prioritized`, `watchlist_plus_prioritized`, and `research_candidate_plus` genes using the cancer-specific tested background.
- Added CLI/Make execution, API endpoint, Streamlit page, quality contracts, data dictionary, reviewer SQL, and regression tests.
- Kept pathway interpretation narrow: enrichment summarizes candidate-set biology for follow-up, not mechanism, causality, or clinical actionability.

## 2026-07-14 - Reactome GMT Acquisition Layer

- Added `scripts/fetch_reactome_gmt.sh` — an idempotent downloader that fetches pinned
  Reactome release 97 `ReactomePathways.gmt` (CC0 1.0, 2,868 pathways at acquisition) into
  `data/bronze/reference/pathways/reactome_pathways.gmt` (the path already expected by
  `src/analytics/pathway_enrichment.py`).
- Idempotency: reuses a cache only when its release and SHA-256 match the provenance sidecar; supports
  `REFRESH_GMT=1` to force a re-download and `SKIP_GMT_FETCH=1` for CI / offline sandboxes.
- Validates every GMT row, rejects duplicate pathway IDs and truncated files, extracts into a
  same-filesystem temporary directory, and atomically replaces the cache only after validation.
- Writes release, URL, timestamps, license, pathway count, file size, and compressed/uncompressed
  SHA-256 values to the bronze provenance sidecar and acquisition report.
- Added `make fetch-reactome-gmt` and wired it as a dependency of `make run-pathway-enrichment`
  via a `GMT_DEP` conditional, so the first enrichment run auto-fetches the GMT and subsequent
  runs reuse the cached file. CI can bypass with `SKIP_GMT_FETCH=1`.
- Verified the existing parser (`load_gmt_pathways`) already handles the official Reactome
  layout (col1 = name, col2 = R-HSA-XXXXX, col3+ = HGNC symbols); also tolerates MSigDB-style
  and mixed layouts.
- Added `tests/test_pathway_enrichment_gmt.py` with regression tests covering:
  parser correctness on the official Reactome layout, MIN/MAX pathway-size filtering,
  per-cancer BH-FDR independence, hypergeometric p-value sanity check against `scipy.stats.hypergeom`,
  fetch-script idempotency, `SKIP_GMT_FETCH=1`, truncated-cache rejection, and atomic refresh fallback.
- Added `docs/pathway_enrichment.md` methodology (GMT layout, candidate sets, statistical test,
  FDR scope, tiering, guardrails, reproducibility, atomic refresh fallback, and truncated-cache rejection).
- Added `outputs/sample_queries/12_pathway_enrichment.sql` reviewer SQL.
- Updated README to reference `make fetch-reactome-gmt` and the `SKIP_GMT_FETCH` / `REFRESH_GMT` env knobs.
- Live release-97 acceptance produced 2,868 pathways and 6,806 enrichment rows across three cancers;
  2,440 rows met the engineering FDR-enriched tier and remain hypothesis-generation results.
- Verified pytest (`173 passed`), quality (`50 checks`), and strict demo readiness (`27 checks`).

## 2026-07-14 - Reactome Pathway Knowledge Graph Projection

- Added deterministic projection of FDR-enriched Reactome pathways into the biomedical graph.
- Added `Pathway` nodes, complete Reactome `MEMBER_OF_PATHWAY` gene edges for retained pathways,
  and `ENRICHED_IN_CANCER` edges weighted by the bounded enrichment score.
- Restricted projection to FDR <= 0.05, collapsed duplicate candidate-set hits by strongest evidence,
  and capped pathways at 50 per cancer to control graph density.
- Preserved the existing node/edge table contracts, Neo4j/Graphify exporters, API, and dashboard filters.
- Added regression coverage for selection caps, deterministic de-duplication, pathway memberships,
  graph node/edge construction, and endpoint integrity through existing quality checks.
- Real projection produced 104 pathway nodes, 17,725 gene-membership edges, and the configured
  150 pathway-cancer edges (50 per cancer) with zero orphan edges.
- Verified pytest (`175 passed`), quality (`50 checks`), and strict demo readiness (`27 checks`).
- Kept interpretation narrow: graph relationships support hypothesis navigation and do not establish
  pathway activation, mechanism, causality, or clinical actionability.

## 2026-07-16 - Publication Mutation Semantics Hardening

- Preserved all source MAF rows while adding conservative consequence groups and an explicit protein-altering flag.
- Added a downloaded mutation-profile silver table so mutation frequencies no longer divide by unrelated
  expression or clinical samples.
- Restricted mutation-based candidate evidence and graph edges to protein-altering events while retaining all-event
  and synonymous audit counts.
- Added matching Python, dbt, quality, test, and documentation contracts.
- Real release audit: 34,393 protein-altering, 9,761 synonymous, and 1,434 non-coding/regulatory events across
  126 downloaded mutation profiles; no silent classification remains as top gene evidence.
- Rebuilt downstream research outputs after the semantic correction: 194 prioritized consensus candidates and
  5,833 pathway-enrichment rows, including 2,207 in the engineering FDR-enriched tier.
- Explicitly limited claims: consequence-stratified evidence is not driver/passenger classification, pathogenicity,
  causality, or clinical actionability.

## 2026-07-16 - Public Graph Compliance Boundary

- Identified that internal Patient and Sample graph entities were flowing into public Neo4j/Graphify exports despite the
  repository's aggregate-only publication policy.
- Added a shared public graph allowlist and made aggregate-safe filtering the default for exports, API graph endpoints,
  dashboard graph views/downloads, and graph hub metrics.
- Preserved full Patient/Sample topology only in ignored local gold tables for entity-model engineering tests.
- Added stale bulk-file cleanup and a strict demo guard that rejects `PATIENT:` or `SAMPLE:` identifiers in public exports.
- Real sanitized exports contain 55,209 nodes and 255,215 edges with zero individual-entity identifiers; 4,780 internal
  Patient/Sample nodes and 5,533 connected edges were excluded.

## 2026-07-16 - Reproducible Research Benchmark

- Added six deterministic DuckDB analytical workloads over mutation, consensus, pathway, graph, expression, and cohort
  gold marts with two warmups and seven measured repeats by default.
- Added typed JSON reporting for source rows/bytes, SQL hashes, result cardinality, min/median/p95/max latency, software,
  hardware, threads, Git commit, and explicit single-environment interpretation boundaries.
- Real reference run passed all six workloads; warm median latency ranged from 0.274 ms to 3.941 ms on the recorded
  macOS arm64, Python 3.11.15, DuckDB 1.5.4, four-thread environment.
- Added CLI/Make execution, fixture coverage, methodology documentation, and CI artifact generation.

## 2026-07-16 - FAIR Aggregate Research Release Gate

- Added a strict, versioned release builder for public-safe aggregate Parquet marts with semantic-version validation.
- Added fail-closed checks for missing or empty resources, identifier-bearing columns, TCGA/GTEx individual-like values,
  and accidental Patient/Sample graph publication.
- Rebuilt graph resources through the shared public allowlist instead of copying internal graph tables.
- Added SHA-256 checksums, row counts, typed schemas, source provenance, limitations, Frictionless-style metadata,
  citation metadata, and a DOI-deposit runbook.
- Real v0.1.0 acceptance produced 16 resources totaling 42,661,802 bytes; all checksums and identifier checks passed.
- Public graph release retained 55,209 safe nodes and 255,215 safe edges while excluding 4,780 individual nodes and
  5,533 connected edges.
- Verified pytest (`186 passed`), dbt build (`26 models`), and dbt tests (`86 passed`).

## 2026-07-26 - Multi-Reference and Consensus Ablation Evaluation

- Added a common-universe comparison of native GTEx, TCGA adjacent-normal, and uniformly processed
  recount3 tumor-normal effects for BRCA, COAD, and LUAD.
- Added deterministic top-k evaluation at 25, 50, 100, and 250 genes using Jaccard overlap,
  top-list direction agreement, regulated-union direction agreement, absolute-effect Spearman
  association, and effect-magnitude differences.
- Added four consensus sensitivity scenarios with explicit component removal, retained-weight
  renormalization, top-k stability, score association, rank displacement, score deltas, and
  descriptive fixed-threshold retention.
- Centralized consensus component weights so production scoring and ablation cannot drift.
- Real evaluation covered 36,004 common genes per cancer, producing 36 pairwise comparisons and
  48 consensus ablations.
- Direct-reference top-k Jaccard ranged from 0.010 to 0.370, regulated-direction concordance from
  0.124 to 0.396, and absolute-effect Spearman association from 0.618 to 0.812. All direct
  comparisons were reference-sensitive under the predefined engineering tier.
- Removing all three explicit reference components produced score associations of 0.672-0.700 and
  top-k Jaccard values of 0.020-0.575, supporting conservative multi-reference filtering rather
  than single-reference candidate claims.
- Added CLI/Make execution, two gold marts, a JSON report, reviewer SQL, methodology and dictionary
  documentation, FAIR release inclusion, and four standard quality checks.
- Verified pytest (`193 passed`), dbt (`86 tests`), quality (`58 checks`), strict demo (`29 checks`),
  research benchmark (`6 workloads`), project completion (`9/9`), and an 18-resource FAIR bundle.

## 2026-07-26 - Evidence-Linked Manuscript Package

- Added a strict manuscript builder that fails on missing, failing, unsafe, incomplete, or stale
  evidence and validates dbt, quality, strict-demo, completion, graph, benchmark, and FAIR gates.
- Generated a journal-neutral methods/data-engineering manuscript, four aggregate tables, two full
  multi-k supplements, three editable pure-SVG figures, and a reproducibility checklist.
- Added a claim-level evidence ledger over 16 source artifacts with SHA-256 hashes and 10 explicit
  quantitative claims; the package records evidence-producing commit `8474ef5`.
- Replaced the placeholder cohort `gene_count=0` in Python and dbt with the union of normalized
  TCGA/GTEx expression gene IDs; the corrected real inventory contains 61,199 genes and is guarded
  by a positive-count dbt test and a fail-closed manuscript check.
- Preserved conservative scope: candidate lists are hypothesis-generating, multi-reference
  sensitivity is not complete batch correction, and no biomarker, causal, or clinical claim is made.
- Verified `198` Python tests, 88 dbt tests, 58 passing quality checks, 29 strict-demo checks,
  9/9 milestones, six benchmark workloads, 18 FAIR resources, all package hashes, all SVGs, and
  identifier safety.

## 2026-07-26 - Fail-Closed Submission Readiness

- Added a nine-check submission audit with normal reporting and strict failure modes for package
  hashes, claim evidence, author fields, AI disclosure, DOI, biological approval, comparative
  evaluation, publication documents, and open-source licensing.
- Ranked GigaScience Technical Note as the primary target, with Bioinformatics Advances and
  Database as conditional alternatives; documented why JOSS is a later option rather than an
  immediate submission route.
- Preregistered 15 comparator-task evaluations across TCGAbiolinks, UCSC Xena, and cBioPortal,
  including versioned evidence requirements and safeguards against unfair hosted-versus-local
  performance rankings.
- Added an independent biological review checklist and an intentionally unapproved attestation
  template; the gate cannot infer or fabricate scientific sign-off.
- Added an explicit generative-AI disclosure placeholder to the generated manuscript and rebuilt
  the evidence package against commit `b7f32eb`.
- Current status is intentionally `not_ready`: four checks pass and five blockers remain for author
  and AI fields, DOI deposit, independent biological review, and comparative evaluation.
- Verified `202` Python tests and successful manuscript package regeneration.

## 2026-07-26 - Comparative Evaluation Evidence Harness

- Expanded the preregistered comparison to the correct 20-row matrix: five CancerOmicsLake baseline
  tasks plus five tasks for each of TCGAbiolinks, UCSC Xena, and cBioPortal.
- Added atomic task evidence collectors, local-path containment checks, live API capture, version
  recording, report assembly, strict incomplete-result handling, and CLI/Make execution.
- Pinned xenaPython 1.0.14 to upstream commit `f243bbf` in a separate comparison dependency file so
  the research API client does not become a core platform dependency.
- Live CancerOmicsLake T1-T5 passed using aggregate cohort, TP53 expression, TP53 mutation,
  reproducibility, and public-safe graph evidence.
- Live cBioPortal T1 passed against three GDC TCGA studies through its public REST API; UCSC Xena T1
  passed against three GDC cohorts and integrated TCGA/GTEx hubs through its pinned Python client.
- Current comparison status is honestly `in_progress`: 7/20 results complete, 13 pending, and zero
  failed. TCGAbiolinks remains unexecuted because the Docker daemon and Bioconductor container were
  unavailable, not because the tool was judged unsupported.
- Verified `205` Python tests and retained the fail-closed submission blocker.

## 2026-07-26 - Containerized TCGAbiolinks Comparison

- Added a digest-pinned Bioconductor 3.21 image with TCGAbiolinks 2.36.0 and retryable installation
  through the official Posit Bioconductor mirror.
- Added an aggregate-only live GDC collector for expression metadata across BRCA, COAD, and LUAD,
  plus LUAD masked-mutation metadata and a machine-readable package capability inventory.
- Classified outcomes conservatively: cohort discovery passed; expression, mutation, clean
  rebuild, and graph-export tasks remained partial, with absent named APIs treated as unverified
  rather than proof of unsupported capability.
- Added CLI and Make targets, evidence checksums, image identity, execution timing, tests, and
  protocol documentation without promoting partial capability evidence to a biological result.

## 2026-07-26 - Complete External Comparative Matrix

- Expanded the live UCSC Xena collector from cohort discovery to uniformly reprocessed BRCA TP53
  tumor-versus-GTEx breast expression, LUAD MC3 protein-altering TP53 frequency, reproducibility
  metadata, and identifier-safe aggregate export.
- Expanded the cBioPortal collector to inventory BRCA expression/GTEx scope, calculate LUAD TP53
  mutation frequency against the portal sequenced-sample denominator, record hosted-service
  reproducibility limits, and export an aggregate-safe cancer-gene edge.
- Completed all 20 preregistered rows with 13 passed, seven partial, zero missing, and zero failed;
  partial rows remain explicit rather than being promoted to equivalently completed analyses.
- Preserved source-specific results: Xena MC3 reported 257/507 protein-altering LUAD TP53 samples
  and cBioPortal GDC reported 277/559, demonstrating why denominators and processing provenance
  must accompany mutation-frequency comparisons.
- Kept individual sample identifiers in memory only; persisted external evidence contains aggregate
  counts, versions, checksums, limitations, and aggregate relationship tables.

## 2026-07-26 - Fail-Closed Manuscript Metadata Contract

- Replaced hard-coded manuscript identity and disclosure fields with
  `configs/manuscript_metadata.yml` as the durable source of truth.
- Added explicit confirmation flags for author metadata, declarations, exact AI tool/model records,
  human review, and author responsibility; pending values continue to render visible placeholders.
- Added the exact metadata snapshot to every generated manuscript package and its SHA-256 manifest.
- Strengthened submission readiness so deleting placeholder text cannot bypass missing metadata or
  human-confirmation requirements.
- Documented the metadata-first workflow and added tests for complete, incomplete, and attempted
  marker-bypass scenarios.
- Verified 210 Python tests with the four legitimate external/human publication blockers retained.

## 2026-07-26 - Provenance-Refreshed Manuscript Release Candidate

- Regenerated the benchmark, reference-ablation report, 18-resource FAIR bundle, and manuscript
  package against clean evidence-producing commit `011de8b`.
- Refreshed the manuscript evidence ledger and package hashes while preserving visible placeholders
  for unconfirmed affiliation, email, declarations, and AI-use details.
- Added the exact structured metadata snapshot to the 15-file manuscript package.
- Verified FAIR identifier safety, 14 manuscript-package hashes, 210 Python tests, and five of nine
  submission checks; DOI registration, metadata confirmation, AI confirmation, and independent
  biological review remain external gates.

## 2026-07-26 - Deterministic DOI-Deposit Archive

- Added a FAIR release packager that re-verifies every resource checksum and identifier-safety
  status before creating an external-deposit artifact.
- Normalized archive ordering, ownership, permissions, tar timestamps, and gzip metadata for
  byte-reproducible packaging.
- Added CLI/Make execution, a machine-readable deposit manifest, tamper rejection, deterministic
  rebuild tests, and DOI runbook documentation.
- Built the real 22-file, 42,348,808-byte v0.1.0 archive twice with identical SHA-256
  `3d418eaaa0aa9b19bce22bff661257484e4d764d7eb9a46c644f6353b85ae039`.
- Kept `doi: null` and an explicit claim boundary until a human uploads the archive and registers
  the persistent identifier.

## 2026-07-26 - External Publication Handoff Packets

- Added form-ready DOI deposit metadata with archive path, exact size, SHA-256, evidence commit,
  description, keywords, licensing boundary, source acknowledgements, and post-mint update steps.
- Added an independent biological-review request with a bounded review scope, six concrete
  questions, evidence locations, attestation instructions, and explicit non-clinical claim limits.
- Registered both handoff packets as required publication documents while preserving human control
  over DOI minting, reviewer approval, authorship, and scientific sign-off.

## 2026-09-20 - Functional and Recurrent Mutation Evidence

- Added a separate gold mart that stratifies protein-altering mutation support into putative
  loss-of-function, missense, in-frame, and other conservative MAF classes.
- Added exact chromosome/start/reference/alternate recurrence features using a preregistered
  minimum of two distinct samples, without promoting recurrence to pathogenicity or driver status.
- Fixed `driver_classification` to `not_assessed` and excluded the new evidence from candidate
  scoring until an externally reviewed integration and validation method is available.
- Verified exact Python/dbt parity across 18,972 cancer-gene rows; the partial real cohort contained
  142 recurrent loci across 133 cancer-gene pairs.
- Passed 60 runtime quality checks, 27 dbt models, 94 dbt tests, and 219 Python tests.

## 2026-09-24 - Mutation Coordinate Assembly Provenance

- Confirmed the GDC masked MAF files expose `NCBI_Build`; retained this value as
  `reference_assembly` in silver mutation records.
- Included assembly in exact-locus recurrence keys and prevented unknown-assembly events from
  contributing recurrence while preserving them in consequence counts.
- Rebuilt real silver/gold and dbt outputs: all 45,588 mutation records carry `GRCh38`; the gold
  mart retains 18,972 cancer-gene rows and 142 recurrent loci across 133 pairs.
- Confirmed Python/dbt equality across all 18,972 rows, with 60 quality checks and 97 dbt tests
  passing. This remains a partial downloaded cohort.

## 2026-09-24 - GDC MAF Transcript Annotation Retention

- Extended the silver mutation contract to retain MAF-reported transcript ID, HGVS coding and protein
  fields, exon, Sequence Ontology consequence, VEP impact, and the original `all_effects` string.
- Added aggregate transcript annotation evidence by cancer, gene, transcript, consequence, and impact,
  with sample/event counts and annotation coverage counts.
- Recorded the GDC limitation that MAF selects the most critically affected transcript; VEP impact is
  retained as a source label and is not treated as driver/pathogenicity evidence.

## 2026-09-29 - Transcript Evidence Verification

- Rebuilt gold and dbt from the existing partial real cohort: 45,588 mutation records yielded 31,928
  transcript-evidence groups. Python Parquet and dbt tables matched on every row and metric.
- Passed 62 silver/gold quality checks, 104 dbt tests, and 222 Python tests; project completion
  reported 9/9 milestones and the FAIR release bundle contained 20 resources.
- These are source-reported annotation aggregates, not independent transcript validation or
  evidence of driver status, pathogenicity, or publication-ready biological findings.

## 2026-09-29 - Automated Transcript Mart Parity Gate

- Added a dbt data test that compares all Python and dbt transcript-evidence rows in both directions,
  including duplicate multiplicity; CI now builds gold before dbt to make this test executable.
- Verified 105 dbt tests passed on current data. A one-row event-count mutation in a temporary copy
  produced the expected parity-test failure (two directional difference rows).
- The gate checks implementation agreement, not biological accuracy or independent validation.

## 2026-09-29 - Mutation Sample Identity Reconciliation

- Audited the 45,588 real mutation rows against the downloaded MAF profile: 126 distinct mutation
  samples and 126 profile samples shared case IDs but initially had zero matching sample IDs because
  MAF tumor barcodes and GDC sample UUIDs occupied different namespaces.
- Preserved each MAF barcode in `source_sample_id`; mapped the canonical `sample_id` only when the
  same file/case has one metadata sample and one MAF tumor barcode. Ambiguous cases stay unresolved.
- Added Python and dbt quality gates for mutation-to-profile sample linkage, plus fixtures for a
  unique mapping, an ambiguous mapping, and an orphaned mutation sample.
- Rebuilt the partial real cohort: all 126 mutation samples now link to a profile, with zero orphans.
  Passed 226 Python tests, 63 runtime quality checks, 28 dbt models, and 107 dbt tests.
- Prior equality of case counts did not establish sample identity; this correction does not make
  capped-cohort mutation frequencies representative of full TCGA cohorts.

## 2026-09-30 - Evidence Confidence Tier Reachability Audit

- Found zero high-tier rows in the partial real cohort, but the score is not broken: with current
  candidate biological support capped at 0.6053, even perfect non-biological components yield a
  maximum overall score of 0.703975, below the fixed high-tier cutoff of 0.75.
- Added a per-cancer calibration report exposing observed score, current-support ceiling, tier counts,
  and reachability without changing weights or retroactively relabeling candidates.
- Real-data report covers 108,600 cancer-gene rows: zero high, 82,033 moderate, and 26,567 limited;
  the per-cancer upper bounds are BRCA 0.668425, COAD 0.703975, and LUAD 0.696325.

## 2026-09-30 - Submission Evidence Revision Gate

- Found that a `passed` comparison and benchmark could be accepted by submission readiness even when
  their CancerOmicsLake revision differed from the manuscript package or current checkout.
- Added a fail-closed revision check for the package, claim ledger, benchmark, ablation, and project-side
  comparator rows. External comparator versions remain independent and are not forced to match our Git SHA.
- Existing historical evidence is preserved; refreshing it is required only for a current-submission claim.
- Live readiness audit now reports five blockers rather than four: the four human/deposit/review
  blockers plus stale revisioned evidence. Comparative task coverage still passes separately.
- Verified 233 Python tests. Git-commit agreement does not replace data-snapshot or package-hash review.

## 2026-09-30 - Manuscript Source-Evidence Integrity Gate

- Found that readiness checked hashes of generated manuscript files but did not rehash the reports
  and gold tables listed as sources in the claim evidence ledger.
- Added a fail-closed ledger-resource check for file existence, repository-contained paths, exact
  byte counts and SHA-256, unique resource names, and claim-to-resource references.
- A modified source report now blocks submission even when its Git revision still matches;
  this is an integrity check, not a biological validation claim.
- On current local evidence, readiness reports six blockers: the four human/deposit/review items,
  stale code revision, and changed ledger source resources. All 235 Python tests pass.

## 2026-09-30 - Release Handoff Metadata Correction

- Found stale, hard-coded archive size, SHA-256, resource count, and Git commit in the deposit and
  biological-review handoff documents after the current release bundle was rebuilt.
- Replaced those values with instructions to read and verify the freshly generated deposit and FAIR
  manifests. No DOI or independent review status has been asserted.

## 2026-10-04 - Controlled Research Evaluation and Input Integrity Repair

- Started the research-strengthening goal without asserting RECOMB suitability or novel methods.
- Added a frozen native-TPM study: patient/donor-separated development and holdout partitions,
  identical tumor sets across references, balanced reference sizes, training-only gene filters,
  repeated development subsampling, scale/pseudocount experiments, baseline rankings, and
  conditional paired-bootstrap holdout intervals. Full and pilot configurations are separate.
- The first real-data pilot stopped on duplicate sample/gene measurements. Whole-table diagnostics
  found 571,592 duplicate groups in the old native TCGA TPM snapshot, including 26,444 groups
  with within-file duplication. Raw STAR identifiers confirmed the `_PAR_Y` normalization collision.
- Fixed numeric version stripping to preserve pseudoautosomal locus identifiers. TCGA ingestion
  now chooses a whole same-workflow file by sorted provenance path without inspecting expression
  values; conflicting workflows or within-file duplicates fail. Rebuilding silver is in progress;
  downstream reports and manuscript evidence must be regenerated, not treated as current.
- Preserved the failed pilot protocol; the corrected pilot uses a new study identifier (v2).
- Added seven offline synthetic fault experiments against production guards. All passed:
  corrupted downloads, retry after interruption, schema drift, duplicate measurements, negative
  expression, same-size stale evidence, and changed frozen protocol. These are not external
  workflow benchmarks, real-network recovery measurements, or independent human reproduction.
- Corrected the manuscript generator's TCGA file quantity to describe metadata catalogue entries,
  and added substantive primary-literature positioning. The existing manuscript is not silently
  regenerated or represented as submission-ready.
- Validation: full suite 252 passed (one upstream FastAPI/Starlette deprecation warning);
  28 focused tests passed after the final protocol/dependency fingerprint changes.
- Remaining: corrected live-study execution, paired-only and verified matched-processing arms,
  external/known-truth evaluation, actual workflow comparisons, independent reproduction, and
  evidence-based novelty assessment. Public release/DOI publication remains disabled.

## 2026-10-04 - Paired Reference Pilots and Known-Truth Counterexample

- Verified the silver rebuild completed: 36,456,660 native TCGA expression rows,
  11,240,000 GTEx expression rows, and 45,588 mutation records. No new acquisition was required.
- Added a separate paired-only arm that partitions complete patients and selects the same cases
  for tumor and adjacent-normal groups, with donor-balanced GTEx reference sizes.
- Both corrected real-data pilots completed all three cohorts with 20 units per group/partition.
  At top-50, lower-quantile and simple maximin ranking both achieved reference replication 1.0
  in all cancers in both pilots. This does not establish incremental novelty of the bootstrap score.
- Executed a frozen five-scenario truth simulation with 20 independent datasets per scenario.
  The shared-normal-bias counterexample had lower-quantile top-25 truth precision 0.018 despite
  reference replication 1.0. Reference concordance must not be interpreted as biological validation.
- Added a hash-verified review bundle retaining all methods/cancers/top-k results and explicit
  research-incomplete/publication-disabled status. Pilot and full studies remain separate.
- Strengthened fault experiments with measured retry-disabled and size-only controls; all seven
  scenarios still pass. These are isolated synthetic comparisons, not external workflow benchmarks.
- Full native and paired preset studies (200 training/holdout draws, 50 development repeats)
  are running without performance-driven parameter retuning. Pilot holdout inspection is disclosed.
- Docker reproduction inspection confirmed that the daemon is unavailable. No independent
  reproduction or biological review is claimed.
- Validation: final full suite 256 passed (one upstream deprecation warning). Five focused
  simulation, fault and review-integrity tests also passed. Public release/DOI remains disabled.

## 2026-10-04 - Full Native Study, Container Reproduction and Pairing Audit

- Corrected silver quality passed all 63 checks. The full native study completed all three
  cohorts with 200 training/holdout bootstrap draws and 50 development repeats. At top-50,
  lower-quantile minus maximin replication differences and conditional interval endpoints were
  zero in all three cohorts. This does not demonstrate an incremental new-method advantage.
- Started Docker Desktop, ran 20 research tests in the existing image, and reproduced the
  primary pilot in separate output/private roots. All 72 heldout rows and 2,400 candidate rows
  matched exactly. Three sensitivity Spearman cells differed by 6.14e-9 and failed the fixed
  numeric tolerance; the failure was retained with diagnostics, not relaxed posthoc.
- Added an environment-comparison report that checks input and implementation fingerprints,
  exact identifiers/schemas, and predefined float tolerances. This is same-author reproduction,
  not independent investigator confirmation. Host/container Polars versions differed; this does
  not identify a single cause of the tiny discrepancy.
- Produced a new evidence-derived exploratory manuscript draft inside the review bundle with
  verified measurement counts, substantive related work, all baseline results and explicit
  limitations. Labeled the legacy manuscript historical and corrected its manifest-count wording;
  its older package hashes are intentionally not resealed or represented as current.
- Found the first paired protocol's development subsampling drew the two TCGA groups independently.
  Corrected it to draw shared case identities; tests cover reordered columns and invalid identity
  sets. Preserved the original source and artifacts and assigned new immutable study IDs.
- Original full paired execution continues unchanged. Corrected full paired v2 is running separately;
  only v2 can support pair-preserving development-subsampling claims. No ranking parameters were
  retuned and no public release or DOI publication was performed.

## 2026-10-04 - Expression-Key Quality Contract and Evidence Audit

- Added unique sample/gene/unit measurement checks for TCGA and GTEx silver expression tables.
  Direct Parquet inputs cannot now pass quality merely because values are non-negative while
  containing duplicate measurements. Missing key schemas fail even for empty inputs.
- Eleven focused silver-quality and measurement-key tests passed. The live corrected quality
  rerun now includes 65 checks and is in progress; no pass is inferred from the earlier 63-check run.
- Added a requirement-by-requirement research-goal audit distinguishing completed evidence from
  unverified claims, and generated a full-native review/draft separately from historical pilots.
- Final verification after the latest quality changes is running. Corrected full paired v2 is
  also still active; no paired-subsampling or combined-full-review completion is claimed yet.

## 2026-10-04 - Corrected Full Evidence Review Completed

- Corrected full paired v2 completed all three cancers with zero patient/donor partition leakage.
  The same-case development-subsampling repair is now covered by executed full-study evidence.
- Both full studies have zero top-50 lower-quantile-minus-maximin replication differences in all
  three cancers. Kept the null advantage rather than claiming a novel-method improvement.
- Generated the combined full evidence review and current exploratory manuscript draft from
  completed native v1 and corrected paired v2, retaining every method/cancer/top-k result.
- Final suite passed 262 tests; live silver quality passed all 65 checks, including the two new
  unique-measurement contracts. A further two review-generation tests passed after wording fixes.
- Prepared an independent-reproduction handoff and requested whether an independent investigator
  is available. No independent confirmation, biological validation, release or DOI is asserted.
- Native/recount3 exact identifier probing found no TCGA overlap in the current 90 recount3 samples
  against native file/sample/case/submitter IDs. This does not rule out a metadata-based specimen
  crosswalk, which requires further provenance verification.

## 2026-10-04 - Global Donor Partition Audit and Correction

- User confirmed no independent reviewer is available; prepared the handoff and retain independent
  reproduction as unverified. Public release and DOI deposition remain disabled.
- Final manifest audit found 26 GTEx donors crossing folds across cancers in both native v1 and
  paired v2. Earlier zero-leakage statements applied within cancer only; withdraw global claims.
- Protocol 1.1 assigns each source/case or source/donor globally, stratified by project/group
  availability, before per-cancer balancing. Added global manifest guard and report fields.
- Added shared-donor, deterministic-order, deliberate leakage and multicancer integration tests;
  focused research/review suite passed 20 tests. Retained prior immutable plans and source archives.
- New full/pilot IDs explicitly include `global`; new real-input executions are required before
  replacing the historical review. Shared donors remain a source of dependence across cancers.
- Full suite passed 264 tests, followed by two review tests that check historical warnings and
  reject a nonzero global leakage count. Seven offline fault scenarios still passed; graph updated.
- Archived protocol-1.1 source by SHA-256. Started a detached sequential full native/paired runner
  at `outputs/research/run_global_studies.sh`, with log and machine-readable status in the same
  directory. It checks both private manifests before generating `global_evidence_review` and
  stops if the frozen source changes. No completion is claimed while status is running.
- Regenerated the historical full review with explicit global-partition limitations. No public
  release, DOI deposit or independent-review claim was made.

## 2026-10-13 - Corrected Study Rerun and recount3 Provenance Check

- The prior detached study process stopped without a recorded exception; the status file remained
  `running` and neither full report existed. Restarted the unchanged frozen run in an attached
  session; the three-cancer global pilot had already completed with zero cross-cancer fold leakage.
- Recount3 metadata provides GDC sample UUID and GTEx SAMPID mapping, but all 90 selected TCGA
  recount3 records have `gdc_access=controlled`. The open-access-only public pipeline cannot use
  these as matched-processing evidence without an explicit provenance/access resolution.
- Added an aggregate-only specimen crosswalk audit that rejects controlled selected TCGA records,
  ambiguous specimen IDs, and case/donor mismatches. Three focused tests passed. The live audit
  raised `PermissionError` and wrote no crosswalk output.
- Full test suite passed 267 tests with one existing Starlette/httpx deprecation warning.
- Primary recount3 docs and the AWS Open Data registry identify its processed expression release
  as publicly available/public domain. Revised the audit to distinguish upstream controlled GDC
  files from the processed release: strict default plus explicit `--allow-public-derived` mode.
  That mode downloads no controlled GDC files and emits aggregate counts/hashes only. It found
  19/90 unambiguous exact TCGA matches and 87/90 GTEx matches; two COAD recount3 files sharing
  one specimen were excluded. No processing-equivalence or biological claim follows from this.
- The attached sequential runner completed both protocol-1.1 full studies and generated
  `outputs/research/global_evidence_review/`. Each study evaluated three cancers, wrote 72
  heldout rows, selected 423 specimen rows and passed the private global fold audit.
- In both corrected full studies, top-50 lower-quantile versus maximin replication difference is
  exactly zero for BRCA, COAD and LUAD. The new review remains `research_incomplete` with
  `publication_enabled=false`. Independent human reproduction remains unverified.

## 2026-10-13 - Frozen Exact-Specimen Processing Sensitivity

- Locked `matched_processing_v1` before metric computation (seed 20261013; input, dependency,
  code and source-revision fingerprints). Selected all 617 exact unambiguous matches from cached
  public recount3 processed data: 417 TCGA and 200 GTEx. Private specimen manifest/metrics are
  under `data/research/`; the strict access default remains, with explicit public-derived opt-in.
- Preserved `_PAR_Y` during recount3 Ensembl normalization. New versioned silver table has
  39,399,152 measurements and zero duplicate `(source, sample_id, gene_id)` keys. The older
  30-per-cohort recount3 extract and original global review were not modified.
- Per-specimen median Spearman on shared genes is about 0.866-0.868 for TCGA and 0.925-0.926
  for GTEx; top-100 expressed-gene Jaccard medians are only 0.38-0.42. Top-50 tumor-versus-GTEx
  absolute-effect Jaccard is 0.0204 (BRCA), 0 (COAD), 0.0204 (LUAD). Native cutoff tie counts
  are 488, 412 and 515. These unfavorable, tie-sensitive findings are retained in the manuscript
  draft; no cross-unit numeric expression, biological validation or novelty claim is made.
- Built new `global_evidence_review_v2` with a verified processing plan/resources and
  `publication_enabled=false`. Verified 32 source/artifact hashes and scanned nine aggregate
  report/figure files against 1,748 private identifier strings; no matches found. Archived the
  four hashed implementation files locally under `outputs/research/protocol_sources/`.
- Full suite: 274 passed, one existing Starlette/httpx deprecation warning. Existing silver
  quality stage: 65 checks passed; the new table's uniqueness was checked separately. Independent
  human reproduction, full published-method comparison and biological validation remain open.

## 2026-10-13 - Post-v1 Matched Processing Diagnostic
- Froze `matched_processing_v2` against the 617-specimen v1 manifest and corrected silver inputs,
  with code/dependency/input hashes and row counts. Reused all inputs offline; preserved v1 and
  both older review bundles. Archived v2 implementation under `protocol_sources/`.
- Completed all three cancers and 200 paired case/donor resamples per cancer, with 1000 seeded
  point tie draws and 100 tie draws per bootstrap replicate. Fixed 20%-detection filtering kept
  31,875-33,684 genes of 55,660 complete shared genes; no post-hoc threshold adjustment.
- Signed effect Kendall tau-b was 0.556-0.571 across all genes, and thresholded direction
  agreement was 89.8%-90.5%. Top-50 tie-aware mean overlap was only 0.0026-0.0058, versus
  deterministic v1 0-0.0204. The informative subset remained weak (0.0042-0.0086). Broad
  agreement and unstable top candidate lists are both reported without claiming biology.
- Aggregate annotation audit found 20,347 shared TCGA/recount3 symbol-string differences, none
  for GTEx/recount3, plus gene-universe and `_PAR_Y` counts. These data do not isolate a causal
  mechanism. Built a separate v3 review with publication disabled; independent reproduction
  and external/biological validation remain unverified.
- Idempotent v2 rerun verified 26 source/aggregate/private resource hashes. Scanned 12 public
  aggregate files against 1,748 private identifier strings with zero matches. Full suite passed
  282 tests with one existing Starlette/httpx deprecation warning; baseline silver quality
  passed 65 checks. The new v2 metrics are validated separately; the baseline 65-check stage
  does not replace the study-specific hash, privacy and bootstrap checks.

## 2026-10-14 - Published RRA Comparator Protocol

- Added a separate official-R-package comparator runner, pinned-version Docker build path,
  frozen resource plan, global-split/candidate reconstruction checks, paired holdout bootstrap
  comparison, aggregate-only review builder and tests. Prior studies/reviews are untouched.
- All six frozen cohort/study combinations reproduced their existing candidates and heldout
  metrics. Full test suite passed 287 tests; read-only silver quality passed 65 checks.
- An unsandboxed Docker Desktop start restored the daemon. Built the R image from a pinned
  base digest, smoke-tested official RobustRankAggreg 1.2.1, froze image/code/input hashes,
  then completed all 18 top-k cells in six cancer/study combinations. The v4 aggregate review
  is separate; earlier reviews remain untouched.
- At top-50, proposed-minus-RRA heldout replication was 0.02-0.10, with one paired interval
  including zero. Official RRA versus the old heuristic had top-50 Jaccard 0.515-0.887.
  This does not overcome the prior no-advantage result against maximin. Publication stays disabled.
- Verified 17 frozen resources and scanned four aggregate files against 1,261 private ID strings:
  no matches. A full official R/Python rerun preserved both aggregate file hashes exactly.
  Independent human reproduction remains unverified.

## 2026-10-15 - Engineering Completion Execution

- Completed the four-runtime numerical diagnosis and corrected-global replays using archived
  source and fixed tolerances. Cross-OS log2 effects first differ by at most 4.44e-16; tested
  Polars-only changes do not explain the discrepancy. Candidate lists and heldout metrics
  reproduce, while 63 native and 60 paired sensitivity cells retain strict-tolerance failures.
- Added the pinned cached-input external-workflow benchmark, aggregate v5 package builder,
  figures, source snapshot, submission gates and separate future-method protocol. The earlier
  full suite passed 297 tests and read-only silver quality passed 65 checks; final verification
  after the last edits is queued, not yet claimed complete.
- First benchmark pass completed for both implementations. The remaining reversed-order pass,
  fault probes and native-script integrations continue without model polling. A follow-on
  `scripts/finalize_engineering_evidence.sh` job waits for the existing benchmark process, then
  verifies resources, tests, quality, package idempotence and code graph. Its current stage is
  recorded in `outputs/research/engineering_acceptance_v1/finalization.json`; private diagnostics
  are in `data/research/engineering_acceptance_v1/finalization.log`.
- No new biomedical downloads, public release or DOI deposit. Frozen earlier evidence stays
  unchanged. Final package execution, independent human reproduction and author confirmations
  must not be inferred merely from this implementation entry.


## Executed engineering evidence (2026-10-15)

Cached preparation completed 21 workload equivalence cells and 84 tool/pass/workload summaries in two passes. Module comparability: True. Native-script comparable outputs: 7/7. Full tests: 297 passed; read-only silver quality: passed (65 checks). Strict numerical sensitivity failures remain retained. Shared TMM normalization and emulated hardware prohibit an end-to-end superiority claim. Independent human reproduction is unverified; author declarations and publication approval remain pending. Publication and DOI deposit are disabled. See the separate v5 review.
## 2026-10-19 - Interview synopsis reviewed and revised

- Reviewed revision 1 for contribution focus, study design, uncertainty,
  denominators and interpretation. Recorded findings and unresolved scientific
  requirements in `manuscript/interview_brief_v2/reviewer_notes.md`.
- Created a separate four-page revision 2 with a directed system workflow,
  matched-processing design diagram and paired-bootstrap interval plots. Added
  617-available/567-primary specimen distinction, separate reference-study group
  sizes, and sensitivity-column failure denominators (63/8,100 and 60/8,100).
- Preserved the first brief and all frozen studies. Verified 49 evidence
  bindings, every plotted interval endpoint, prior-brief hashes, layout and
  identifier checks; visually inspected the revised PDF. The source archive
  compiled independently to four pages in a clean temporary directory.
- Presentation changes do not resolve independent reproduction, novelty,
  biological/causal validation or the documented numerical failures. No new
  scientific experiments, publication or independent peer review are claimed.
