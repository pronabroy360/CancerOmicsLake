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

Notes:

- Endpoints read silver/gold parquet outputs and report files produced by the pipeline.
- Fallback behavior exists for demo safety, but `make run-demo-check-strict` rejects stub/demo-origin rows.
- Reviewer-safe workflow: run `make run-demo` or `make run-demo-aggressive`, then start `make run-api`.
