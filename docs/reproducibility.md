# Reproducibility

## Local setup

```bash
make setup
make validate-config
make run-metadata
make run-metadata-strict
make run-silver
make run-gold
make run-quality
make test
```

## Notes

- Public mode is open-access-only.
- Use synthetic or aggregate outputs for GitHub publishing.
- Metadata runs write GDC ingestion audit details to `outputs/reports/gdc_ingestion_audit.json`.
- Set `tcga.require_live_gdc: true` to fail fast if live GDC query is unavailable.
- Silver quality checks write `outputs/reports/silver_data_quality_report.json`.
- Real expression ingestion paths:
  - TCGA files: `data/bronze/tcga/**/expression/*.tsv|*.csv|*.txt`
  - GTEx files: `data/bronze/gtex/expression/*.tsv|*.csv|*.txt`
