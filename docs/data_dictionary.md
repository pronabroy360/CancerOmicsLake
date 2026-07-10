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
- `donor_id`: donor identifier derived from the public GTEx sample identifier.
- `tissue_site`: GTEx tissue site.
- `tissue_detail`: GTEx tissue detail.
- `gene_id`: normalized Ensembl gene ID without version suffix.
- `gene_symbol`: parsed or mapped gene symbol.
- `expression_value`: expression value.
- `expression_unit`: expression unit, usually `TPM` for GTEx public expression matrices.
- `log2_expression`: `log2(expression_value + 1)`.
- `source_version`: GTEx version label.
- `data_origin`: exact open-access GTEx source GCT filepath, otherwise demo source.
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

### `gold_batch_effect_sensitivity.parquet`

- `cancer_type`: TCGA project ID.
- `gene_symbol`: gene symbol.
- `tumor_log2_median`: log2 median TCGA tumor TPM plus one.
- `normal_log2_median`: log2 median GTEx normal TPM plus one.
- `tumor_expression_percentile`: within-cancer percentile rank of tumor gene expression.
- `normal_expression_percentile`: within-reference percentile rank of normal gene expression.
- `percentile_delta`: tumor percentile minus normal percentile.
- `tumor_robust_z`: tumor gene-expression robust z-score within the cancer cohort.
- `normal_robust_z`: normal gene-expression robust z-score within the mapped GTEx reference.
- `robust_z_delta`: tumor robust z-score minus normal robust z-score.
- `sample_count_tumor`: contributing TCGA tumor samples.
- `sample_count_normal`: contributing GTEx normal samples.
- `support_tier`: `high`, `moderate`, or `limited` based on sample support.
- `sensitivity_direction`: `rank_up`, `rank_down`, or `stable`.
- `batch_method`: normalization method label.
- `batch_effect_caveat`: machine-readable warning that this is not full batch correction.

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
- `expression_confidence`: tumor/normal sample support adjusted by directional batch-sensitivity concordance, capped at `0.5`.
- `batch_sensitivity_confidence`: support-aware score from raw fold-change versus rank/robust-z direction agreement.
- `graph_confidence`: pair-edge presence and gene graph-degree support; this is structural evidence, not independent biological validation.
- `quality_confidence`: row-level integrity score for frequencies, denominators, and expression counts.
- `traceability_confidence`: fraction of contributing source rows with non-stub provenance.
- `biological_confidence`: available-modality confidence before structural and operational signals.
- `overall_confidence`: bounded composite confidence score from biological, graph, quality, and provenance components.
- `confidence_tier`: `high`, `moderate`, `limited`, or `low`.
- `raw_expression_direction`, `sensitivity_direction`: raw fold-change and scale-reduced direction labels.
- `sensitivity_support_tier`: sample-support tier inherited from the batch-sensitivity mart.
- `batch_concordance`: `concordant`, `inconclusive`, `discordant`, `unavailable`, or `not_applicable`.
- `percentile_delta`, `robust_z_delta`: sensitivity evidence used in the concordance decision.
- `batch_effect_risk`: `high` for discordant/unassessed expression, `elevated` otherwise, or `not_applicable`.
- `quality_status`, `traceability_status`: human-readable component outcomes.
- `caveat_summary`: semicolon-delimited machine-readable limitations for the pair.

### `gold_reference_triangulation.parquet`

- `cancer_type`, `gene_symbol`: cancer-gene pair.
- `median_tcga_tumor_expression`: TCGA primary-tumor median TPM.
- `median_tcga_normal_expression`: TCGA solid-tissue adjacent-normal median TPM.
- `median_gtex_normal_expression`: mapped GTEx healthy-tissue median TPM.
- `sample_count_tumor`, `sample_count_tcga_normal`, `sample_count_gtex_normal`: unique sample support.
- `log2_fc_tumor_vs_tcga_normal`, `log2_fc_tumor_vs_gtex`: tumor effect under each reference.
- `log2_fc_tcga_normal_vs_gtex`: normal-reference shift for audit, not a pure technical batch estimate.
- `reference_effect_delta`: absolute difference between the two tumor effect estimates.
- `tcga_reference_direction`, `gtex_reference_direction`: thresholded `up`, `down`, or `stable` directions.
- `reference_concordance`: concordant, reference-sensitive, or directionally discordant classification.
- `tcga_normal_support_tier`: `high`, `moderate`, or `limited` adjacent-normal support.
- `reference_stability_score`: bounded support, direction, and effect-similarity calibration.
- `triangulation_caveat`: required adjacent-normal and cross-study interpretation warning.

### `gold_candidate_bootstrap_stability.parquet`

- `cancer_type`, `gene_symbol`: candidate cancer-gene pair.
- `candidate_priority_rank`, `priority_score`: upstream candidate rank and score.
- `evidence_confidence_tier`, `candidate_selection_reason`: reason the candidate entered the bootstrap cohort.
- `bootstrap_iterations`, `top_k`, `random_seed`: reproducibility parameters.
- `tcga_direction_stability`, `gtex_direction_stability`: baseline-direction retention rates.
- `reference_concordance_rate`, `opposite_direction_rate`: cross-reference directional behavior.
- `tcga_top_k_selection_rate`, `gtex_top_k_selection_rate`: bootstrap top-k inclusion probabilities.
- `tcga_median_rank`, `gtex_median_rank`: median absolute-effect ranks.
- `tcga_rank_ci_low/high`, `gtex_rank_ci_low/high`: 95% percentile rank intervals.
- `tcga_median_log2_fc`, `gtex_median_log2_fc`: median bootstrap effects.
- `tcga_log2_fc_ci_low/high`, `gtex_log2_fc_ci_low/high`: 95% percentile effect intervals.
- `rank_precision`: normalized inverse rank-interval width.
- `bootstrap_stability_score`, `bootstrap_stability_tier`: transparent bounded stability calibration.
- `bootstrap_caveat`: required candidate-restricted and non-validation warning.

### `gold_external_expression_validation.parquet`

- `cancer_type`, `gene_symbol`: externally validated cancer-gene pair.
- `native_log2_fold_change`: native TCGA tumor versus GTEx normal effect from the project mart.
- `recount3_log2_fold_change`: effect recomputed from a normalized recount3 extract.
- `effect_delta`: absolute native-versus-recount3 effect difference.
- `native_direction`, `recount3_direction`: thresholded `up`, `down`, or `stable` directions.
- `direction_agreement`: `concordant`, `inconclusive`, or `discordant`.
- `native_abs_effect_rank`, `recount3_abs_effect_rank`: per-cancer absolute-effect ranks.
- `absolute_rank_delta`: absolute rank difference between native and recount3 effects.
- `top_k`, `top_k_overlap`, `top_k_jaccard_by_cancer`: top-k reproducibility metrics.
- `native_sample_count_tumor`, `native_sample_count_normal`: native support counts.
- `recount3_sample_count_tumor`, `recount3_sample_count_normal`: recount3 support counts.
- `validation_score`, `validation_tier`: bounded reproducibility calibration.
- `external_source`, `external_annotation`: external source provenance.
- `validation_caveat`: required external-validation interpretation warning.

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
