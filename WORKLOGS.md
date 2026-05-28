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
  - Expanded quality checks to include TCGA expression null/non-negative checks
  - Added `run-metadata-strict-smoke` operational target and `.github/workflows/ci.yml` automation
- Next:
  - Expand quality checks for mutation and future TCGA expression tables when parsers land
  - Add manifest-driven TCGA expression file discovery and parser normalization presets per workflow
  - Replace stub-first TCGA expression path with real cohort expression files from manifest-driven ingestion
