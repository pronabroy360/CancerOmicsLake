# API Spec

FastAPI application entrypoint: `src/api/main.py`

Implemented endpoints:

- `GET /health`
- `GET /metadata/projects`
- `GET /metadata/samples?project_id=TCGA-BRCA`
- `GET /genes/search?query=TP53`
- `GET /expression/gene/{gene_symbol}`
- `GET /expression/tumor-vs-normal/{gene_symbol}`
- `GET /mutations/gene/{gene_symbol}`
- `GET /mutations/cancer/{project_id}`
- `GET /research/candidate-genes?cancer_type=TCGA-BRCA&tier=high&limit=20`
- `GET /research/evidence-confidence?cancer_type=TCGA-BRCA&confidence_tier=moderate&limit=20`
- `GET /research/batch-effect-sensitivity?cancer_type=TCGA-BRCA&support_tier=high&direction=rank_up&limit=20`
- `GET /research/reference-triangulation?cancer_type=TCGA-BRCA&concordance=concordant_up&limit=20`
- `GET /research/bootstrap-stability?cancer_type=TCGA-BRCA&stability_tier=high&limit=20`
- `GET /research/external-expression-validation?cancer_type=TCGA-BRCA&validation_tier=high&limit=20`
- `GET /research/consensus-candidates?cancer_type=TCGA-BRCA&decision=prioritized&limit=20`
- `GET /research/expression-statistical-support?cancer_type=TCGA-BRCA&support_tier=replicated_fdr&max_fdr=0.05&limit=20`
- `GET /graph/nodes`
- `GET /graph/edges`
- `GET /quality/latest`

Example response: `GET /health`

```json
{
  "status": "ok",
  "service": "CancerOmicsLake API"
}
```

Example response: `GET /metadata/projects`

```json
{
  "projects": [
    {
      "project_id": "TCGA-BRCA",
      "sample_count": 42,
      "patient_count": 38
    }
  ]
}
```

Example response: `GET /expression/gene/TP53`

```json
{
  "gene_symbol": "TP53",
  "rows": [
    {
      "project_id": "TCGA-BRCA",
      "source": "TCGA",
      "sample_count": 20,
      "mean_expression": 9.41
    }
  ]
}
```

Example response: `GET /quality/latest`

```json
{
  "status": "passed_with_warnings",
  "pipeline_run_id": "20260709T170000Z",
  "checks": [
    {
      "check_name": "expression_values_non_negative",
      "status": "passed"
    }
  ]
}
```

Example response: `GET /research/candidate-genes?cancer_type=TCGA-BRCA&tier=high&limit=20`

```json
{
  "filters": {
    "cancer_type": "TCGA-BRCA",
    "tier": "high",
    "limit": 20
  },
  "row_count": 1,
  "total_matching_rows": 1,
  "warning": "Exploratory prioritization only; scores are not clinically validated.",
  "rows": [
    {
      "cancer_type": "TCGA-BRCA",
      "gene_symbol": "TP53",
      "priority_score": 0.72,
      "priority_tier": "high",
      "evidence_summary": "mutation_frequency=0.4;abs_log2_fold_change=1.5"
    }
  ]
}
```

Notes:

- Endpoints read silver/gold parquet outputs and report files produced by the pipeline.
- Fallback behavior exists for demo safety, but `make run-demo-check-strict` rejects stub/demo-origin rows.
- Reviewer-safe workflow: run `make run-demo` or `make run-demo-aggressive`, then start `make run-api`.

`GET /research/evidence-confidence` accepts `cancer_type`, `gene_query`, `confidence_tier`,
`batch_concordance`, `min_confidence`, and `limit`. It returns calibrated component scores, an overall tier,
batch-sensitivity concordance, batch-effect risk, and machine-readable caveats. Confidence measures evidence reliability;
it does not replace the separate candidate priority score and is not clinical validation.

`GET /research/batch-effect-sensitivity` accepts `cancer_type`, `gene_query`, `support_tier`,
`direction`, `min_abs_percentile_delta`, and `limit`. It returns within-cohort percentile
and robust z-score deltas for TCGA tumor versus GTEx normal expression. This is a sensitivity
analysis that reduces scale dependence; it is not full batch correction.

`GET /research/reference-triangulation` accepts `cancer_type`, `gene_query`, `concordance`,
`support_tier`, `min_stability`, and `limit`. It compares TCGA tumor direction using TCGA
adjacent-normal and GTEx normal references, while preserving reference-shift and support caveats.

`GET /research/bootstrap-stability` accepts `cancer_type`, `gene_query`, `stability_tier`,
`min_stability`, and `limit`. It returns deterministic candidate-level direction, rank, confidence
interval, top-k selection, and reference-concordance stability metrics.

`GET /research/external-expression-validation` accepts `cancer_type`, `gene_query`, `validation_tier`,
`direction_agreement`, `min_validation_score`, and `limit`. It compares native TCGA/GTEx effects with
a normalized recount3 extract when available. It is an external reproducibility check, not clinical validation.

`GET /research/consensus-candidates` accepts `cancer_type`, `gene_query`, `decision`,
`publication_tier`, `min_consensus_score`, and `limit`. It returns the final publication-triage
ranking and explicit rejection reasons from the combined evidence layers.

`GET /research/expression-statistical-support` accepts `cancer_type`, `gene_query`, `support_tier`,
`max_fdr`, `min_support_score`, and `limit`. It returns native and recount3 Mann-Whitney tests,
rank-biserial effects, cancer-wise Benjamini-Hochberg FDR, and replication tiers. Source and disease
status remain confounded, so the endpoint does not represent causal or clinical differential expression.
