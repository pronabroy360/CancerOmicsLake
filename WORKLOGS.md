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
| M1 Project Setup | Done | pronabroy360 + Codex | 2026-05-27 | 2026-05-27 | Scaffold, configs, Makefile, API/dashboard stubs, tests passing |
| M2 Metadata Ingestion | In Progress | pronabroy360 + Codex | 2026-05-27 | 2026-05-28 | Live GDC API query path implemented with retries and stub fallback |
| M3 Expression Processing | In Progress | pronabroy360 + Codex | 2026-05-27 | 2026-05-29 | Silver expression TCGA/GTEx tables now generated with stable schemas |
| M4 Mutation Processing | Not Started | | | | |
| M5 dbt Warehouse | Not Started | | | | |
| M6 Data Quality Layer | Not Started | | | | |
| M7 Knowledge Graph | Not Started | | | | |
| M8 Dashboard | Not Started | | | | |
| M9 Final Packaging | Not Started | | | | |

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
