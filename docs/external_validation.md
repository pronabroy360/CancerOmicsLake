# External Expression Validation

## Purpose

`gold_external_expression_validation` is the next publication-readiness layer for CancerOmicsLake. It compares
native TCGA/GTEx tumor-vs-normal effects against an external uniformly processed expression source, starting with
recount3.

This answers a stricter question than the current batch-sensitivity and bootstrap layers:

> Do prioritized cancer-gene expression directions replicate when TCGA and GTEx are re-read from a uniformly
> processed resource?

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

If no recount3 extract exists, the command writes an empty schema-valid table and a skipped report. This keeps CI and
the main demo path deterministic while preserving the validation contract.

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
- `validation_score`
- `validation_tier`: `high`, `moderate`, `limited`, or `discordant`

## Interpretation

Use this layer as an external reproducibility filter before making biological claims. A strong candidate should ideally
show:

- high evidence confidence,
- high bootstrap stability,
- stable TCGA-adjacent versus GTEx reference triangulation,
- concordant external recount3 validation.

This still does not establish clinical validity. It only reduces one major reproducibility risk: dependence on one
expression processing path.
