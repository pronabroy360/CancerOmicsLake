# FAIR Release Runbook

CancerOmicsLake publishes a versioned, machine-readable bundle of aggregate derived research
tables. The release gate deliberately excludes raw biomedical data and individual-level entities.

## Build and verify

```bash
make build-fair-release RELEASE_VERSION=0.1.0
cd outputs/releases/v0.1.0
sha256sum -c checksums.sha256
```

The build fails if a required research mart is absent or empty, an identifier-bearing column is
present, or values resemble TCGA/GTEx individual identifiers. Internal Patient and Sample graph
entities are removed with the shared public-graph policy before release.

## Bundle contents

- Aggregate expression, mutation, evidence, stability, validation, consensus, and pathway Parquet
  tables
- Sanitized public knowledge-graph node and edge Parquet tables
- `manifest.json` with provenance, schemas, row counts, limitations, and SHA-256 hashes
- Frictionless-style `datapackage.json`
- `checksums.sha256` and a release-specific README

## DOI deposit checklist

1. Run strict quality, dbt, demo, benchmark, and FAIR release gates from the intended Git commit.
2. Verify every checksum and inspect the identifier-safety and graph-publication audit sections.
3. Create a tagged GitHub release using the same semantic version.
4. Deposit the generated bundle in a DOI-minting research repository such as Zenodo or OSF.
5. Add the DOI to `CITATION.cff`, README, manuscript, and release notes.
6. Cite GDC/TCGA, GTEx, recount3, Reactome, and the CancerOmicsLake software separately.

The project code uses MIT licensing. The release metadata does not claim a new license over source
biomedical data; downstream users remain responsible for the source providers' terms.
