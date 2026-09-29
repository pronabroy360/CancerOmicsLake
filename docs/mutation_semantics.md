# Mutation Evidence Semantics

## Purpose

The mutation layer provides consequence-stratified, open-access TCGA somatic mutation evidence for engineering and
hypothesis generation. It does not classify cancer drivers, pathogenicity, clonality, or clinical actionability.

## Silver Contract

`silver_mutations.parquet` preserves every parsed MAF row and adds two derived fields:

- `consequence_group`: `protein_altering`, `synonymous`, `non_coding_or_regulatory`, or `unclassified`.
- `is_protein_altering`: true only for the conservative protein-altering allowlist in
  `src/processing/mutation_consequences.py`.
- `reference_assembly`: retained from the MAF `NCBI_Build` field. Missing values are recorded as `Unknown`.

The original `variant_classification` is retained unchanged for audit. Unknown classifications are never promoted to
protein-altering evidence.

`silver_mutation_profile.parquet` contains one row per downloaded open-access somatic MAF file and records its project,
sample, source file, checksum metadata, and processing timestamp. This table defines the denominator used by mutation
frequency marts. It prevents expression-only or clinical-only samples from being counted as mutation-profiled samples.

The GDC MAF contract defines `NCBI_Build` as the alignment reference and notes that MAF annotation reports the most
critically affected transcript, while annotated VCF can report multiple affected transcripts. The current recurrence
mart uses the supplied assembly and does not reconstruct transcript-level consequences. See the
[GDC MAF format](https://docs.gdc.cancer.gov/Data/File_Formats/MAF_Format/).

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

`gold_mutation_functional_evidence.parquet` adds a separate, non-ranking evidence layer with:

- unique sample counts for putative loss-of-function, missense, in-frame, and other protein-altering classes;
- exact genomic loci observed in at least two distinct samples;
- recurrence is grouped by reference assembly, chromosome, start position, reference allele, and alternate allele;
- events with unknown reference assembly remain in consequence summaries and are counted, but do not contribute to
  recurrence;
- the maximum sample recurrence at one locus and the fraction of profiled samples carrying a recurrent locus;
- fixed labels `driver_evidence_scope=consequence_and_exact_locus_recurrence` and
  `driver_classification=not_assessed`.

Exact-locus recurrence is a reproducible prioritization feature, not proof that a variant or gene is a cancer driver.
This mart is deliberately excluded from the existing candidate score until an externally reviewed integration method
and independent validation source are available.

`gold_mutation_transcript_evidence.parquet` aggregates the MAF-reported transcript ID, HGVS coding/protein
annotations, Sequence Ontology consequence, VEP impact category, and `all_effects` availability by cancer, gene, and
annotation. `all_effects` is retained in silver for audit; the aggregate mart does not parse its delimiter-encoded
transcript entries. GDC MAF reports the most critically affected transcript, so these rows describe the reported
transcript only, not all possible transcript consequences. GDC also cautions that VEP impact categories do not
necessarily measure relative biological influence. The source impact label is therefore not used as driver or
pathogenicity evidence.

The dbt test `mutation_transcript_evidence_python_parity` compares the full multiset of rows in the
Python gold Parquet and dbt model. Run `make run-gold` before `make run-dbt test-dbt`; a missing or
stale Python output fails the parity gate instead of silently accepting divergent implementations.

## Important Limitations

- Protein-altering does not mean oncogenic, pathogenic, clonal, or causal.
- No VEP impact score, population-frequency filter, copy-number evidence, curated driver model, or protein-coordinate
  hotspot model is applied. Exact genomic recurrence can be split across codons or transcripts.
- Capped acquisition produces a deterministic partial cohort, not full TCGA cohort prevalence.
- Frequencies describe the downloaded open-access profile represented by the release.
- MAF preprocessing and caller choices remain inherited from GDC source workflows.

Any manuscript must describe this as consequence-stratified somatic evidence and must not use the terms driver,
validated biomarker, or clinically actionable without an independent analysis.
