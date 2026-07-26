# Manuscript Reproducibility

Build the journal-neutral manuscript evidence package only after regenerating research reports and
the FAIR bundle from the intended Git commit:

```bash
make run-quality
make test-dbt
make run-demo-check-strict
make run-reference-ablation
make run-project-completion
make run-research-benchmark
make build-fair-release RELEASE_VERSION=0.1.0
make build-manuscript-package
```

The final command fails when required evidence is missing, the dbt or strict-demo gate has not
passed, another report has a failing status, the public graph or FAIR identifier audit is unsafe,
milestones are incomplete, or versioned evidence points to a different Git commit.

Generated package:

```text
manuscript/
├── manuscript.md
├── evidence_ledger.json
├── package_manifest.json
├── figures/
├── tables/
└── supplement/
```

All quantitative manuscript claims must appear in `evidence_ledger.json`. SVG figures and CSV tables
are generated directly from aggregate gold marts. Author affiliation, funding, competing interests,
DOI, target-journal formatting, and biological review remain intentionally manual.
