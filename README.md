# CancerOmicsLake

CancerOmicsLake is a reproducible bioinformatics data engineering project that integrates open-access TCGA cancer genomics data from the NCI Genomic Data Commons with GTEx normal tissue expression data. The project builds a lakehouse-style architecture with bronze, silver, and gold data layers, transforms raw biomedical files into research-ready analytical tables, and exports cancer-gene-tissue relationships into a knowledge graph for visualization through Graphify/Neo4j-style tools. The MVP focuses on TCGA-BRCA, TCGA-LUAD, and TCGA-COAD with matched GTEx normal tissues.

## Current Status

Implemented so far:

- Project structure and config system
- GDC metadata ingestion path (live with safe fallback)
- Bronze metadata and manifest generation
- GDC ingestion audit reporting (`outputs/reports/gdc_ingestion_audit.json`)
- Strict live-ingestion support (`tcga.require_live_gdc`)
- File-based TCGA/GTEx expression loaders with fallback behavior
- Silver parquet outputs for projects, patients, samples, file manifest, and expression tables
- Mutation MAF parsing and mutation-frequency gold marts
- Gold cohort, expression, tumor-vs-normal, mutation, candidate gene-priority, and graph marts
- Quality report generation
- Graphify and Neo4j CSV graph exports
- FastAPI endpoints and Streamlit dashboard pages backed by local marts
- Test suite for config, ingestion, parsing, silver/gold builders, graph exports, API, dashboard data, reporting, and quality checks
- Daily CI schedule + dbt run/test gate on Python 3.11
- Local dbt runner with automatic Docker fallback when Python 3.14 is incompatible
- Medium-cap real ingestion profile (`expression<=25`, `mutations<=10` per project)
- Pipeline run-mode tagging (`manual`/`push`/`scheduled`) and run history tracking
- Project completion report for milestone-level release readiness (`outputs/reports/project_completion_report.json`)

## Architecture

```text
Public TCGA/GTEx sources
        |
        v
YAML config + ingestion clients
        |
        v
Bronze metadata/files -> Silver normalized parquet -> Gold analytics marts
        |                         |                    |
        |                         v                    v
        |                    Quality reports       DuckDB/dbt models
        |                                              |
        v                                              v
Graphify/Neo4j exports                          FastAPI + Streamlit
```

Detailed docs:

- `docs/architecture.md`
- `docs/data_dictionary.md`
- `docs/graph_schema.md`
- `docs/reproducibility.md`
- `docs/sample_queries.md`

## Quickstart

```bash
make setup
make test
make run-metadata
make run-metadata-strict
make run-metadata-strict-smoke
make run-download-tcga-medium
make run-download-tcga-aggressive
make run-silver
make run-gold
make run-quality
make run-dbt
make test-dbt
make run-flow-medium
make run-flow-aggressive
make run-demo-check
make run-ingestion-traceability
make run-project-completion
```

Optional application surfaces:

```bash
make run-api
make run-dashboard
make run-graph-export
```

Reviewer demo path:

```bash
make run-demo
make run-demo-aggressive
make run-demo-check-strict
```

`make run-demo` executes the capped pipeline and verifies that silver/gold marts, quality reports, graph exports, API health, and dashboard data contracts are ready for demonstration. `make run-demo-check-strict` additionally rejects stub/demo-origin rows and requires live GDC audit provenance.

## Medium Cap Profile

- Default medium cap in this sprint:
  - `expression: 25 files/project`
  - `mutations: 10 files/project`
- Applies to `TCGA-BRCA`, `TCGA-LUAD`, and `TCGA-COAD`.
- Use:
  - `make run-download-tcga-medium` for download-only stage
  - `make run-flow-medium` for end-to-end flow
- Intended for repeatable daily automation and local demonstration, not full-cohort completeness.
- Expected storage depends on GDC file availability, but this profile is deliberately bounded to avoid accidental large downloads.

## Aggressive Cap Profile

- Aggressive cap profile:
  - `expression: 100 files/project`
  - `mutations: 40 files/project`
- Applies to `TCGA-BRCA`, `TCGA-LUAD`, and `TCGA-COAD`.
- Use:
  - `make run-download-tcga-aggressive` for download-only stage
  - `make run-flow-aggressive` for end-to-end flow
  - `make run-demo-aggressive` for pipeline + traceability + demo checks
- This profile is intended for fast manual completion and uses `--force-download`.
- Flow/demo targets focus download scope on `expression,mutations` for higher success rates.

## Runtime Notes

- dbt execution source-of-truth is CI Python `3.11`.
- Local Python `3.14` remains supported for non-dbt pipeline commands.
- `make run-dbt` and `make test-dbt` automatically use local dbt when supported, otherwise fall back to the `dbt` Docker Compose service.
- GitHub Actions runs on push/pull request and once daily through the scheduled workflow.
- CI uploads run reports, ingestion audit output, download summaries, pipeline metadata, and graph export bundles as artifacts.
- CI now runs `make run-download-tcga-ci-smoke`, `make run-graph-export`, and `make run-demo-check` as a bounded reviewer-readiness gate.
- CI and manual ingestion workflows now also generate `outputs/reports/project_completion_report.json` so milestone readiness is reviewable as an artifact.
- Manual ingestion workflow is available in GitHub Actions (`CancerOmicsLake Manual Ingestion`) with profile selection (`medium`/`aggressive`) and optional strict no-stub validation.

## Example Questions

- Which genes are most overexpressed in TCGA-BRCA compared with GTEx breast tissue?
- Which genes are commonly mutated in TCGA-LUAD?
- Which cancer-gene relationships are exported to the graph layer?
- What percentage of source files and table rows passed quality checks?

See `docs/sample_queries.md` and `outputs/sample_queries/` for reviewer-friendly SQL examples.

## Ingestion Traceability

Generate a download-to-silver traceability report:

```bash
make run-ingestion-traceability
```

This writes `outputs/reports/ingestion_traceability_report.json` with per-project/per-modality candidate/selected/downloaded/skipped/failed counts and silver parsed row/file coverage.

## Compliance Notice

- Public mode is `open-access-only` by default.
- Do not commit raw downloaded data, restricted data, or credentials.
- This repository is for data engineering and exploratory analytics, not clinical claims.
