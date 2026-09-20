# recount3 Reprocessing Corroboration

## Purpose

`gold_external_expression_validation` is retained as a compatibility name. Scientifically, the mart compares native
TCGA/GTEx tumor-vs-normal effects against uniformly reprocessed recount3 views of the same source studies.

This answers a stricter question than the current batch-sensitivity and bootstrap layers:

> Are prioritized cancer-gene expression directions robust to a different processing pipeline over TCGA and GTEx?

This is reprocessing corroboration, not independent cohort validation. The pipeline audits exact normalized sample
identifiers and reports overlap for TCGA and GTEx separately. Even when exact sample overlap is absent, both analyses
still originate from the same source studies and cannot establish independent replication.

## Why recount3

recount3 is a uniformly processed public RNA-seq resource and provides gene, exon, and junction summaries for human
and mouse projects. Its documentation states that the R/Bioconductor package builds RangedSummarizedExperiment objects,
and that large studies such as TCGA and GTEx are fragmented at the tissue level for accessibility.

Primary references:

- recount3 portal: https://rna.recount.bio/
- Bioconductor documentation: https://rna.recount.bio/docs/bioconductor.html
- Quick start: https://research.libd.org/recount3/articles/recount3-quickstart.html
- Paper: https://pmc.ncbi.nlm.nih.gov/articles/PMC8628444/

## Input Contract

The Python validation mart expects a normalized recount3 extract at:

```text
data/silver/silver_expression_recount3.parquet
```

CSV is also accepted through the CLI argument.

Required columns:

| Column | Description |
| --- | --- |
| `source` | `TCGA` or `GTEx` |
| `project_id` | TCGA project ID for tumor rows, e.g. `TCGA-BRCA` |
| `sample_id` | recount3/sample identifier |
| `sample_type` | `Primary Tumor` for TCGA tumor rows |
| `tissue_site` | GTEx tissue name for normal rows |
| `gene_symbol` | Upper/lower case accepted; normalized to uppercase |
| `expression_value` | Non-negative normalized expression value used for validation |
| `external_annotation` | Source/version note, e.g. `recount3_monorail_gencode_vXX` |

## Live Extract

Build the normalized input directly from the public recount3 S3 release:

```bash
make run-recount3-expression
```

The extractor downloads and caches tissue-level gene-sum, metadata, and QC files for TCGA BRCA/LUAD/COAD and
GTEx breast/lung/colon. It deterministically selects 30 eligible samples per cohort, maps GENCODE v26 gene IDs,
and applies recount3's documented AUC scaling:

```text
scaled_count = raw_coverage_count * (40,000,000 / bc_auc.all_reads_all_bases)
```

The current real extract contains 11,494,080 rows from 180 samples. Source URLs, SHA-256 hashes, selected sample
counts, output size, and normalization provenance are recorded in
`outputs/reports/recount3_expression_report.json`. Cached source data and the generated Parquet are excluded from Git.

## Build Command

```bash
make run-external-validation
```

Equivalent CLI:

```bash
.venv/bin/python -m src.main run-external-validation \
  --config configs/project_config.yml \
  --recount3-expression-path data/silver/silver_expression_recount3.parquet \
  --top-k 100
```

If no recount3 extract exists, the validation command writes an empty schema-valid table and a skipped report. This
keeps CI and the main demo path deterministic; use `make run-recount3-expression` for the real local research run.

## Output Metrics

The mart compares native `gold_tumor_vs_normal_expression` with recount3-derived contrasts by cancer and gene.

Key fields:

- `native_log2_fold_change`
- `recount3_log2_fold_change`
- `effect_delta`
- `direction_agreement`: `concordant`, `inconclusive`, or `discordant`
- `native_abs_effect_rank`
- `recount3_abs_effect_rank`
- `absolute_rank_delta`
- `top_k_overlap`
- `top_k_jaccard_by_cancer`
- `validation_score` and `validation_tier`: legacy-compatible names for a bounded reprocessing-concordance calibration.
- `evidence_scope`: explicitly marks the evidence as same-study reprocessing corroboration.
- `sample_overlap_status`, TCGA/GTEx overlap counts, and recount3 sample counts: identifier-based overlap audit.

## Interpretation

Use this layer as a processing-sensitivity filter before making biological claims. A strong candidate should ideally
show:

- high evidence confidence,
- high bootstrap stability,
- stable TCGA-adjacent versus GTEx reference triangulation,
- concordant recount3 reprocessing evidence.

This does not establish independent replication or clinical validity. It only reduces one reproducibility risk:
dependence on one expression processing path.

Current real-data corroboration covers 108,012 gene-cancer pairs. It classifies 84,542 as high tier, 12,070 as moderate,
9,585 as limited, and 1,815 as discordant. These tiers are engineering reproducibility evidence, not biological or
clinical significance. Uniform recount3 processing reduces computational pipeline differences but does not remove
cohort composition, tissue collection, ischemic-time, tumor-purity, or other biological confounding.

The identifier audit found no exact native/recount3 TCGA sample overlap among the 30 recount3 tumors per cancer, but
found 29 of 30 recount3 GTEx samples overlapping the native GTEx reference for each cancer. Exact sample non-overlap
does not establish donor independence, and both sides still derive from TCGA and GTEx.
