# AGENTS.md

This document defines human and AI agent responsibilities for building **CancerOmicsLake**.

## 1) Mission

Build a reproducible, open-access-only TCGA + GTEx bioinformatics data engineering platform with:

- Lakehouse layers (bronze/silver/gold)
- Analytical warehouse models
- Data quality validation
- Graph exports (Neo4j/Graphify style)
- Dashboard + API
- Publication-safe documentation

## 2) Core Agents

## 2.1 Product Owner Agent

- Owns scope decisions against PRD and milestones.
- Approves tradeoffs on dataset size, timeline, and feature cuts.
- Signs off on release readiness.

Inputs:
- PRD
- Milestone status
- Risks and blockers

Outputs:
- Prioritized backlog
- Scope decisions

## 2.2 Data Acquisition Agent

- Handles GDC metadata queries and manifest generation.
- Maintains GTEx download configuration.
- Enforces open-access-only acquisition mode.

Inputs:
- `configs/gdc_*.yml`, `configs/gtex_config.yml`
- Project whitelist (BRCA/LUAD/COAD for MVP)

Outputs:
- Bronze metadata files
- Manifest files
- Download audit logs

## 2.3 Harmonization Agent

- Normalizes metadata, sample entities, and gene identifiers.
- Builds stable silver schemas with type-safe columns.
- Tracks mapping failures and provenance.

Inputs:
- Bronze raw files + metadata
- Gene reference tables

Outputs:
- Silver parquet tables
- Mapping QA statistics

## 2.4 Analytics Warehouse Agent

- Builds gold marts for expression, mutation, and cohort summaries.
- Maintains dbt models and tests.
- Optimizes queryability in DuckDB (and portable SQL patterns).

Inputs:
- Silver tables
- dbt model contracts/tests

Outputs:
- Gold analytical tables
- dbt run + test reports

## 2.5 Data Quality Agent

- Executes quality checks (nulls, duplicates, ranges, whitelist, access level).
- Produces HTML/JSON quality reports.
- Fails fast on compliance-breaking conditions.

Inputs:
- Silver/gold outputs
- Guardrail thresholds

Outputs:
- `outputs/reports/data_quality_report.*`
- Check-level pass/warn/fail outcomes

## 2.6 Graph Modeling Agent

- Builds graph nodes and edges from gold tables.
- Produces Neo4j/Graphify-compatible CSV exports.
- Applies edge selection thresholds to avoid unusable graph density.

Inputs:
- Gold expression + mutation summaries

Outputs:
- Graph node/edge CSV files
- Graph schema version metadata

## 2.7 API Agent

- Implements FastAPI endpoints for metadata, expression, mutation, graph, and quality.
- Ensures endpoint contracts are stable and documented.

Inputs:
- Gold tables and graph exports

Outputs:
- API service
- API docs examples

## 2.8 Dashboard Agent

- Implements Streamlit pages for cohort, expression, tumor-vs-normal, mutation, graph, and quality.
- Adds user-visible caveats for batch effects and exploratory interpretation.

Inputs:
- Gold tables
- Graph exports

Outputs:
- Dashboard pages
- Screenshots for README

## 2.9 Documentation & Reproducibility Agent

- Maintains README, architecture, compliance, data dictionary, and outreach summary.
- Ensures setup commands are runnable and consistent.

Inputs:
- Actual code behavior
- Pipeline metadata

Outputs:
- Updated docs
- Reproducibility checklists

## 3) Operating Model

- Single source of truth: PRD + `WORKLOGS.md`.
- Every milestone starts with explicit acceptance criteria mapping.
- Every pipeline run writes run metadata and quality outputs.
- Every major change updates docs and changelog notes.

## 4) Handoff Rules

- Acquisition -> Harmonization only with manifest + source metadata + checksum context.
- Harmonization -> Warehouse only with schema contracts frozen for run.
- Warehouse -> Dashboard/API/Graph only when gold tests pass.
- Quality gate runs before publishing outputs or screenshots.

## 5) Definition of Done (Per Milestone)

- Required code implemented.
- Tests added or updated.
- Quality checks executed.
- Documentation updated.
- Compliance guardrails passed.
- Worklog entry completed.

## 6) Escalation Triggers

Escalate immediately to Product Owner when:

- Controlled-access data appears in pipeline inputs.
- Gene mapping rate drops below agreed threshold.
- Schema-breaking change affects downstream models.
- Dashboard/API latency violates MVP targets.
- Any PRD scope addition impacts timeline materially.

