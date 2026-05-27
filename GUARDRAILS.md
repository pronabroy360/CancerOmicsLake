# GUARDRAILS.md

This file defines **possible guardrails** for safe, reproducible, and publication-ready execution of CancerOmicsLake.

## 1) Compliance Guardrails (Hard Stop)

1. Open-access mode is default and mandatory for public runs.
2. Controlled-access files must be blocked unless an explicit private-mode override exists.
3. Never commit raw downloaded biomedical data to Git.
4. Never commit tokens, secrets, manifests with credentials, or private keys.
5. Never publish individual-level sensitive patient/donor details in dashboard/API outputs.
6. Public artifacts must be aggregate-level or synthetic/sample-safe.

Fail condition:
- If any rule above is violated, pipeline status = `failed_compliance`.

## 2) Repository Guardrails

1. `.gitignore` must include at least:
   - `data/`
   - `.env`
   - `*.token`
   - `*.pem`
   - `*.key`
   - `outputs/raw/`
   - `gdc-user-token*`
2. All configs required for pipeline execution must live in `configs/`.
3. Documentation updates are required for schema or interface changes.
4. Each milestone must leave a trace in `WORKLOGS.md`.

## 3) Data Ingestion Guardrails

1. TCGA projects must be from configured whitelist (MVP: BRCA, LUAD, COAD).
2. Metadata fetch must capture source fields needed for traceability:
   - file id/name, checksum, size, project, case, sample, category/type.
3. Manifest-based downloads should be checksum-verified when checksums are present.
4. Failed downloads must be logged with retry metadata.

## 4) Transformation Guardrails

1. Preserve raw values and source IDs before transformation.
2. Gene normalization must preserve original gene ID and normalized ID.
3. Ensembl version suffix stripping must be deterministic and logged.
4. Expression values must be non-negative.
5. Expression unit must always be stored and never inferred silently.
6. Missing values must use consistent null handling rules across tables.

## 5) Schema and Modeling Guardrails

1. Silver and gold tables must have stable schemas (versioned on breaking changes).
2. Primary key strategy must be explicit and deterministic.
3. Fact tables must only use validated foreign keys from dimension tables.
4. Gold tables must contain analysis-ready fields only.
5. Every gold table must be documented in `docs/data_dictionary.md`.

## 6) Quality Guardrails

Minimum required checks:

1. Null project IDs: fail
2. Null gene IDs in expression facts: fail
3. Duplicate sample IDs within source: fail
4. Negative expression values: fail
5. Invalid mutation positions: fail
6. Access level violation in public mode: fail
7. Gene mapping rate below threshold: warn/fail based on threshold
8. Checksum mismatches: fail

Suggested thresholds (MVP):

- Gene mapping rate target: `>= 0.98`
- Failed download rate target: `< 0.02`
- Duplicate sample ratio target: `0.00`

## 7) Analytical Guardrails

1. Tumor-vs-normal outputs must include a batch-effect caveat.
2. No claims of clinical validity or biomarker discovery in docs/UI.
3. Label analysis as exploratory engineering output.

## 8) Graph Guardrails

1. Node and edge exports must include schema version metadata.
2. Dense graph control: export only top-N edges per cancer where needed.
3. Edge derivation logic must be reproducible and documented.
4. Graph exports must avoid any sensitive row-level identifiers not required for MVP.

## 9) API and Dashboard Guardrails

1. `/health` and quality endpoints must expose run status safely.
2. API responses must not leak local paths, credentials, or tokenized URLs.
3. Dashboard must display data freshness timestamp and run status.
4. Any failed quality gate must be visible in UI before exploratory charts.

## 10) Operational Guardrails

1. Every pipeline run records:
   - `pipeline_run_id`, start/end, status, config hash, error/warning counts.
2. Reruns should support stage-level retry without full rebuild.
3. Any schema change requires test updates in same change set.
4. Release candidate requires:
   - tests passing
   - quality report generated
   - docs updated
   - compliance checklist passed

## 11) Publishing Guardrails

Before GitHub publish:

1. Run secret scan.
2. Verify no `data/` raw files tracked.
3. Verify only sample/synthetic/public-safe artifacts in `outputs/`.
4. Include compliance note in README.
5. Include reproducibility commands and expected outputs.

