# CancerOmicsLake

CancerOmicsLake is a reproducible bioinformatics data engineering project that integrates open-access TCGA cancer genomics data from the NCI Genomic Data Commons with GTEx normal tissue expression data. The project builds a lakehouse-style architecture with bronze, silver, and gold data layers, transforms raw biomedical files into research-ready analytical tables, and exports cancer-gene-tissue relationships into a knowledge graph for visualization through Graphify/Neo4j-style tools. The MVP focuses on TCGA-BRCA, TCGA-LUAD, and TCGA-COAD with matched GTEx normal tissues.

## Current Status

Implemented so far:

- Project structure and config system
- GDC metadata ingestion path (live with safe fallback)
- Bronze metadata and manifest generation
- GDC ingestion audit reporting (`outputs/reports/gdc_ingestion_audit.json`)
- Strict live-ingestion support (`tcga.require_live_gdc`)
- Silver parquet outputs for projects, patients, samples, file manifest, and expression tables
- Gold cohort summary mart
- Quality report generation
- FastAPI and Streamlit scaffolds
- Test suite for config, ingestion, silver, and gold builders

## Quickstart

```bash
make setup
make test
make run-metadata
make run-metadata-strict
make run-silver
make run-gold
```

## Compliance Notice

- Public mode is `open-access-only` by default.
- Do not commit raw downloaded data, restricted data, or credentials.
- This repository is for data engineering and exploratory analytics, not clinical claims.
