# Research Goal Evidence Audit

**Engineering diagnosis (2026-10-15):** Four pinned runtime combinations completed. Polars-only
changes did not reproduce the cross-OS difference. The earliest divergent intermediate was the
log2-effect array; fixed-tolerance failures remain in corrected sensitivity results, despite
reproduced candidate lists and heldout metrics. See `docs/engineering_completion.md` for executed
report paths and the separate v5 packaging gate. This is not independent reproduction or novelty.

**Comparator execution (2026-10-14):** The separate published-RRA protocol ran in an
official-package container across all six cancer/study cells. The new aggregate v4 review
records 18 top-k comparisons; prior studies/reviews remain frozen. At top-50 the proposed
method exceeded RRA replication by 0.02-0.10, but still did not outperform simple maximin
in the corrected prior studies. This closes only one comparator-implementation gap, not
novelty, independent reproduction or biological validation. See `docs/published_rra_baseline.md`.

Updated 2026-10-13. Goal status remains active. This audit distinguishes implemented features,
executed evidence and submission readiness; it is not a novelty attestation.

**Audit correction:** Historical native v1 and paired v2 checks establish within-cancer separation
only. A global audit found 26 GTEx donors crossing folds across cancers in each study. Global
leakage-free statements in those historical entries are withdrawn. Protocol 1.1 full native and
paired studies completed on 2026-10-13 with one global donor/case partition. Their private full and
selected manifests were independently rechecked with zero cross-fold units. The new
`outputs/research/global_evidence_review_v3/` adds the frozen post-v1 tie/annotation diagnostic
to the corrected global and v1 processing evidence; both older reviews remain intact.
Independent human reproduction remains unverified; the user requested a handoff and has no reviewer.

| Requirement | Authoritative evidence | Current conclusion |
| --- | --- | --- |
| Correct quantities | Review generator rehashes silver inputs and reads Parquet measurement counts; draft-generation test checks labels; legacy manuscript explicitly historical | Current review draft has verified measurement counts. Older package is not resealed or current. |
| Substantive related work | `docs/research_related_work.md`; manuscript generator and review draft cite GEPIA2, tcga-data-nf, Wang and Arora | Integration/processing sensitivity are established; no blanket superiority claim. |
| Controlled reference experiments | Full global native v1 plan/report and three-cancer output tables | Completed, fixed tumor set across references, balanced group sizes, training-only filtering, 50 sensitivity repeats, 200 training and holdout draws. |
| Matched TCGA cases | Pair-preserving selection, cluster-bootstrap and development-subsampling tests; completed paired global v1 plan/report | Matched analysis completed in all three cancers with global donor separation verified. Original paired v1 grid must not support matched-subsampling claims. |
| Scale/pseudocount sensitivity | Native sensitivity tables and invariance tests | Executed; fixed-offset scaling can change membership, co-scaling offset preserves the tested lists. |
| Heldout rankings without leakage | Whole patient/donor split tests, private manifests, cohort leakage audit, frozen selection tests | Protocol 1.1 full native and paired manifests have zero global cross-fold donors/cases; 423 selected rows in each. Pilot holdouts were inspected; later analysis is not untouched confirmatory validation. |
| Strong baseline comparison | Single-reference fold changes/effects, mean rank, RRA-style heuristic, maximin and official published RRA, retained at all top-k values | Corrected full studies show zero top-50 lower-quantile advantage over maximin in every cancer. The new official-RRA comparison favors lower-quantile at top-50 but does not override that maximin result. |
| Engineering failure benefits | Seven production-function fault scenarios with measured retry-disabled and size-only controls | Passes isolated synthetic scenarios. External workflow superiority and real-network resume performance are unproven. |
| Separate-environment reproduction | Docker pilot plus twenty research tests; `environment_reproduction.json` | Heldout metrics and candidates match exactly; three Spearman cells fail the original numeric tolerance. Not independent human reproduction. |
| Novelty assessment | Baseline comparisons, literature positioning, constructed shared-bias counterexample | Engineering/evaluation contribution strengthened. Novel statistical method and RECOMB competitiveness not established. |
| Reviewable evidence | Current `outputs/research/global_evidence_review_v3/` plus immutable full plans, source archives and aggregate crosswalk audit | Combined corrected review completed with global partition and both processing studies. Publication remains disabled, and an independent reviewer has not reproduced it. |
| Exact-specimen processing sensitivity | `outputs/research/matched_processing_v1/study_plan.json`, `report.json` and aggregate CSV/SVG; private manifest under `data/research/` | 617 exact specimens (417 TCGA, 200 GTEx), 39,399,152 corrected recount3 measurements, zero duplicate keys. Median within-specimen ranks correlate, but top-50 cancer effect-list overlap is 0-0.020 and strongly affected by native score ties. This is processing sensitivity, not independent validation. |
| Frozen post-v1 tie/annotation diagnostic | `outputs/research/matched_processing_v2/` and new `global_evidence_review_v3/`; 200 paired-unit bootstrap draws per cancer | All 617 specimens retained. Broad signed effects agree moderately (tau-b 0.556-0.571; thresholded direction 89.8%-90.5%), but tie-aware top-50 overlap remains very low (mean 0.0026-0.0058). Symbol/provenance differences are recorded, not causally assigned. |
| Publication disabled | No release/DOI creation; review payload sets `publication_enabled: false`; legacy package visibly invalidated | No publication or author/funding/independent-review confirmation asserted. |

## Next Proof Obligations

Both corrected global full runs and the combined review completed. Corrected silver quality passed
all 65 checks, including unique-expression-key guards; the 2026-10-13 suite passed 267 tests.
Retain the numerical
environment-reproduction failure and diagnose or reproduce it prospectively; never relax a
tolerance merely to obtain a pass. One official published comparator is now executed; broader
published-method coverage, independent investigator reproduction and biological review remain
absent. These gaps must not be replaced with synthetic tests
or green software checks when discussing publication readiness.

The matched-processing study uses only publicly released recount3 processed counts in explicit
public-derived mode. Its TCGA source metadata refer to controlled upstream GDC inputs; the run
does not download them. The older 30-per-cohort recount3 table remains unchanged. The new versioned
table preserves `_PAR_Y` loci and has zero duplicate specimen-gene keys; its native versus recount3
effects should not be read as comparable numeric expression units. See
`docs/matched_processing_study.md` for the protocol and limitations.

The constructed shared-bias scenario has perfect reference replication but approximately 0.018
top-25 truth precision for the lower-quantile method. It demonstrates why reproducibility under
shared confounding is not biological validity. Do not use this constructed rate to estimate the
false-discovery rate of real cancer genes.


## Executed engineering evidence (2026-10-15)

Cached preparation completed 21 workload equivalence cells and 84 tool/pass/workload summaries in two passes. Module comparability: True. Native-script comparable outputs: 7/7. Full tests: 297 passed; read-only silver quality: passed (65 checks). Strict numerical sensitivity failures remain retained. Shared TMM normalization and emulated hardware prohibit an end-to-end superiority claim. Independent human reproduction is unverified; author declarations and publication approval remain pending. Publication and DOI deposit are disabled. See the separate v5 review.
