# Data Dictionary

This dictionary documents the currently implemented lakehouse tables. Target future tables remain described in `PRD.md`.

## Silver Tables

### `silver_projects.parquet`

- `project_id`: TCGA project ID, for example `TCGA-BRCA`.
- `primary_site`: primary anatomical site.
- `disease_type`: GDC disease label.

### `silver_patients.parquet`

- `project_id`: TCGA project ID.
- `case_id`: GDC case UUID.
- `submitter_id`: TCGA submitter/case barcode when available.

### `silver_samples.parquet`

- `project_id`: TCGA project ID.
- `case_id`: GDC case UUID.
- `sample_id`: GDC sample UUID or submitter-derived sample ID.
- `sample_type`: GDC sample type, for example primary tumor or solid tissue normal.

### `silver_file_manifest.parquet`

- `project_id`: TCGA project ID.
- `case_id`: GDC case UUID.
- `sample_id`: sample UUID or submitter-derived sample ID.
- `file_id`: GDC file UUID.
- `file_name`: source file name.
- `data_category`: GDC data category.
- `data_type`: GDC data type.
- `experimental_strategy`: assay strategy.
- `workflow_type`: GDC workflow label.
- `access`: GDC access level, expected to be `open` in public mode.
- `file_size`: source file size in bytes when available.
- `md5sum`: source checksum when available.
- `ingested_at`: ingestion timestamp.

### `silver_expression_tcga.parquet`

- `project_id`: TCGA project ID.
- `case_id`: GDC case UUID.
- `sample_id`: TCGA/GDC sample identifier.
- `sample_type`: sample type.
- `gene_id`: normalized Ensembl gene ID without version suffix.
- `gene_symbol`: parsed or mapped gene symbol.
- `expression_value`: expression value in the recorded unit.
- `expression_unit`: unit such as `TPM`, `FPKM`, or `COUNT`.
- `log2_expression`: `log2(expression_value + 1)`.
- `pipeline_workflow`: GDC workflow or parser-inferred workflow.
- `data_origin`: source filepath when parsed from bronze expression files, otherwise demo source.
- `ingested_at`: processing timestamp.

### `silver_expression_gtex.parquet`

- `gtex_sample_id`: GTEx sample identifier.
- `tissue_site`: GTEx tissue site.
- `tissue_detail`: GTEx tissue detail.
- `gene_id`: normalized Ensembl gene ID without version suffix.
- `gene_symbol`: parsed or mapped gene symbol.
- `expression_value`: expression value.
- `expression_unit`: expression unit, usually `TPM` for GTEx public expression matrices.
- `log2_expression`: `log2(expression_value + 1)`.
- `source_version`: GTEx version label.
- `data_origin`: source filepath when parsed from bronze expression files, otherwise demo source.
- `ingested_at`: processing timestamp.

### `silver_mutations.parquet`

- `project_id`: TCGA project ID.
- `case_id`: GDC case UUID when available.
- `sample_id`: tumor sample identifier.
- `gene_id`: normalized Ensembl gene ID when available.
- `gene_symbol`: Hugo/gene symbol.
- `variant_classification`: MAF variant classification.
- `variant_type`: MAF variant type.
- `chromosome`: chromosome.
- `start_position`: variant start coordinate.
- `end_position`: variant end coordinate.
- `reference_allele`: reference allele.
- `tumor_seq_allele`: tumor allele.
- `source`: source system label.
- `data_origin`: source MAF filepath or demo source.
- `ingested_at`: processing timestamp.

## Gold Tables

### `gold_cohort_summary.parquet`

- `tcga_project_count`
- `tcga_patient_count`
- `tcga_sample_count`
- `tcga_file_count`
- `gtex_expression_sample_count`
- `tcga_expression_row_count`
- `gtex_expression_row_count`
- `gene_count`
- `mutation_record_count`
- `generated_at`

### `gold_gene_expression_by_cancer.parquet`

- `cancer_type`: TCGA project ID.
- `gene_id`: normalized Ensembl gene ID.
- `gene_symbol`: gene symbol.
- `mean_expression`: mean expression value.
- `median_expression`: median expression value.
- `mean_log2_expression`: mean log2 expression.
- `sample_count`: number of contributing samples.

### `gold_gene_expression_by_tissue.parquet`

- `tissue_site`: GTEx tissue site.
- `tissue_detail`: GTEx tissue detail.
- `gene_id`: normalized Ensembl gene ID.
- `gene_symbol`: gene symbol.
- `mean_expression`: mean expression value.
- `median_expression`: median expression value.
- `mean_log2_expression`: mean log2 expression.
- `sample_count`: number of contributing samples.

### `gold_tumor_vs_normal_expression.parquet`

- `cancer_type`: TCGA project ID.
- `normal_tissue`: mapped GTEx tissue.
- `gene_id`: normalized Ensembl gene ID.
- `gene_symbol`: gene symbol.
- `median_tumor_expression`
- `median_normal_expression`
- `mean_tumor_expression`
- `mean_normal_expression`
- `log2_fold_change`
- `sample_count_tumor`
- `sample_count_normal`

### `gold_mutation_frequency_by_gene.parquet`

- `cancer_type`: TCGA project ID.
- `gene_id`: normalized Ensembl gene ID when available.
- `gene_symbol`: gene symbol.
- `mutated_sample_count`
- `total_profiled_sample_count`
- `mutation_frequency`
- `top_variant_classification`

### `gold_mutation_frequency_by_cancer.parquet`

- `cancer_type`: TCGA project ID.
- `mutated_sample_count`
- `total_profiled_sample_count`
- `mutation_record_count`
- `mean_mutation_frequency`

### `gold_candidate_gene_priority.parquet`

- `cancer_type`: TCGA project ID.
- `gene_symbol`: gene symbol.
- `mutation_frequency`: fraction of profiled samples with mutation evidence for the gene.
- `mutated_sample_count`: number of mutated samples for the gene/cancer pair.
- `total_profiled_sample_count`: profiled sample denominator.
- `abs_log2_fold_change`: absolute tumor-vs-normal expression shift when available.
- `log2_fold_change`: signed exploratory tumor-vs-normal expression shift.
- `graph_degree`: count of available evidence families represented for the gene/cancer pair.
- `evidence_count`: count of evidence families contributing to the score.
- `priority_score`: weighted exploratory score combining mutation, expression shift, and evidence coverage.
- `priority_tier`: `high`, `medium`, or `low`.
- `evidence_summary`: compact score provenance string.

### `gold_cancer_gene_evidence_confidence.parquet`

- `cancer_type`, `gene_symbol`: cancer-gene pair.
- `priority_score`, `priority_tier`: candidate importance from the upstream prioritization mart.
- `mutation_confidence`: support calibration from profiled and mutated sample counts.
- `expression_confidence`: tumor/normal sample support with an explicit penalty for uncorrected TCGA-GTEx batch risk.
- `graph_confidence`: pair-edge presence and gene graph-degree support; this is structural evidence, not independent biological validation.
- `quality_confidence`: row-level integrity score for frequencies, denominators, and expression counts.
- `traceability_confidence`: fraction of contributing source rows with non-stub provenance.
- `biological_confidence`: available-modality confidence before structural and operational signals.
- `overall_confidence`: bounded composite confidence score from biological, graph, quality, and provenance components.
- `confidence_tier`: `high`, `moderate`, `limited`, or `low`.
- `batch_effect_risk`: `high` for cross-study expression comparisons, otherwise `not_applicable`.
- `quality_status`, `traceability_status`: human-readable component outcomes.
- `caveat_summary`: semicolon-delimited machine-readable limitations for the pair.

### `gold_graph_nodes.parquet`

- `node_id`: stable graph node identifier.
- `node_label`: node type, for example `CancerType`, `Gene`, `Sample`, `Patient`, `Tissue`, or `Dataset`.
- `name`: display name.
- `primary_site`: primary site where available.
- `source`: source system or mart.

### `gold_graph_edges.parquet`

- `edge_id`: stable graph edge identifier.
- `source_node_id`: source node ID.
- `target_node_id`: target node ID.
- `edge_type`: graph relationship type.
- `weight`: relationship score/count/frequency.
- `evidence_source`: source table or rule that produced the edge.

### `gold_graph_node_metrics.parquet`

- `node_id`: stable graph node identifier.
- `node_label`: node type.
- `name`: display name.
- `total_degree`: incoming plus outgoing graph degree.
- `in_degree`: incoming edge count.
- `out_degree`: outgoing edge count.
- `weighted_degree`: sum of incoming and outgoing edge weights.
- `edge_type_count`: number of directional edge-type families connected to the node.
- `degree_rank`: rank ordered by total degree and weighted degree.

## Quality And Caveats

- Expression units are preserved and checked for workflow/unit compatibility.
- Gene IDs are normalized by stripping Ensembl version suffixes.
- Open-access enforcement is validated before public-mode downloads.
- Tumor-vs-normal tables are exploratory and should not be interpreted as clinical findings.
