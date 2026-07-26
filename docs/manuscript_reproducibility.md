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

Before the final build, complete `configs/manuscript_metadata.yml`. Author identity, affiliation,
email, declarations, exact AI tools/model versions, and the two human-responsibility confirmations
are rendered from that file. Empty or unconfirmed fields deliberately remain visible placeholders;
editing generated `manuscript/manuscript.md` directly is not durable.

The final command fails when required evidence is missing, the dbt or strict-demo gate has not
passed, another report has a failing status, the public graph or FAIR identifier audit is unsafe,
milestones are incomplete, or versioned evidence points to a different Git commit.

Generated package:

```text
manuscript/
├── manuscript.md
├── manuscript_metadata.yml
├── evidence_ledger.json
├── package_manifest.json
├── figures/
├── tables/
└── supplement/
```

All quantitative manuscript claims must appear in `evidence_ledger.json`. SVG figures and CSV tables
are generated directly from aggregate gold marts. The packaged metadata file is the exact snapshot
used to render the draft. DOI registration, target-journal formatting, author confirmation, and
independent biological review remain intentionally manual and fail closed.
