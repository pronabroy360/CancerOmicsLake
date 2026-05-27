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
| M3 Expression Processing | Not Started | | | | |
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

## 6) Decision Log (ADR-lite)

| Date | Decision ID | Context | Decision | Alternatives Considered | Impact | Owner |
|---|---|---|---|---|---|---|
| 2026-05-27 | DEC-001 | Dataframe stack for MVP | Start with Polars-compatible pipeline stubs and typed config models | Pandas-first | Keeps performance-oriented path while staying simple for MVP |
| 2026-05-27 | DEC-002 | Environment setup on macOS | Use local `.venv` for project commands | System Python install | Avoids PEP-668 conflicts and keeps dependencies isolated |
| 2026-05-27 | DEC-003 | Code navigation at scale | Enable `codeindex` and build symbol index early | Manual grep-only navigation | Faster iterative development and safer refactors |
| 2026-05-27 | DEC-004 | GDC ingestion resilience | Implement live API query with retry/backoff and configurable stub fallback | Hard fail on first network issue | Keeps local/dev workflow moving while preserving path to real metadata |

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
- Next:
  - Add request audit logs and retry failure logs to metadata ingestion outputs
  - Add first real silver parquet writer
  - Add optional strict mode to fail fast when live GDC fetch is required
