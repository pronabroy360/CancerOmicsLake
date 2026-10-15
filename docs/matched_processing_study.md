# Matched Processing Sensitivity (v1)

## Question and boundary

How much do gene-rank summaries change when the **same specimens** are quantified by
native TCGA/GTEx pipelines versus the public, uniformly reprocessed recount3 release?
This is a descriptive processing-sensitivity study, not an independent validation cohort,
differential-expression analysis, batch correction, biomarker study or clinical claim.
Native TPM and recount3 AUC-scaled coverage are different units; no numerical fold change
is computed between the pipelines.

## Frozen protocol

`configs/matched_processing_v1.yml` fixes seed 20261013, all unambiguous exact matches,
1000 shared genes minimum, 1000 paired-unit bootstrap repeats, and top-25/50/100 effect
rank sets. `study_plan.json` records source-code and input SHA-256 hashes, dependency
versions, source revision, selection counts, access mode and recount3 release provenance.
The plan is locked before metrics. Changed inputs or code require a new study ID.
The exact implementation snapshot is archived locally at
`outputs/research/protocol_sources/matched_processing_v1_8672f5e7c125d655/`;
its four implementation hashes match the frozen plan. This is a local reproducibility
artifact, not authorization to publish input data or private identifiers.

The cohort match uses the GDC sample UUID for TCGA and SAMPID for GTEx, and checks TCGA
case/project/sample type or GTEx donor/tissue, QC AUC, and count-file header. Duplicate
specimen mappings are excluded in full. A missing count column or conflicting linkage is
fatal. All exact matches are selected, without a sample cap. Upstream TCGA count records
may be controlled; only the **publicly released processed** recount3 outputs are read,
and this path requires `allow_public_derived: true`. No controlled GDC files are fetched.

The private match manifest and specimen-level metrics stay under `data/research/`.
The new corrected table is `data/silver/silver_expression_recount3_matched_processing_v1.parquet`.
It preserves `_PAR_Y` loci when stripping Ensembl versions and rejects duplicate
`(source, sample_id, gene_id)` keys. The older capped recount3 extract and its downstream
results are not rewritten. Public reports and figures contain cohort aggregates only.

## Metrics

For each matched specimen: shared gene coverage, Spearman on all shared genes, Spearman
on genes detected in both pipelines, and top-100 expressed-gene Jaccard. Ties use
deterministic gene-ID ordering. For each cancer: independent within-pipeline tumor-versus-
normal rank-biserial effects on the same matched specimens and a complete common-gene
universe. Report top-25/50/100 absolute-effect rank overlap, direction agreement among
shared top genes, and boundary ties. COAD uses transverse colon for the primary effect
comparison; transverse and sigmoid remain separate in specimen-level summaries.

Bootstrap intervals summarize specimen-level median metrics by resampling matched TCGA
cases or GTEx donors, preserving all their specimens across both pipelines. These are
descriptive conditional intervals, not sampling guarantees for other populations. Effect
rank overlap is a point estimate. Small cohorts, many tied effects and any unfavorable
discordance must remain visible in the report and manuscript.

## Observed aggregate results

The frozen run selected 617 specimens: 417 TCGA tumors (BRCA 162, LUAD 136, COAD 119)
and 200 GTEx normals (50 each in breast, lung, transverse colon and sigmoid colon).
It produced 39,399,152 corrected recount3 measurement rows with zero duplicate
specimen-gene keys. Median per-specimen Spearman on all shared genes was approximately
0.867 in TCGA and 0.925 in GTEx, but median top-100 expressed-gene Jaccard was only
0.38-0.42. Top-50 tumor-versus-normal absolute-effect Jaccard was 0.0204 for BRCA,
0 for COAD and 0.0204 for LUAD. Native top-50 cutoffs had 488, 412 and 515 tied
genes respectively. Top-25 lists shared no genes in any cancer. These are negative,
tie-sensitive results, not evidence that one processing pipeline is biologically right.
Direction agreement at top-50 was defined for only two shared genes in BRCA and LUAD;
COAD had none. No cohort-level effect-overlap uncertainty interval is claimed.

## Execution and verification

```sh
make run-matched-processing-prepare
make run-matched-processing
.venv/bin/python -m src.operations.research_review \
  --studies outputs/research/native_reference_global_v1 \
            outputs/research/native_reference_paired_global_v1 \
  --processing outputs/research/matched_processing_v1 \
  --output outputs/research/global_evidence_review_v2
```

Do not publish `data/research/`, silver Parquet or raw recount3 files. A different
researcher still needs to reproduce the frozen protocol independently; neither this run
nor a Docker rerun fulfills that obligation. The v2 review must preserve the prior
review bundle and keep `publication_enabled` false.
