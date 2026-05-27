# CancerOmicsLake PRD

Version: `0.1`
Status: `Draft`
Last updated: `2026-05-27`
Default mode: `open-access-only`

## 1. Project Summary

## 1.1 Project Name

**CancerOmicsLake: A Scalable TCGA-GTEx Data Lakehouse and Knowledge Graph for Pan-Cancer Bioinformatics**

## 1.2 One-Line Description

CancerOmicsLake is a reproducible biomedical data engineering platform that integrates open-access TCGA cancer genomics data with GTEx normal tissue expression data, transforms them into a research-ready lakehouse and graph model, and visualizes cancer-gene-tissue relationships through Graphify/Neo4j-style graph exploration.

## 1.3 Project Goal

Build a strong, PhD-profile-ready bioinformatics data engineering project using famous, large, public biomedical datasets. The project should demonstrate the ability to ingest, model, validate, query, and visualize large cancer genomics datasets using modern data engineering practices.

## 1.4 Why This Project Is Strong

This project combines:

- Data engineering
- Bioinformatics
- Cancer genomics
- Healthcare data mining
- Knowledge graphs
- Large public biomedical datasets
- Visualization and reproducible research infrastructure

TCGA is one of the best-known cancer genomics datasets and molecularly characterized more than 20,000 primary cancer and matched normal samples across 33 cancer types. GTEx is a major reference dataset for normal tissue expression, with open-access expression resources and controlled-access sensitive data.

Sources from original PRD:

- TCGA: https://www.genome.gov/Funded-Programs-Projects/Cancer-Genome-Atlas
- GDC: https://gdc.cancer.gov/access-data/data-access-processes-and-tools
- GDC manifest docs: https://docs.gdc.cancer.gov/Encyclopedia/pages/Manifest_File/
- GDC transfer docs: https://docs.gdc.cancer.gov/Data_Transfer_Tool/Users_Guide/Data_Download_and_Upload/
- GTEx Portal: https://gtexportal.org/home/
- GTEx FAQ: https://gtexportal.org/home/faq
- NIH Common Fund GTEx: https://commonfund.nih.gov/GTEx

## 2. Target Audience

Primary audiences:

- US PhD professors and labs working in biomedical informatics, healthcare data mining, bioinformatics data infrastructure, cancer data science, clinical genomics, computational biology, and biomedical knowledge graphs.
- Resume reviewers looking for evidence of large-scale data engineering, public biomedical dataset experience, SQL/data warehouse design, ETL/ELT pipelines, data quality validation, graph analytics, and reproducible research infrastructure.
- Future collaborators who may reuse schemas, SQL models, ingestion scripts, graph schema, dashboard templates, and documentation.

## 3. Dataset Availability and Access Policy

## 3.1 TCGA / GDC

TCGA data is accessed through the NCI Genomic Data Commons (GDC), which provides a portal, API, command-line tools, and manifest-based download workflow.

Public version rule:

- Use only open-access GDC/TCGA data.
- Avoid controlled-access data unless a future private workflow explicitly supports dbGaP authorization.
- Authentication tokens must not be required in public mode.
- Any file marked controlled/restricted must be blocked by default.

## 3.2 GTEx

GTEx open-access expression and metadata files are available through GTEx public resources. Sensitive genotype-level or restricted files are out of scope for the public version.

Public version rule:

- Use open-access expression and metadata resources only.
- Record GTEx version and source file metadata.
- Do not publish sensitive donor-level data.

## 3.3 Public GitHub Safety Rule

The repository may publish:

- Code
- Documentation
- Schema diagrams
- Pipeline configs
- SQL/dbt models
- Data dictionary
- Sample synthetic files
- Aggregated results
- Dashboard screenshots
- Graph schema

The repository must not publish:

- Controlled-access data
- Raw restricted sequencing data
- Individual-level sensitive donor/patient details
- Tokens, credentials, or private manifests
- Any file requiring dbGaP-controlled access

## 4. Problem Statement

Cancer genomics datasets are large, fragmented, multi-modal, and difficult to explore without strong data infrastructure. TCGA and GTEx are famous and public, but effective use requires:

- Metadata harmonization
- Sample and patient entity modeling
- Gene identifier standardization
- Expression and mutation processing
- Cross-dataset mapping
- Data quality checks
- Efficient analytical tables
- Visual graph exploration

CancerOmicsLake solves this by converting raw public biomedical files into clean, queryable, graph-ready research datasets.

## 5. Product Goals

## 5.1 Primary Goals

The system must:

1. Ingest selected TCGA open-access cancer data from GDC.
2. Ingest selected GTEx open-access normal tissue expression data.
3. Store raw files and metadata in a reproducible lakehouse structure.
4. Transform raw data into cleaned analytical tables.
5. Build gold-layer marts for cancer-gene-tissue analysis.
6. Create a biomedical knowledge graph.
7. Provide dashboards and graph visualizations.
8. Generate data quality reports.
9. Provide strong documentation suitable for professor outreach.

## 5.2 Secondary Goals

The system should:

1. Support easy addition of new cancer types.
2. Support easy addition of new omics modalities later.
3. Support reproducible local execution through Docker.
4. Provide SQL query templates for researchers.
5. Provide resume-ready screenshots and architecture diagrams.
6. Provide API endpoints for querying genes, cancers, and samples.

## 6. Non-Goals

The project is not trying to:

1. Develop a clinically validated biomarker discovery pipeline.
2. Make medical claims.
3. Predict patient outcomes for clinical use.
4. Publish controlled-access data.
5. Download the full TCGA dataset.
6. Replace official TCGA/GDC/GTEx portals.
7. Guarantee biological discovery without batch-effect-aware analysis.

This is primarily a data engineering and visualization project, not a clinical diagnostic system.

## 7. MVP Scope

## 7.1 MVP TCGA Cancer Types

| TCGA Project | Cancer Type |
|---|---|
| `TCGA-BRCA` | Breast invasive carcinoma |
| `TCGA-LUAD` | Lung adenocarcinoma |
| `TCGA-COAD` | Colon adenocarcinoma |

## 7.2 MVP GTEx Tissues

| TCGA Cancer | GTEx Normal Reference Tissue |
|---|---|
| `BRCA` | Breast - Mammary Tissue |
| `LUAD` | Lung |
| `COAD` | Colon - Transverse / Colon - Sigmoid |

## 7.3 MVP Data Modalities

Use:

1. TCGA clinical metadata
2. TCGA biospecimen/sample metadata
3. TCGA RNA-seq gene expression quantification
4. TCGA open-access somatic mutation MAF data, if available for selected cohorts
5. GTEx gene expression matrix
6. Gene annotation table
7. Optional pathway annotation from public gene sets later

## 7.4 MVP Deliverables

The MVP must produce:

1. Data ingestion scripts
2. Bronze/silver/gold lakehouse folders
3. Clean relational schema
4. DuckDB/PostgreSQL analytical warehouse
5. dbt models
6. Data quality report
7. Knowledge graph export
8. Graphify/Neo4j-compatible graph files
9. Streamlit dashboard
10. Technical README
11. Architecture diagram
12. Resume bullet section
13. Professor outreach project summary

## 8. Suggested Tech Stack

| Layer | Recommended Tool |
|---|---|
| Language | Python |
| Dataframe engine | Polars or Pandas |
| Storage format | Parquet |
| Local analytical DB | DuckDB |
| Transformations | dbt Core |
| Orchestration | Prefect or Dagster |
| Data quality | Great Expectations or Soda |
| Graph database/export | Neo4j, Graphify, Graphistry, or NetworkX |
| Dashboard | Streamlit |
| API | FastAPI |
| Containerization | Docker + Docker Compose |
| Documentation | Markdown + Mermaid diagrams |
| Testing | Pytest |

Recommended default:

- Python + Polars
- DuckDB
- dbt Core
- Prefect
- Great Expectations or equivalent validation
- Neo4j/Graphify exports
- Streamlit
- Docker Compose

## 9. High-Level Architecture

```text
Public Biomedical Sources
  - NCI GDC / TCGA
  - GTEx Portal
  - Gene Annotation Sources
        |
        v
Ingestion Layer
  - GDC API query
  - Manifest generation
  - GTEx download config
  - Metadata capture
        |
        v
Bronze Layer
  - Raw metadata
  - Raw expression files
  - Raw mutation files
        |
        v
Silver Layer
  - Cleaned patients
  - Cleaned samples
  - Cleaned genes
  - Cleaned expression
  - Cleaned mutations
        |
        v
Gold Analytics Layer
  - Cancer summaries
  - Tumor-vs-normal comparison
  - Mutation frequency marts
        |
        +--> SQL Dashboard / API (Streamlit + DuckDB + FastAPI)
        |
        +--> Biomedical Graph Layer (Graphify / Neo4j export)
```

## 10. Repository Structure

```text
canceromicslake/
  README.md
  LICENSE
  .gitignore
  docker-compose.yml
  pyproject.toml
  requirements.txt
  Makefile
  AGENTS.md
  GUARDRAILS.md
  WORKLOGS.md
  PRD.md

  configs/
    project_config.yml
    gdc_tcga_brca.yml
    gdc_tcga_luad.yml
    gdc_tcga_coad.yml
    gtex_config.yml
    graph_config.yml

  data/
    README.md
    bronze/
    silver/
    gold/

  src/
    ingestion/
    processing/
    quality/
    graph/
    analytics/
    api/

  dbt/
    dbt_project.yml
    models/
    tests/

  dashboard/
    app.py
    pages/
    assets/

  notebooks/
  tests/
  docs/
  outputs/
```

## 11. Functional Requirements

## FR-1: Dataset Configuration

The system must allow dataset scope through YAML configs.

Acceptance criteria:

- User can change cancer projects without modifying code.
- User can add/remove GTEx tissues from config.
- Pipeline reads configuration from YAML.
- Invalid config produces clear error messages.

Example:

```yaml
project:
  name: CancerOmicsLake
  version: 1.0

tcga:
  projects:
    - TCGA-BRCA
    - TCGA-LUAD
    - TCGA-COAD
  data_categories:
    - Transcriptome Profiling
    - Simple Nucleotide Variation
    - Clinical
    - Biospecimen
  access:
    type: open

gtex:
  version: v8
  tissues:
    - Breast - Mammary Tissue
    - Lung
    - Colon - Transverse
    - Colon - Sigmoid

storage:
  format: parquet
  database: duckdb
```

## FR-2: TCGA Metadata Ingestion

Required fields:

- `project_id`
- `case_id`
- `submitter_id`
- `sample_id`
- `sample_type`
- `primary_site`
- `disease_type`
- `file_id`
- `file_name`
- `data_category`
- `data_type`
- `experimental_strategy`
- `workflow_type`
- `access`
- `file_size`
- `md5sum`

Acceptance criteria:

- Metadata saved in `data/bronze/tcga/metadata/`.
- Only open-access files selected in public mode.
- Manifest files generated for selected files.
- Metadata can trace source files.

## FR-3: TCGA File Download

The system must support:

- Metadata-only mode
- Data download mode

Acceptance criteria:

- Supports GDC manifest-based downloads.
- Stores downloaded files in cancer-project-specific folders.
- Verifies checksums when available.
- Logs failed downloads.
- Supports resume/retry behavior.
- Public mode does not require controlled-access token.

## FR-4: GTEx Data Ingestion

Required fields:

- `gtex_sample_id`
- `donor_id`, if available in open-access form
- `tissue_site`
- `tissue_detail`
- `gene_id`
- `gene_symbol`
- `expression_value`
- `expression_unit`
- `source_version`

Acceptance criteria:

- GTEx files stored in `data/bronze/gtex/`.
- Only selected tissues loaded into silver layer.
- GTEx expression values normalize to same gene table as TCGA.
- GTEx version recorded in metadata.

## FR-5: Reference Gene Annotation

Required columns:

| Column | Description |
|---|---|
| `gene_id` | Ensembl gene ID |
| `gene_symbol` | HGNC-style gene symbol |
| `gene_name` | Full gene name, if available |
| `chromosome` | Chromosome |
| `start_position` | Start coordinate, optional |
| `end_position` | End coordinate, optional |
| `gene_type` | Protein coding, lncRNA, etc. |
| `source` | Reference source |
| `source_version` | Version/date |

Acceptance criteria:

- TCGA and GTEx expression tables map to same `gene_id`.
- Versioned reference table is created.
- Missing gene symbols are flagged.

## FR-6: Bronze Layer

Requirements:

- Preserve original file names.
- Preserve source metadata.
- Do not modify raw files.
- Store ingestion timestamp.
- Store source URL or source system reference.
- Store file checksum when available.

Acceptance criteria:

- Raw files trace back from silver/gold records.
- Every raw file has corresponding metadata.
- No controlled-access files stored in public repo.

## FR-7: Silver Layer

Required silver tables:

- `silver_patients`
- `silver_samples`
- `silver_projects`
- `silver_genes`
- `silver_expression_tcga`
- `silver_expression_gtex`
- `silver_mutations`
- `silver_clinical`
- `silver_file_manifest`
- `silver_data_quality_events`

Acceptance criteria:

- All silver tables written as Parquet.
- All silver tables have stable schemas.
- Date/time fields standardized.
- Missing values represented consistently.
- Duplicate records detected and reported.

## FR-8: Gold Layer

Required gold tables:

- `gold_cohort_summary`
- `gold_gene_expression_by_cancer`
- `gold_gene_expression_by_tissue`
- `gold_tumor_vs_normal_expression`
- `gold_mutation_frequency_by_gene`
- `gold_mutation_frequency_by_cancer`
- `gold_cancer_gene_edges`
- `gold_graph_nodes`
- `gold_graph_edges`

Acceptance criteria:

- Gold tables queryable from DuckDB.
- Gold tables power dashboard pages directly.
- Gold tables contain only analysis-ready fields.
- Each gold table has a data dictionary entry.

## 12. Data Warehouse Schema

## 12.1 `dim_project`

| Column | Type | Description |
|---|---|---|
| `project_key` | string | Internal key |
| `project_id` | string | TCGA project ID |
| `project_name` | string | Full project name |
| `cancer_abbreviation` | string | BRCA, LUAD, COAD |
| `primary_site` | string | Primary anatomical site |
| `source` | string | TCGA/GDC |

## 12.2 `dim_patient`

| Column | Type | Description |
|---|---|---|
| `patient_key` | string | Internal patient key |
| `case_id` | string | GDC case ID |
| `submitter_id` | string | TCGA submitter ID |
| `project_key` | string | FK to project |
| `gender` | string | If available |
| `race` | string | If available and open |
| `ethnicity` | string | If available and open |
| `vital_status` | string | Alive/deceased/unknown |
| `days_to_death` | integer | If available |
| `days_to_last_follow_up` | integer | If available |

Sensitive demographic details should be handled carefully and displayed only in aggregate form.

## 12.3 `dim_sample`

| Column | Type | Description |
|---|---|---|
| `sample_key` | string | Internal sample key |
| `sample_id` | string | Source sample ID |
| `patient_key` | string | FK to patient |
| `project_key` | string | FK to project |
| `sample_type` | string | Tumor/normal/etc. |
| `tissue_type` | string | Tumor, normal, metastatic, etc. |
| `source` | string | TCGA or GTEx |
| `platform` | string | RNA-seq, WXS, etc. |
| `experimental_strategy` | string | RNA-Seq, WXS, etc. |

## 12.4 `dim_gene`

| Column | Type | Description |
|---|---|---|
| `gene_key` | string | Internal gene key |
| `gene_id` | string | Ensembl ID |
| `gene_symbol` | string | Gene symbol |
| `gene_name` | string | Full gene name |
| `chromosome` | string | Chromosome |
| `gene_type` | string | Protein coding, lncRNA, etc. |

## 12.5 `fact_expression`

| Column | Type | Description |
|---|---|---|
| `expression_key` | string | Internal key |
| `sample_key` | string | FK to sample |
| `gene_key` | string | FK to gene |
| `expression_value` | float | TPM/count/normalized value |
| `expression_unit` | string | TPM, FPKM, count, etc. |
| `log2_expression` | float | log2(value + 1) |
| `source` | string | TCGA or GTEx |
| `pipeline_workflow` | string | Source workflow type |
| `batch_id` | string | Optional |

## 12.6 `fact_mutation`

| Column | Type | Description |
|---|---|---|
| `mutation_key` | string | Internal key |
| `sample_key` | string | FK to sample |
| `gene_key` | string | FK to gene |
| `variant_classification` | string | Missense, nonsense, etc. |
| `variant_type` | string | SNP, DEL, INS, etc. |
| `chromosome` | string | Chromosome |
| `start_position` | integer | Genomic position |
| `end_position` | integer | Genomic position |
| `reference_allele` | string | Ref allele |
| `tumor_seq_allele` | string | Tumor allele |
| `source` | string | TCGA/GDC |

## 12.7 `fact_clinical`

| Column | Type | Description |
|---|---|---|
| `clinical_key` | string | Internal key |
| `patient_key` | string | FK to patient |
| `diagnosis_age` | integer | Age at diagnosis if available |
| `tumor_stage` | string | Stage |
| `tumor_grade` | string | Grade |
| `vital_status` | string | Survival status |
| `days_to_death` | integer | If available |
| `days_to_last_follow_up` | integer | If available |
| `source` | string | TCGA/GDC |

## 13. Data Transformation Rules

## 13.1 Gene ID Normalization

The system must:

- Strip Ensembl version suffixes when necessary.
- Map gene IDs to gene symbols.
- Preserve original gene IDs in audit columns.
- Flag genes that fail mapping.

Example:

```text
ENSG00000141510.17 -> ENSG00000141510
```

## 13.2 Expression Normalization

The system must:

- Store original expression value.
- Create `log2_expression = log2(expression_value + 1)`.
- Track expression unit.
- Avoid mixing incompatible units without labeling them.

## 13.3 Tumor vs Normal Comparison

For each gene and cancer type:

- `median_tcga_tumor_expression`
- `median_gtex_normal_expression`
- `mean_tcga_tumor_expression`
- `mean_gtex_normal_expression`
- `log2_fold_change`
- `sample_count_tumor`
- `sample_count_normal`

Important caveat:

TCGA and GTEx come from different projects and pipelines, so tumor-vs-normal comparisons may be affected by batch effects. The dashboard must clearly label this as exploratory engineering analysis, not a validated biological finding.

## 13.4 Mutation Frequency

For each cancer type and gene:

- `mutated_sample_count`
- `total_profiled_sample_count`
- `mutation_frequency`
- `top_variant_classification`

## 14. Knowledge Graph Requirements

## 14.1 Node Types

Required node types:

- `CancerType`
- `Gene`
- `Sample`
- `Patient`
- `Tissue`
- `Mutation`
- `Dataset`

## 14.2 Edge Types

| Edge | From | To | Meaning |
|---|---|---|---|
| `HAS_SAMPLE` | Patient | Sample | Patient has sample |
| `BELONGS_TO_CANCER` | Sample | CancerType | Sample belongs to cancer type |
| `MEASURED_IN_DATASET` | Sample | Dataset | Sample came from dataset |
| `EXPRESSES_GENE` | Sample | Gene | Sample has expression value |
| `MUTATED_IN` | Gene | Sample | Gene mutated in sample |
| `OVEREXPRESSED_IN` | Gene | CancerType | Gene overexpressed in cancer |
| `HAS_NORMAL_REFERENCE` | CancerType | Tissue | Cancer mapped to GTEx tissue |
| `EXPRESSED_IN_TISSUE` | Gene | Tissue | Gene expressed in normal tissue |
| `SIMILAR_TO` | CancerType | CancerType | Optional expression similarity |

## 14.3 Graph Export Formats

The system must export:

- CSV node files
- CSV edge files
- Graphify-compatible format if required
- Neo4j bulk import format
- Optional NetworkX pickle/GraphML

Example outputs:

```text
outputs/graph_exports/nodes_gene.csv
outputs/graph_exports/nodes_cancer_type.csv
outputs/graph_exports/nodes_sample.csv
outputs/graph_exports/edges_gene_overexpressed_in_cancer.csv
outputs/graph_exports/edges_gene_mutated_in_sample.csv
```

## 15. Dashboard Requirements

Dashboard name: **CancerOmicsLake Explorer**

Required pages:

1. Project Overview
2. Cohort Explorer
3. Gene Expression Explorer
4. Tumor vs Normal Explorer
5. Mutation Landscape
6. Knowledge Graph Explorer
7. Data Quality Report

Global dashboard requirements:

- Show data freshness timestamp.
- Show pipeline run status.
- Allow gene search for examples such as `TP53`, `BRCA1`, `EGFR`, `KRAS`, `PIK3CA`.
- Support cancer type and source dataset filters.
- Include cross-dataset batch-effect warning on tumor-vs-normal pages.
- Allow table export where appropriate.

## 16. API Requirements

Build a lightweight FastAPI service.

Required endpoints:

```text
GET /health
GET /metadata/projects
GET /metadata/samples?project_id=TCGA-BRCA
GET /genes/search?query=TP53
GET /expression/gene/{gene_symbol}
GET /expression/tumor-vs-normal/{gene_symbol}
GET /mutations/gene/{gene_symbol}
GET /mutations/cancer/{project_id}
GET /graph/nodes
GET /graph/edges
GET /quality/latest
```

Example response:

```json
{
  "query": "TP53",
  "results": [
    {
      "gene_id": "ENSG00000141510",
      "gene_symbol": "TP53",
      "gene_name": "tumor protein p53",
      "chromosome": "17"
    }
  ]
}
```

## 17. Data Quality Requirements

## 17.1 Required Checks

| Check | Rule |
|---|---|
| Null project IDs | Not allowed |
| Null gene IDs | Not allowed in expression facts |
| Duplicate sample IDs | Not allowed within same source |
| Expression values | Must be non-negative |
| Mutation positions | Must be valid integers |
| File checksum | Must match when checksum exists |
| Gene mapping rate | Must be reported |
| TCGA project whitelist | Only configured projects allowed |
| Access level | Controlled-access files blocked in public mode |

## 17.2 Quality Report Output

Generate:

```text
outputs/reports/data_quality_report.html
outputs/reports/data_quality_report.json
```

Example JSON:

```json
{
  "pipeline_run_id": "2026-05-27T10:00:00",
  "status": "passed_with_warnings",
  "checks": [
    {
      "check_name": "expression_values_non_negative",
      "status": "passed",
      "failed_rows": 0
    },
    {
      "check_name": "gene_mapping_rate",
      "status": "warning",
      "mapping_rate": 0.982
    }
  ]
}
```

## 18. Orchestration Requirements

Use Prefect or Dagster to define pipeline flows.

Required stages:

1. `load_config`
2. `query_gdc_metadata`
3. `generate_gdc_manifest`
4. `download_tcga_files`
5. `download_gtex_files`
6. `validate_raw_files`
7. `build_bronze_metadata`
8. `transform_tcga_expression`
9. `transform_gtex_expression`
10. `normalize_gene_ids`
11. `build_silver_tables`
12. `run_data_quality_checks`
13. `build_gold_tables`
14. `build_graph_nodes_edges`
15. `export_graph_files`
16. `update_duckdb`
17. `generate_quality_report`
18. `launch_dashboard`

Every run must record:

- `pipeline_run_id`
- `start_time`
- `end_time`
- `status`
- `config_hash`
- `input_file_count`
- `output_table_count`
- `error_count`
- `warning_count`

## 19. Performance Requirements

MVP local target on a 16 GB RAM machine:

| Task | Target |
|---|---|
| Metadata ingestion | < 10 minutes |
| Small cohort expression transform | < 30 minutes |
| DuckDB query on gold tables | < 5 seconds |
| Dashboard page load | < 10 seconds |
| Graph export for MVP | < 10 minutes |

Scaling target:

- Add more TCGA cancer types.
- Add more genes/samples.
- Re-run only failed stages.
- Process Parquet files incrementally.
- Switch DuckDB to PostgreSQL, BigQuery, or Snowflake later.

## 20. Security and Compliance Requirements

The system must:

1. Never commit downloaded raw data to GitHub.
2. Never commit authentication tokens.
3. Use `.gitignore` for `data/`, `.env`, and token files.
4. Run in open-access mode by default.
5. Block controlled-access files unless explicitly enabled.
6. Display a compliance notice in README.
7. Publish only aggregate/demo outputs.

`.gitignore` must include:

```text
data/
.env
*.token
*.pem
*.key
outputs/raw/
gdc-user-token*
```

## 21. Documentation Requirements

Required docs:

- `README.md`
- `docs/architecture.md`
- `docs/data_dictionary.md`
- `docs/graph_schema.md`
- `docs/api_spec.md`
- `docs/reproducibility.md`
- `docs/compliance.md`
- `docs/professor_outreach_summary.md`

README must include:

- Project overview
- Why TCGA + GTEx
- Architecture diagram
- Dataset access policy
- Quickstart
- Example dashboard screenshots
- Example graph visualization
- Public GitHub safety note
- Resume bullets

## 22. MVP Milestones

| Milestone | Name | Core Deliverable |
|---|---|---|
| M1 | Project Setup | Docker, configs, README, folder structure, logging |
| M2 | Metadata Ingestion | GDC query script, TCGA metadata, manifests, summary report |
| M3 | Expression Processing | TCGA/GTEx parsers, gene normalization, silver expression |
| M4 | Mutation Processing | MAF parser, mutation facts, mutation frequency marts |
| M5 | dbt Warehouse | dbt project, silver/gold models, tests, DuckDB integration |
| M6 | Data Quality Layer | Checks, HTML report, JSON report |
| M7 | Knowledge Graph | Nodes, edges, graph exports, graph schema docs |
| M8 | Dashboard | Streamlit pages for exploration and quality reporting |
| M9 | Final Packaging | README, diagrams, resume bullets, outreach summary, sample queries |

## 23. Example Analytical Questions

The system should answer:

1. Which genes are most overexpressed in TCGA-BRCA compared with GTEx breast tissue?
2. Which genes are commonly mutated in LUAD?
3. Which cancer types share similar highly expressed genes?
4. What is the sample count distribution across TCGA-BRCA, TCGA-LUAD, and TCGA-COAD?
5. What are the top 20 cancer-gene relationships in the graph?
6. Which genes are both overexpressed and frequently mutated in a cancer type?
7. How many source files were processed successfully?
8. What percentage of genes failed identifier mapping?

## 24. Example SQL Queries

Top overexpressed genes in BRCA:

```sql
SELECT
    gene_symbol,
    cancer_type,
    median_tumor_expression,
    median_normal_expression,
    log2_fold_change
FROM gold_tumor_vs_normal_expression
WHERE cancer_type = 'TCGA-BRCA'
ORDER BY log2_fold_change DESC
LIMIT 20;
```

Top mutated genes in LUAD:

```sql
SELECT
    gene_symbol,
    cancer_type,
    mutated_sample_count,
    total_profiled_sample_count,
    mutation_frequency
FROM gold_mutation_frequency_by_gene
WHERE cancer_type = 'TCGA-LUAD'
ORDER BY mutation_frequency DESC
LIMIT 20;
```

Cancer-gene graph edges:

```sql
SELECT
    source_node_id,
    target_node_id,
    edge_type,
    weight,
    evidence_source
FROM gold_graph_edges
WHERE edge_type IN ('OVEREXPRESSED_IN', 'MUTATED_IN_CANCER')
LIMIT 100;
```

## 25. Graph Query Examples

Top genes linked to BRCA:

```cypher
MATCH (g:Gene)-[r:OVEREXPRESSED_IN]->(c:CancerType {project_id: "TCGA-BRCA"})
RETURN g.gene_symbol, r.log2_fold_change
ORDER BY r.log2_fold_change DESC
LIMIT 20;
```

Mutated genes in LUAD:

```cypher
MATCH (g:Gene)-[r:MUTATED_IN_CANCER]->(c:CancerType {project_id: "TCGA-LUAD"})
RETURN g.gene_symbol, r.mutation_frequency
ORDER BY r.mutation_frequency DESC
LIMIT 20;
```

## 26. Risks and Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| TCGA/GTEx batch effects | Misleading biological interpretation | Label as exploratory; avoid clinical claims |
| Large files | Local storage issue | Start with 3 cancer types and selected files |
| Controlled-access confusion | Compliance risk | Open-access mode by default |
| Gene ID mismatch | Poor joins | Build robust gene normalization table |
| Download failures | Incomplete pipeline | Retry logs and checksum validation |
| Dashboard too slow | Poor demo experience | Use gold aggregate tables |
| Graph too dense | Hard to visualize | Limit graph to top N genes/edges |

## 27. Success Metrics

Technical targets:

| Metric | Target |
|---|---|
| TCGA projects processed | 3 in MVP |
| GTEx tissues processed | 3-4 in MVP |
| Data quality checks | 15+ |
| Gold analytical tables | 5+ |
| Graph node types | 5+ |
| Graph edge types | 7+ |
| Dashboard pages | 6+ |
| API endpoints | 8+ |
| Test coverage | 60%+ for core pipeline |

Profile/resume outcomes:

- Large public biomedical dataset handling
- Data lakehouse design
- SQL warehouse modeling
- Reproducible ETL
- Data validation
- Graph data modeling
- Biomedical visualization
- Research-oriented documentation

## 28. Resume Positioning

Data engineering focused:

> Built CancerOmicsLake, a TCGA-GTEx bioinformatics data lakehouse integrating open-access cancer genomics and normal tissue expression data; designed reproducible ingestion pipelines, Parquet-based bronze/silver/gold layers, DuckDB/dbt analytical marts, data quality checks, and graph-ready cancer-gene-tissue exports.

Biomedical informatics focused:

> Engineered a biomedical knowledge graph over TCGA and GTEx datasets to explore cancer-gene-tissue relationships, mutation frequency, and tumor-vs-normal expression patterns across BRCA, LUAD, and COAD cohorts.

PhD outreach focused:

> Developed a research-grade public biomedical data engineering platform using TCGA and GTEx, demonstrating scalable metadata harmonization, gene expression processing, mutation analytics, data quality validation, and graph-based visualization for cancer informatics.

## 29. README Opening Paragraph

> CancerOmicsLake is a reproducible bioinformatics data engineering project that integrates open-access TCGA cancer genomics data from the NCI Genomic Data Commons with GTEx normal tissue expression data. The project builds a lakehouse-style architecture with bronze, silver, and gold data layers, transforms raw biomedical files into research-ready analytical tables, and exports cancer-gene-tissue relationships into a knowledge graph for visualization through Graphify/Neo4j-style tools. The MVP focuses on TCGA-BRCA, TCGA-LUAD, and TCGA-COAD with matched GTEx normal tissues.

## 30. Implementation Build Prompt

```text
You are a senior data engineer and bioinformatics platform architect.

Build the project "CancerOmicsLake" according to this PRD.

The project must create a reproducible data engineering pipeline for open-access TCGA and GTEx data. The MVP should support TCGA-BRCA, TCGA-LUAD, TCGA-COAD, and selected GTEx normal tissues. Use Python, Polars, DuckDB, dbt Core, Prefect, Great Expectations or equivalent validation, Streamlit, and graph exports compatible with Graphify/Neo4j.

Do not include or commit raw downloaded biomedical data. Add .gitignore rules for data, tokens, credentials, and raw outputs. The default mode must be open-access only.

Implement project structure, YAML config, GDC metadata ingestion, manifest generation, GTEx configuration, bronze/silver/gold layers, expression and mutation parsers, gene ID normalization, DuckDB warehouse, dbt models, data quality checks, graph exports, FastAPI service, Streamlit dashboard, tests, and documentation.

Prioritize clean architecture, reproducibility, and strong documentation. Use small sample/synthetic files for tests. Make every major pipeline stage runnable independently through CLI commands and Makefile targets.
```

## 31. Final Project Positioning

This project should be positioned as:

> A Data Engineering for Bioinformatics project, not just a bioinformatics notebook.

Many applicants show ML notebooks. CancerOmicsLake should show the infrastructure layer that biomedical AI and data-mining labs need: ingestion, harmonization, validation, warehouse design, graph modeling, and visual exploration over large public biomedical datasets.

## 32. Codex Review: Missing Pieces and Suggested Improvements

## 32.1 What Is Already Strong

- The project has a clear identity: bioinformatics data engineering, not just analysis.
- The MVP scope is credible and focused around three familiar TCGA cohorts.
- The open-access-only policy is explicit, which is important for public GitHub safety.
- Bronze/silver/gold modeling, dbt, DuckDB, quality reports, API, dashboard, and graph exports give a complete platform story.
- The project is very well positioned for professor outreach because it demonstrates infrastructure, reproducibility, and biomedical domain awareness.

## 32.2 Important Missing Details

1. Exact source file selection is not yet pinned.
   - The PRD names TCGA and GTEx, but implementation needs exact GDC filters, workflow types, file formats, and GTEx file names/URLs.

2. Dataset size controls need to be explicit.
   - Add config limits such as `max_files_per_project`, `max_samples_per_project`, `gene_subset`, and `metadata_only` so local execution stays predictable.

3. The first runnable demo dataset is not specified.
   - Add tiny synthetic fixtures and possibly a public-safe mini sample so tests and dashboard can run before real downloads.

4. Schema versioning is not defined.
   - Add `schema_version` to table metadata, graph exports, and API responses where useful.

5. Data lineage should be more formal.
   - Add `source_file_id`, `source_file_name`, `source_md5`, `ingestion_run_id`, and `transform_run_id` to silver/gold audit columns where feasible.

6. API pagination and limits are missing.
   - Graph and expression endpoints can get large, so add `limit`, `offset`, and maximum response size policies.

7. Dashboard loading states and empty states are not specified.
   - Add expected behavior for missing data, failed runs, and metadata-only mode.

8. CI/CD is not specified.
   - Add GitHub Actions for linting, tests, docs checks, and secret scanning.

9. Biological interpretation boundaries should be repeated in UI/API/docs.
   - The batch-effect caveat is present, but the same language should appear in dashboard pages, README, and exported reports.

10. License choices are not defined.
    - Add a code license, likely MIT or Apache-2.0, plus a data-use disclaimer clarifying that source datasets remain governed by their original terms.

## 32.3 Suggested Improvements

1. Add a `demo_mode`.
   - A synthetic dataset mode will make `make demo` work without downloading large biomedical files.

2. Choose one validation layer for MVP.
   - Great Expectations is fine, but a lightweight custom validation layer plus JSON/HTML reports may be faster to ship. The PRD can still allow Great Expectations later.

3. Add explicit GDC query presets.
   - Example presets: `rna_seq_star_counts`, `masked_somatic_mutation_maf`, `clinical_supplement`, and `biospecimen_supplement`.

4. Add sample identity rules.
   - TCGA aliquot/sample/case relationships can get tricky. Define how `case_id`, `sample_id`, `portion`, `analyte`, and `file_id` roll up.

5. Add mutation denominator logic.
   - Mutation frequency requires a clear `total_profiled_sample_count`, preferably based on samples with mutation profiling available, not all cohort samples.

6. Add statistical fields carefully.
   - Include `median_diff`, `log2_fold_change`, `normal_sample_count`, `tumor_sample_count`, and optional `effect_size`, but avoid overclaiming p-values unless batch correction is addressed.

7. Add graph export contracts.
   - Define required columns for every node and edge file: `node_id`, `node_label`, `source`, `schema_version`, `edge_id`, `source_node_id`, `target_node_id`, `edge_type`, `weight`, `evidence_source`.

8. Add observability basics.
   - Standardize logs as JSON lines and add `outputs/reports/pipeline_run_summary.json`.

9. Add environment strategy.
   - Support `.env.example`, `configs/project_config.yml`, and documented environment variables for local paths, database path, and public/private mode.

10. Add professor-review pathway.
    - Include a three-minute README path: project summary, architecture diagram, one screenshot, one sample query, one graph example, and a clear "why this matters" section.

## 32.4 Recommended MVP Build Order

1. Scaffold repo, `.gitignore`, configs, Makefile, tests, and docs shell.
2. Implement config loading and validation.
3. Build synthetic demo fixtures.
4. Build GDC metadata-only ingestion and manifest generation.
5. Build DuckDB + Parquet silver/gold tables from demo data.
6. Add quality checks and reports.
7. Add graph exports.
8. Add API endpoints over DuckDB.
9. Add Streamlit dashboard over gold tables.
10. Add real-download mode after metadata-only path is stable.

