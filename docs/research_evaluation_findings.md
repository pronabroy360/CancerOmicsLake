# Research Evaluation Findings

**Numerical diagnosis (2026-10-15):** The historical three failed LUAD rows repeat one Spearman
statistic across three top-k settings. Four runtime combinations locate the earliest cross-OS
divergence in log2 effects, not input order, medians or ratios. Polars-only changes produce no
observed difference. Corrected sensitivity tables retain 63 and 60 failing cells at the original
tolerance; candidate lists and heldout metrics reproduce. Underlying numerical-library causation
is not established. These unfavorable results remain part of the engineering package.

**Post-v2 published baseline (2026-10-14):** The official `RobustRankAggreg` 1.2.1 container
completed 18 top-k cells on the two corrected globally separated studies. At top-50, the
proposed method minus RRA heldout replication fraction was 0.02-0.10; one paired descriptive
interval included zero. Official RRA versus the earlier `rra_style` heuristic had top-50
Jaccard 0.515-0.887, reflecting different tie handling rather than independent biological
evidence. The corrected studies still show no top-50 advantage over simple maximin. Do not
interpret RRA scores as calibrated significance with shared tumor samples. See the separate
v4 aggregate review; independent reproduction remains unverified.

Updated 2026-10-13. These are exploratory pilot and constructed-simulation findings, not a
publication-readiness verdict. The full preset native and paired studies are separate runs.

**Global split audit:** Native v1 and paired v2 each contain 26 GTEx donors assigned to different
folds across cancers. Within-cancer analyses are separated, but global leakage-free and independent
cross-cancer claims are unsupported for those historical results. Protocol 1.1 full native and
paired runs completed on 2026-10-13 with a single source/donor or source/case partition across all
configured cancers. The private full and selected manifests pass a global zero-crossing audit.
Shared donors still make the cancer estimates dependent, and inspected pilot holdouts are not an
untouched confirmatory test. Both corrected full runs again show no top-50 lower-quantile
replication advantage over simple maximin in BRCA, COAD or LUAD. The new current aggregate review
is `outputs/research/global_evidence_review_v3/`, which preserves earlier bundles and adds
both matched-processing studies; publication remains disabled.

**recount3 provenance audit:** All 90 selected TCGA recount3 records have `gdc_access=controlled`
in their metadata. That field describes an upstream GDC file, not necessarily the access terms of
recount3's processed output. The [recount3 project](https://rna.recount.bio/docs/index.html)
publishes processed TCGA/GTEx expression, and the [AWS Open Data registration](https://github.com/awslabs/open-data-registry/blob/main/datasets/recount.yaml)
labels recount3 public domain. The crosswalk therefore defaults to blocking non-open upstream
records, but `--allow-public-derived` explicitly audits the published processed release without
downloading controlled GDC files. It exports only aggregate counts and input hashes. Exact specimen
matching yielded 19/90 TCGA and 87/90 GTEx recount3 samples in the local extract; two COAD TCGA
files sharing one specimen were excluded from matched comparisons. Specimen identity alone does
not establish comparable expression units or biological validation.

## Frozen exact-specimen processing study

`matched_processing_v1` selected all 617 unambiguous exact matches in cached metadata: 162 BRCA,
136 LUAD and 119 COAD TCGA tumors; 50 breast, 50 lung, 50 transverse-colon and 50 sigmoid-colon
GTEx normals. Duplicate-specimen exclusions were 18, 12 and 31 TCGA specimen IDs and 1, 3 and 2
GTEx IDs for the corresponding cohorts. Each selected record passed case/donor, tissue, QC and
count-column checks. The private manifest remains under `data/research/`; the frozen plan records
input and source hashes. This full match set is different from the older capped 90-per-source
extract. The corrected versioned recount3 silver table contains 39,399,152 measurement rows,
zero duplicate `(source, sample_id, gene_id)` keys and 45 distinct `_PAR_Y` loci.

On shared genes, median per-specimen Spearman was 0.8677 (BRCA), 0.8665 (LUAD), 0.8669 (COAD),
0.9259 (breast), 0.9256 (lung), 0.9250 (transverse colon) and 0.9256 (sigmoid colon). Median
top-100 expressed-gene Jaccard was only 0.38-0.42. These metrics compare ranks/sets, **not**
native TPM values directly with recount3 AUC-scaled coverage. The report retains 95% paired
case/donor bootstrap intervals for cohort medians.

For tumor-versus-mapped-GTEx absolute-effect rankings on identical specimens, top-50 Jaccard was
0.0204 in BRCA, 0 in COAD and 0.0204 in LUAD; top-25 Jaccard was zero in every cancer. The native
top-50 boundary was tied across 488, 412 and 515 genes respectively, so deterministic tie-breaking
materially limits interpretation of the top-list overlap. Top-50 direction agreement was 1.0
for only two shared genes in BRCA/LUAD and undefined for COAD (no shared top genes), **not** a
general direction-concordance result. The weak overlap is an unfavorable sensitivity result,
not an independent biological falsification or evidence that one pipeline is correct. COAD uses
transverse colon in the primary effect comparison; sigmoid remains separate in specimen summaries.

**Frozen post-v1 diagnostic:** `matched_processing_v2` reused the same 617 private exact matches
and kept v1 intact. Across 55,660 complete genes per cancer, signed rank-biserial effect
Kendall tau-b was 0.559 (BRCA), 0.556 (COAD), 0.571 (LUAD). Direction agreement among genes
with both absolute effects at least 0.2 was 89.8%, 90.5% and 90.2%, with denominators
23,247, 22,007 and 23,732. The prespecified 20%-detection filter kept 33,243, 31,875
and 33,684 genes and raised tau-b only to 0.613, 0.617 and 0.605. These are conditional,
descriptive effect-concordance measures, not independent validation.

At top-50, uniform tie resolution gave mean Jaccard 0.0046 (BRCA), 0.0026 (COAD) and
0.0058 (LUAD), below the deterministic v1 overlaps of 0.0204, 0 and 0.0204 except COAD.
Filtering did not rescue this: informative-gene tie means were 0.0063, 0.0042 and 0.0086.
The large native saturation sets and boundary ties therefore remain a serious top-candidate
stability limitation despite substantial broad-gene sign agreement. Tie-resolution variability
must not be confused with the separate 200-replicate paired case/donor bootstrap intervals.

The annotation audit found 20,347 differing TCGA/recount3 symbol strings on shared Ensembl
IDs, while GTEx/recount3 shared symbols matched. It also recorded native STAR-count and GTEx v8
labels versus recount3 Monorail/GENCODE v26. These are observed provenance differences, not
a demonstrated mechanism for rank discordance. No gene names or datasets were remapped after
seeing the result. The new v3 review retains both favorable and unfavorable comparisons.

## Corrected input snapshot

The rebuilt silver layer contains 36,456,660 native TCGA expression rows, 11,240,000 GTEx
expression rows and 45,588 mutation records. These are measurement rows, not file or patient
counts. The metadata manifest has 3,444 entries; it must not be described as 3,444 successfully
parsed expression files. Gene normalization now preserves `_PAR_Y` loci, and repeated same-unit,
same-workflow quantifications are resolved by whole-file provenance ordering, not averaging.

## Native reference pilots

Both `native_reference_pilot_v2` and `native_reference_paired_pilot_v1` completed all three cancer
cohorts. Each used twenty development and twenty holdout biological units per group. The primary
pilot retained 23,960 genes for BRCA, 22,711 for COAD and 25,005 for LUAD after training-only
filtering. The paired pilot restricts tumor/adjacent membership to matched TCGA patients.

At top-50, the lower-quantile stability score and the simpler reference-maximin baseline both
achieved a reference-replication fraction of 1.0 in every cancer in both pilots. Consequently,
these results do not demonstrate an incremental benefit from the lower-quantile bootstrap layer.
Several aggregation comparisons are also saturated. Improvements over a weaker single-reference
fold-change ranking alone would not establish a new computational method.

Primary-pilot median tumor/normal-reference top-list Jaccard values across the development
sensitivity grid were approximately 0.064 (BRCA), 0.072 (COAD), and 0.031 (LUAD). These pooled-grid
medians are descriptive, not independent-replicate confidence estimates. Fixed-pseudocount scaling
could change candidate membership; scaling the pseudocount with the measurements yielded Jaccard
1.0 throughout the tested grid. This establishes a numerical-control property, not biological
normalization or batch correction.

## Constructed truth benchmark

`reference_truth_simulation_v1` evaluated five scenarios with twenty independent simulated
datasets each, comparing eight ranking strategies. At top-25:

| Scenario | Lower-quantile truth precision | Reference-maximin truth precision | Lower-quantile reference replication |
| --- | ---: | ---: | ---: |
| Clean signal | 1.000 | 1.000 | 1.000 |
| GTEx-specific bias | 1.000 | 1.000 | 1.000 |
| Adjacent-specific bias | 1.000 | 1.000 | 0.998 |
| Shared normal bias | 0.018 | 0.016 | 1.000 |
| No-signal null | 0.000 | 0.000 | 0.000 |

The shared-bias counterexample is the key caution: agreement with both normal references can be
perfect while recovery of true tumor effects is very poor. Neither reference concordance nor
reprocessing concordance can alone validate the biological interpretation. These scenarios are
constructed, method-aware stress tests; their truth labels must never be transferred to real genes.

## Engineering evidence

Seven offline synthetic fault scenarios pass against production guards. Two controls are directly
measured: disabling retries fails to recover an interrupted transfer, and byte-count-only checking
accepts a modified same-size evidence source that checksum verification rejects. Transport remains
mocked; no general superiority over an external workflow or real-network resume performance has
been demonstrated. After starting Docker Desktop, twenty research tests passed in the container
and the primary pilot completed. Host/container comparison reproduced all 72 heldout rows and all
2,400 candidate rows exactly. Three of 1,296 sensitivity rows had an absolute-effect Spearman
difference of approximately 6.14e-9, exceeding the fixed `atol=1e-10, rtol=1e-8` tolerance. The
comparison remains failed at that tolerance; it was not relaxed after inspection. Host Polars was
1.42.1 and container Polars 1.44.2; NumPy/SciPy/PyYAML versions matched. This does not isolate the
cause to Polars or any single platform difference. Independent human reproduction remains
unperformed.

## Contribution assessment

The evidence currently strengthens a reproducible engineering and sensitivity-evaluation article.
It does not yet establish a novel ranking method or RECOMB-level computational advance. Keep
negative comparisons and the shared-bias counterexample in the paper. Next requirements are
broader published-method baselines, external or
stronger independent evidence, external-workflow utility comparisons and independent reproduction.

The current review bundle under `outputs/research/global_evidence_review_v3/` records input and output checksums,
all method/cancer/top-k rows, simulation summaries and explicit incomplete-research status. Use the
full-run bundle when available; do not silently relabel the pilot bundle as confirmatory evidence.
