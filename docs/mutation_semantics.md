# Mutation Evidence Semantics

## Purpose

The mutation layer provides consequence-stratified, open-access TCGA somatic mutation evidence for engineering and
hypothesis generation. It does not classify cancer drivers, pathogenicity, clonality, or clinical actionability.

## Silver Contract

`silver_mutations.parquet` preserves every parsed MAF row and adds two derived fields:

- `consequence_group`: `protein_altering`, `synonymous`, `non_coding_or_regulatory`, or `unclassified`.
- `is_protein_altering`: true only for the conservative protein-altering allowlist in
  `src/processing/mutation_consequences.py`.

The original `variant_classification` is retained unchanged for audit. Unknown classifications are never promoted to
protein-altering evidence.

`silver_mutation_profile.parquet` contains one row per downloaded open-access somatic MAF file and records its project,
sample, source file, checksum metadata, and processing timestamp. This table defines the denominator used by mutation
frequency marts. It prevents expression-only or clinical-only samples from being counted as mutation-profiled samples.

## Gold Contract

`gold_mutation_frequency_by_gene.parquet` reports the fraction of downloaded mutation-profile samples containing at
least one conservatively classified protein-altering event in a gene. Synonymous and non-coding events do not create
mutation support for candidate prioritization or graph edges.

Audit columns preserve the distinction:

- `protein_altering_event_count`
- `all_somatic_event_count`
- `synonymous_event_count`
- `mutation_scope`, fixed to `protein_altering_only`

The cancer-level mart uses the same profiled-sample denominator and preserves all-event audit counts.

## Important Limitations

- Protein-altering does not mean oncogenic, pathogenic, clonal, or causal.
- No VEP impact score, population-frequency filter, copy-number evidence, driver model, or hotspot model is applied.
- Capped acquisition produces a deterministic partial cohort, not full TCGA cohort prevalence.
- Frequencies describe the downloaded open-access profile represented by the release.
- MAF preprocessing and caller choices remain inherited from GDC source workflows.

Any manuscript must describe this as consequence-stratified somatic evidence and must not use the terms driver,
validated biomarker, or clinically actionable without an independent analysis.
