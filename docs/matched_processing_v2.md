# Matched Processing Sensitivity v2

This is a **post-v1 exploratory diagnostic**, specified after the unfavorable v1 overlap
was observed. It cannot be described as an untouched confirmatory study or independent
biological validation. The exact v1 specimen manifest and corrected recount3 silver table
are reused; no downloads, controlled GDC files, or re-extraction occur.

## Frozen contract

`configs/matched_processing_v2.yml` fixes seed 20261014, 617 exact specimens, a complete
shared-gene universe, top-25/50/100 lists, a 20% detection-prevalence filter, 1000 point
tie draws, 200 biological-unit resamples and 100 tie draws per resample. The plan under
`outputs/research/matched_processing_v2/` hashes the v1 plan/report, private manifest,
native and corrected recount3 silver inputs, three implementation files, dependency versions,
and input row counts. A changed input or source file requires a new study ID. The local
source snapshot is in `outputs/research/protocol_sources/matched_processing_v2_cb208415ca7f72ad/`.

## Metrics and audit

Each cancer uses identical matched specimens in both pipelines. The primary comparison
uses all complete shared genes. The informative subset requires `>0` expression in at
least 20% of both tumors and normals **in each pipeline**; fewer than 100 genes marks
that subset incomplete. BRCA uses breast, LUAD lung and COAD transverse colon as the
primary normal reference. Sigmoid colon remains in the v1 specimen summary.

Signed rank-biserial effects are computed within, never across, expression units.
The report includes zero/saturated effect fractions, signed Kendall tau-b, and effect
direction agreement only where both absolute effects reach 0.2, with denominators.
For absolute-effect top-k lists, it retains v1's deterministic result and adds seeded
uniform boundary-tie resolution. The tie distribution is **computational uncertainty**;
paired case/donor bootstrap intervals are separate, descriptive biological-unit
resampling uncertainty conditional on this available matched set. No differential-
expression p-value or clinical interpretation is implied.

The annotation/workflow audit counts common and unique Ensembl IDs, `_PAR_Y` loci,
symbol conflicts, and paired detection discordance. It records only available native
workflow/version and recount3 annotation labels; missing provenance is `unknown`.
These differences are hypotheses about the source of disagreement, not causal proof.

All specimen IDs and per-gene effect intermediates stay in `data/research/` or ignored
silver input files. Aggregate CSV/JSON/SVG and a new hashed review bundle may be shared
only after privacy and quality review. The v1 study and both older reviews remain
unaltered; the new bundle keeps publication disabled.

```sh
make run-matched-processing-v2-prepare
make run-matched-processing-v2
make build-matched-processing-v2-review
```

Independent human reproduction remains outstanding. A same-author rerun, green tests,
or Docker execution does not satisfy that requirement.

## Observed results

The completed run retained all 617 specimens (417 tumors, 200 GTEx normals), with
55,660 complete shared genes per cancer and 31,875-33,684 genes in the fixed
informative subset. All six cancer/universe comparisons completed 200 paired
biological-unit resamples. On all shared genes, signed-effect Kendall tau-b was
0.556-0.571 and directional agreement was 89.8%-90.5% among approximately
22,000-24,000 genes clearing the effect threshold in both pipelines. Informative-
gene tau-b was 0.605-0.617. These are descriptive, not evidence of independent
biological validity.

The all-gene top-50 deterministic Jaccard exactly reproduced v1: 0.0204 BRCA,
0 COAD and 0.0204 LUAD. Uniform boundary-tie resolution gave mean top-50
Jaccard 0.0046, 0.0026 and 0.0058 respectively. Even after the fixed detection
filter, tie-resolution means were only 0.0063, 0.0042 and 0.0086. Native top-50
boundaries had 488, 412 and 515 tied genes; many effects saturate at absolute
value 1. The fixed filter improves broad concordance but does **not** rescue
top-candidate stability. Tie-draw ranges and paired-unit bootstrap intervals
remain separate columns in the aggregate table.

The annotation audit found 57,606 shared TCGA/recount3 Ensembl IDs and 56,200
shared GTEx/recount3 IDs. Among shared TCGA IDs, 20,347 recorded symbol strings
differed, versus zero for GTEx; TCGA native records `STAR - Counts`, GTEx native
records `v8`, and recount3 records its Monorail/GENCODE v26 label. This is an
annotation/provenance discrepancy, not proof that symbols or workflow versions
caused the effect-rank difference. No annotation was changed during the study.
