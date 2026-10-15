# Independent Reproduction Handoff

## Current Engineering Package (2026-10-15)

Follow `docs/engineering_completion.md` for the numerical diagnosis and cached external-module
benchmark. The new v5 review is the current package once its build completes; older reviews below
remain historical. Independent human reproduction is still unverified. Check the execution and
numerical-acceptance fields separately: completed execution is not proof of numerical equivalence.

The numerical study observed the first macOS/Linux difference in log2 effect arrays (maximum
4.44e-16), followed by tie/rank differences. Changing Polars 1.42.1 to 1.44.2 within either OS
did not change these arrays. This does not identify the underlying library/compiler cause.
Corrected candidate lists and heldout metrics reproduced, but sensitivity comparisons retained
63 native-study and 60 paired-study failed cells at the original tolerance. Do not widen it.

The external comparison measures cached preparation modules, not Nextflow orchestration.
Its shared edgeR TMM backend, adapter costs and AMD64 emulation must accompany timing claims.
The aggregate archive excludes specimen manifests and matrices; reconstruct and hash-check these
before attempting independent execution. Publication and DOI deposit remain disabled.

## Published RRA Comparator

`docs/published_rra_baseline.md` describes the new post-v2 comparator protocol and separate
Docker/R execution. The author-run container completed all six cohort/study cells and the
`global_evidence_review_v4` aggregate review. An independent investigator should verify the
package version, image digest, frozen candidate reproduction, all 18 top-k cells, paired
intervals and resource hashes. The author-run result is **not** independent human
reproduction; publication remains disabled.

Updated 2026-10-13. No independent investigator confirmation has been received. Do not convert
same-author Docker execution, a code review or a green test suite into independent reproduction.

## Global Partition Correction

The final private-manifest audit found 26 GTEx donors crossing development/holdout folds across
cancers in each of native v1 and paired v2. Their zero-leakage checks were within cancer only.
Do not use those historical studies to claim a globally separated holdout. Protocol 1.1 now assigns
each source/donor or source/case once across every configured cancer, stratified by project/group
availability. New frozen IDs are `native_reference_global_v1` and
`native_reference_paired_global_v1`. Both completed on 2026-10-13; their private full and selected
manifests passed the global leakage audit. The archived protocol-1.1 source is at
`outputs/research/protocol_sources/dcb5d1c0a62aa3a465eea8c987ef42e84b44464eb6849a3f0ace3254dc42a0e1/controlled_reference_study.py`.
Shared donors also mean cancer-level estimates are dependent even after this correction.
The historical evidence paths below remain for auditing earlier results.

The current review is `outputs/research/global_evidence_review/`, built from the two corrected
full studies with zero top-50 lower-quantile replication advantage over maximin in all three
cancers. An independent reviewer should reproduce those plans and manifests first.

The TCGA recount3 metadata for all 90 selected samples reports upstream `gdc_access=controlled`.
The [processed recount3 release](https://rna.recount.bio/docs/index.html) is publicly available;
the [AWS registry](https://github.com/awslabs/open-data-registry/blob/main/datasets/recount.yaml)
labels recount3 public domain. The crosswalk uses an explicit public-derived mode, records only
aggregate matches and excludes ambiguous specimens. It does not establish expression-scale or
annotation comparability. The native TCGA/GTEx study is separate.

The additional `matched_processing_v1` study used all 617 exact available specimen matches from
cached public recount3 processed counts (417 TCGA, 200 GTEx), with a frozen private match manifest,
input/code hashes and a distinct corrected silver table. The new review is
`outputs/research/global_evidence_review_v2/`; the older global review remains intact. Median
within-specimen ranks correlate, but top-50 cancer effect-list Jaccard is 0-0.020 and native
boundary ties make that comparison unstable. This is an unfavorable processing sensitivity result,
not independent validation. The implementation snapshot is
`outputs/research/protocol_sources/matched_processing_v1_8672f5e7c125d655/`.
See `docs/matched_processing_study.md`.

The frozen post-v1 `matched_processing_v2` diagnostic reuses the same 617 specimens and does not
replace v1. Its plan hashes the v1 snapshot and its own implementation; a local source archive is
at `outputs/research/protocol_sources/matched_processing_v2_cb208415ca7f72ad/`. An independent
investigator should reproduce the 20% four-group detection filter, tie-resolution draws and 200
paired case/donor resamples, then verify that top-50 tie means remain 0.0026-0.0058 despite
all-gene Kendall tau-b of 0.556-0.571. Confirm the 20,347 TCGA symbol-string disagreements,
but do not treat them as a causal explanation without a separate controlled experiment. The
current combined review is `outputs/research/global_evidence_review_v3/`; publication is disabled.

## Evidence to Review

- `outputs/research/global_evidence_review/review.json`: current verified sources, counts and gaps.
- `outputs/research/global_evidence_review_v2/review.json`: new hash-verified aggregate review including processing sensitivity; publication disabled.
- `outputs/research/global_evidence_review_v3/review.json`: newer review with frozen v2 tie, bootstrap and annotation diagnostics; older reviews preserved.
- `outputs/research/matched_processing_v2/`: v2 plan, aggregate tables, figure and hashed report; private draw/gene files remain under `data/research/`.
- `outputs/research/matched_processing_v1/`: processing plan, aggregate report/figures and selection audit (no individual IDs).
- `outputs/research/global_evidence_review/manuscript_draft.md`: current exploratory draft.
- `outputs/research/global_evidence_review/heldout_methods.csv`: every cancer/method/top-k result.
- `outputs/research/global_evidence_review/simulation_methods.csv`: all constructed scenarios.
- `outputs/research/native_reference_global_v1/`: current full native plan and outputs.
- `outputs/research/native_reference_paired_global_v1/`: current matched full plan and outputs.
- `outputs/research/full_evidence_review/`: historical review with known cross-cancer fold crossings.
- `outputs/research/reference_truth_simulation_v1/`: frozen constructed-truth model and results.
- `outputs/research/environment_reproduction.json`: original strict-tolerance reproduction failure.
- `outputs/research/failure_experiments.json`: isolated synthetic fault scenarios and controls.

Review JSON hashes before interpreting tables. The native v1 implementation is archived at
`outputs/research/protocol_sources/73429ce3b64c08e29850cac110a140ae230208ef3da518de71f27a2d3a939dcb/controlled_reference_study.py`.
The corrected paired v2 implementation fingerprint is recorded in its plan and must match the
source used to execute it. Parent Git SHA alone does not identify uncommitted source edits.

## Reproduction Procedure

1. Work in a clean private workspace. Obtain the exact open-access silver inputs privately or
   reacquire public source files and reproduce the input transformation. Do not publish raw files,
   individual identifiers, sample split manifests or donor metadata.
2. Verify every input byte count/SHA-256 against the frozen plan. If the snapshot differs, report
   a new-data replication, not an exact reproduction. Do not silently substitute current downloads.
3. Use Python 3.11 and the package versions recorded in the relevant plan. The original host plans
   use NumPy 2.4.6, Polars 1.42.1, SciPy 1.17.1 and PyYAML 6.0.3. A dependency-drift experiment
   must record its differences and must not be pooled with an exact-environment claim.
4. Use each plan's exact configuration and implementation, writing results and private manifests
   to separate roots. Do not reuse the author's output directories or edit a frozen plan to make
   it accept changed settings. Archived native v1 source is needed for exact replay because current
   configs/source have intentionally moved to new identifiers after the paired-subsampling repair.
5. Compare case/donor partitions privately, candidate IDs/ranks exactly, and all aggregate numeric
   outputs at the original `atol=1e-10, rtol=1e-8` tolerance. Preserve failures, missing cohorts,
   implementation differences and any evidence of leakage. Report all methods and top-k values.
   For the processing arm, verify all 617 private exact matches and per-cohort duplicate exclusions,
   recount3 `_PAR_Y` preservation, zero duplicate measurement keys and report/plan SHA-256 hashes.
   Compare ranks and gene sets rather than numeric TPM to AUC-scaled coverage; report cutoff ties.
   For v2, separately reproduce the seeded tie-resolution distribution and the paired biological-
   unit bootstrap intervals. Report broad signed-effect concordance and near-zero top-list overlap
   together; neither cancels the other. Do not call same-author v2 a confirmatory replication.
6. Exercise fault scenarios independently. Distinguish mocked transport retry from actual network
   interruption recovery and independent workflow comparisons. Reproduce the shared-normal-bias
   counterexample; do not reinterpret its truth labels as real cancer biology.
7. Record the investigator, date, environment, source/input/output hashes, commands, deviations,
   pass/fail results and interpretation in a signed or attributable review. Leave status unverified
   until the investigator personally confirms it. No release, DOI deposit or submission is authorized.

## Questions for the Investigator

Can you reproduce the patient/donor separation and matched development subsampling? Do candidate
rankings and conditional intervals match? Does fixed-pseudocount scaling change candidate membership,
and does co-scaling preserve it? Are the weak single-reference baselines and stronger maximin
baseline reported equally? Do you agree that the lower-quantile score has no demonstrated top-50
replication advantage over maximin in the current full studies? Does the shared-bias counterexample
invalidate any biological-validation language? Is the evidence sufficient for an engineering methods
article, and what would be required for a substantive new computational-method claim?

## Known Reproduction Caveat

The author's original Docker run matched all heldout metrics and candidate ranks exactly, but three
sensitivity Spearman cells differed by approximately 6.14e-9 and failed the original fixed tolerance.
The container used a different Polars version and a different software environment. The cause has
not been isolated. Do not loosen the tolerance after seeing that failure or claim the entire strict
reproduction passed. Report numerical significance separately from scientific significance.
