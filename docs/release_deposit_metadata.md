# v0.1.0 Deposit Metadata

Use this packet when depositing the aggregate FAIR bundle in Zenodo, OSF, or another DOI-minting
research repository. Do not enter a DOI in project files until the repository has actually minted
one.

## Upload

- Archive: `outputs/releases/canceromicslake-derived-data-v0.1.0.tar.gz`
- Deposit manifest: `outputs/releases/canceromicslake-derived-data-v0.1.0.deposit.json`
- Archive bytes: `42,348,808`
- Archive SHA-256: `3d418eaaa0aa9b19bce22bff661257484e4d764d7eb9a46c644f6353b85ae039`
- Evidence-producing commit: `011de8b54019f7836893d1d2228b25f8eba041af`

Re-run `make package-fair-release RELEASE_VERSION=0.1.0` immediately before upload and confirm the
archive hash still matches this packet. If it differs, investigate and update this document rather
than uploading silently changed evidence.

## Repository Fields

**Title:** CancerOmicsLake aggregate derived research data

**Version:** 0.1.0

**Resource type:** Dataset

**Creator:** Pronab Chandra Roy

**Description:**

> CancerOmicsLake v0.1.0 is an aggregate, open-access-derived cancer-omics research bundle produced
> from a provenance-aware TCGA-GTEx lakehouse. It contains 18 analysis-ready Parquet resources for
> expression, consequence-stratified mutation summaries, multi-reference sensitivity, candidate
> stability, validation, pathways, and a public-safe cancer-gene knowledge graph. Raw biomedical
> source files and individual-level patient, case, donor, and sample identifiers are excluded.
> Results support reproducible data-engineering evaluation and biological hypothesis generation;
> they are not clinical, causal, diagnostic, or biomarker-validation claims.

**Keywords:**

- bioinformatics data engineering
- TCGA
- GTEx
- cancer genomics
- data lakehouse
- reproducibility
- knowledge graph
- multi-reference sensitivity

**License:** MIT applies to project code. Do not assert a new license over upstream biomedical data;
retain the source-provider terms and citations documented in the bundle.

**Related identifier:** `https://github.com/pronabroy360/CancerOmicsLake`

## Source Acknowledgements

Cite NCI GDC/TCGA, GTEx V8, recount3/Monorail, and Reactome separately from the CancerOmicsLake
software and derived-data DOI. The bundle manifest records source versions and processing scope.

## After DOI Minting

1. Add the DOI to `CITATION.cff`.
2. Add it to the README FAIR release section.
3. Replace the manuscript Data and Code Availability DOI placeholder.
4. Add it to the GitHub release notes.
5. Re-run `make run-submission-readiness`.

DOI registration satisfies a persistent-identifier packaging gate only. It does not replace
independent biological review or author confirmation.
