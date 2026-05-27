# CancerOmicsLake

CancerOmicsLake is a reproducible bioinformatics data engineering project that integrates open-access TCGA cancer genomics data from the NCI Genomic Data Commons with GTEx normal tissue expression data. The project builds a lakehouse-style architecture with bronze, silver, and gold data layers, transforms raw biomedical files into research-ready analytical tables, and exports cancer-gene-tissue relationships into a knowledge graph for visualization through Graphify/Neo4j-style tools. The MVP focuses on TCGA-BRCA, TCGA-LUAD, and TCGA-COAD with matched GTEx normal tissues.

## Current Status

Milestone 1 is scaffolded:

- Project structure
- YAML config system
- Metadata-only ingestion skeleton
- Quality report skeleton
- FastAPI and Streamlit stubs
- dbt project scaffold
- Tests for core utility logic

## Quickstart

```bash
make setup
make test
make run-metadata
```

## Compliance Notice

- Public mode is `open-access-only` by default.
- Do not commit raw downloaded data, restricted data, or credentials.
- This repository is for data engineering and exploratory analytics, not clinical claims.

