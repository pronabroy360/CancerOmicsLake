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
- Consequence-stratified mutation MAF parsing with downloaded-profile denominators
- Gold cohort, expression, tumor-vs-normal, mutation, candidate-priority, evidence-confidence, and graph marts
- Quality report generation
- Graphify and Neo4j CSV graph exports
- Public graph exports and graph API/dashboard views exclude Patient and Sample identifiers by default
- Graph node-degree metrics and graph metrics report
- FastAPI endpoints and Streamlit dashboard pages backed by local marts
- Test suite for config, ingestion, parsing, silver/gold builders, graph exports, API, dashboard data, reporting, and quality checks
- Daily CI schedule + dbt run/test gate on Python 3.11
- Local dbt runner with automatic Docker fallback when Python 3.14 is incompatible
- Medium-cap real ingestion profile (`expression<=25`, `mutations<=10` per project)
- Pipeline run-mode tagging (`manual`/`push`/`scheduled`) and run history tracking
- Project completion report for milestone-level release readiness (`outputs/reports/project_completion_report.json`)
- Reproducible DuckDB research benchmark with dataset inventory and median/p95 latency reporting

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
make run-graph-metrics
make run-recount3-expression
make run-external-validation
make run-expression-statistics
make run-paired-expression
make run-consensus-candidates
make run-pathway-enrichment
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

Live GTEx V8 normal-reference build:

```bash
make run-gtex-live
make run-gold
make run-quality
make run-graph-export
```

This verifies official object size/MD5 metadata, validates sample-to-tissue assignments against the open
sample annotation file, strips Ensembl version suffixes, and atomically writes the silver Parquet.

Research surface:

- API: `GET /research/candidate-genes?cancer_type=TCGA-BRCA&tier=high&limit=20`
- Dashboard: `Candidate Gene Priority` page for filtering and exporting ranked candidate cancer-gene pairs.
- API: `GET /research/evidence-confidence?cancer_type=TCGA-BRCA&confidence_tier=moderate&limit=20`
- Dashboard: `Evidence Confidence` page separating sample support, graph structure, integrity, provenance, and raw-versus-sensitivity direction concordance.
- API: `GET /research/batch-effect-sensitivity?cancer_type=TCGA-BRCA&support_tier=high&direction=rank_up&limit=20`
- Dashboard: `Batch-Effect Sensitivity` page for rank/robust-z TCGA-GTEx sensitivity review.
- API: `GET /research/reference-triangulation?cancer_type=TCGA-BRCA&concordance=concordant_up&limit=20`
- Dashboard: `Reference Triangulation` page comparing TCGA-adjacent and GTEx-normal reference directions.
- Expand the TCGA adjacent-normal bridge cohort with `make run-download-tcga-normals`.
- API: `GET /research/bootstrap-stability?cancer_type=TCGA-BRCA&stability_tier=high&limit=20`
- Dashboard: `Bootstrap Stability` page for deterministic candidate rank and direction resampling results.
- Run the 200-iteration candidate experiment with `make run-bootstrap-stability`.
- API: `GET /research/external-expression-validation?cancer_type=TCGA-BRCA&validation_tier=high&limit=20`
- Dashboard: `External Validation` page comparing native effects with an optional recount3 extract.
- Run the recount3 validation contract with `make run-external-validation` after exporting `data/silver/silver_expression_recount3.parquet`.
- API: `GET /research/consensus-candidates?cancer_type=TCGA-BRCA&decision=prioritized&limit=20`
- API: `GET /research/expression-statistical-support?cancer_type=TCGA-BRCA&support_tier=replicated_fdr&max_fdr=0.05&limit=20`
- API: `GET /research/paired-expression-support?cancer_type=TCGA-BRCA&support_tier=paired_replicated&max_fdr=0.05&limit=20`
- API: `GET /research/pathway-enrichment?cancer_type=TCGA-BRCA&candidate_set=prioritized&max_fdr=0.05&limit=20`
- Build sample-level association support with `make run-expression-statistics`, then rebuild publication triage with `make run-consensus-candidates`.
- Build matched cases with `make run-metadata-strict`, `make run-download-tcga-paired`, `make run-silver`, and `make run-paired-expression`.
- Build pathway hypotheses with `make run-pathway-enrichment`. The first run fetches pinned Reactome release 97 into `data/bronze/reference/pathways/reactome_pathways.gmt` via `make fetch-reactome-gmt` (idempotent; set `SKIP_GMT_FETCH=1` to opt out in CI).
- Rebuild graph tables with `make run-gold`, then export Reactome `Pathway` nodes plus `MEMBER_OF_PATHWAY` and capped `ENRICHED_IN_CANCER` relationships with `make run-graph-export`.
- Build independently with `make run-evidence-confidence`; `make run-graph-export` also refreshes the confidence mart.

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
- Download and flow targets use bounded parallel workers (`8` for aggressive, `4` for medium) while preserving checksum skip/retry behavior.
- The expanded local profile now produces 37.0 million TCGA expression rows, including paired primary-tumor coverage
  and 60 BRCA, 59 LUAD, and 41 COAD adjacent-normal samples, plus 45,588 mutation records.
- Mutation candidate evidence excludes synonymous and non-coding/regulatory events. Frequencies use the downloaded
  mutation-profile cohort as their denominator; they do not classify drivers or pathogenic variants. See
  [`docs/mutation_semantics.md`](docs/mutation_semantics.md).

## GTEx V8 Live Profile

- Four official tissue-specific TPM GCT files plus open sample annotations.
- Breast mammary, lung, transverse colon, and sigmoid colon.
- Deterministic cap of 50 samples per tissue.
- Approximately 178 MB downloaded and 11.24 million harmonized rows in a 92 MB silver Parquet.
- Raw GTEx files and generated Parquet remain excluded from Git.
- This resolves normal-reference coverage, but does not correct TCGA-GTEx batch effects.

## recount3 External Validation Profile

- Run `make run-recount3-expression` to build a uniformly processed TCGA/GTEx validation extract from the public
  recount3 S3 release, then run `make run-external-validation`.
- The extractor uses TCGA BRCA/LUAD/COAD and GTEx breast/lung/colon, with a deterministic 30-sample cap per cohort.
- It applies recount3's documented 40-million-read AUC scaling and records source URLs, hashes, sample counts, and
  normalization provenance.
- Current output: 11,494,080 expression rows from 180 samples and 108,012 validated gene-cancer comparisons.
- Current validation tiers: 84,531 high, 12,056 moderate, 9,610 limited, and 1,815 discordant.
- Uniform processing improves computational comparability but does not eliminate biological or collection confounding.

## Consensus Candidate Profile

- Run `make run-expression-statistics` after native and recount3 silver expression are available.
- Run `make run-consensus-candidates` after evidence confidence, bootstrap stability, external validation, expression statistics, and paired expression support.
- Output: `data/gold/gold_consensus_candidate_genes.parquet` plus `outputs/reports/consensus_candidate_report.json`.
- The score combines candidate priority, evidence confidence, adjacent-normal triangulation, bootstrap stability, recount3 validation, replicated statistical support, and mutation support.
- Discordant external validation, reference sensitivity, weak bootstrap support, or weak evidence confidence explicitly deprioritizes a gene.
- Statistical support uses Mann-Whitney effect sizes and cancer-wise Benjamini-Hochberg FDR, but source and disease status remain confounded.
- This is a publication-triage layer, not a batch-corrected differential-expression result or clinical biomarker claim.

## Matched TCGA Tumor-Normal Profile

- `make run-metadata-strict` enumerates open-access primary-tumor STAR files independently of capped acquisition.
- `make run-download-tcga-paired` selects primary tumors only for cases represented by downloaded adjacent normals.
- `make run-paired-expression` applies case-level Wilcoxon signed-rank tests, paired rank-biserial effects, and cancer-wise Benjamini-Hochberg FDR.
- The paired mart classifies `paired_replicated`, `paired_internal_fdr`, `limited`, and `paired_discordant` evidence against recount3 direction.
- Pairing reduces cross-source confounding, but adjacent-normal field effects and residual biological confounding remain.

## Pathway Enrichment Profile

- `make run-pathway-enrichment` performs hypergeometric over-representation analysis over consensus candidate sets.
- Default input path: `data/bronze/reference/pathways/reactome_pathways.gmt`.
- The release-97 GMT is fetched automatically by `make fetch-reactome-gmt` (idempotent; skip with `SKIP_GMT_FETCH=1`, force refresh with `REFRESH_GMT=1`). Acquisition provenance and checksums are written to `outputs/reports/reactome_gmt_acquisition_report.json`.
- Outputs: `data/gold/gold_pathway_enrichment.parquet` and `outputs/reports/pathway_enrichment_report.json`.
- This layer supports biological hypothesis generation only; it does not prove mechanism, causality, or clinical actionability.
- Graph projection retains at most 50 FDR-enriched pathways per cancer and deterministically collapses duplicate candidate-set evidence.

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
- Which high-priority cancer-gene candidates are supported by sufficiently reliable and traceable evidence?

See `docs/sample_queries.md` and `outputs/sample_queries/` for reviewer-friendly SQL examples.
The confidence model and pre-publication validation plan are documented in `docs/evidence_confidence_methodology.md`.

## FAIR Derived-Data Release

Run `make build-fair-release RELEASE_VERSION=0.1.0` to create a versioned, checksummed bundle in
`outputs/releases/v0.1.0/`. The strict release gate packages only aggregate research marts, rebuilds
the graph through the public node policy, and fails on individual-level identifier columns or values.
See [`docs/fair_release.md`](docs/fair_release.md) for verification and DOI-deposit steps.

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
