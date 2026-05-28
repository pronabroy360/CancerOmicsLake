# Reproducibility

## Local setup

```bash
make setup
make validate-config
make run-metadata
make run-metadata-strict
make run-silver
make run-gold
make test
```

## Notes

- Public mode is open-access-only.
- Use synthetic or aggregate outputs for GitHub publishing.
- Metadata runs write GDC ingestion audit details to `outputs/reports/gdc_ingestion_audit.json`.
- Set `tcga.require_live_gdc: true` to fail fast if live GDC query is unavailable.
