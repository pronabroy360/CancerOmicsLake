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
`min_confidence`, and `limit`. It returns calibrated component scores, an overall tier,
batch-effect risk, and machine-readable caveats. Confidence measures evidence reliability;
it does not replace the separate candidate priority score and is not clinical validation.

`GET /research/batch-effect-sensitivity` accepts `cancer_type`, `gene_query`, `support_tier`,
`direction`, `min_abs_percentile_delta`, and `limit`. It returns within-cohort percentile
and robust z-score deltas for TCGA tumor versus GTEx normal expression. This is a sensitivity
analysis that reduces scale dependence; it is not full batch correction.
