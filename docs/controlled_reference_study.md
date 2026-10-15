# Controlled Reference Study

## Protocol 1.1: Global donor/case separation

Assign biological units once across all configured cancers, stratified by their project/group
availability signature. All tissues from a GTEx donor must share a fold; within-cancer balancing
cannot change that assignment. The runner checks both the global index and saved private manifest
and reports `partition_scope` and `global_group_leakage_count`. Shared donors still induce
cross-cancer dependence, so cancer results cannot be treated as independent replicates.

Current full IDs are `native_reference_global_v1` and `native_reference_paired_global_v1`.
Historical native v1 and paired v2 each had 26 GTEx donors crossing folds across cancers despite
zero within-cancer leakage. Retain those artifacts as historical evidence, not a globally separated
holdout. Both corrected full studies completed on 2026-10-13, and their private manifests have zero
global fold crossings. This correction changed the split protocol, not ranking parameters.

## Objective and claim boundary

Test whether reference-aware ranking improves patient/donor-held-out reproducibility relative to
single-reference and simple aggregation baselines. The experiment is a candidate computational
contribution, not established novelty, independent-cohort validation, or biological ground truth.
Publication suitability will be decided from the observed results and comparison with prior work.

The YAML protocol is fixed before the new experiment executes. This is a prospective local lock,
not an externally registered preregistration; previous exploratory project results already exist.

## Acceptance criteria

1. Each cancer uses the same tumor samples for its adjacent-normal and GTEx contrasts, equal-sized
   reference groups, a single configured GTEx tissue, and canonical Ensembl IDs.
2. TCGA cases and GTEx donors cannot appear in both development and holdout partitions. Retain at
   most one measurement sample per biological unit and group; deterministic sample-ID selection
   resolves multiple specimens. This choice limits specimen representation and must be reported.
3. All abundance eligibility, orientation, scores, candidate choices, and any later tuning use
   development data only. Missing holdout measurements cause a failure, never a new gene filter.
4. Run repeated 80% development subsampling, abundance thresholds, pseudocount and global-scale
   perturbations. Repeats are correlated: report empirical spread, not independent-sample CIs.
5. Freeze candidate lists before held-out evaluation. Report reference-specific list overlap,
   direction replication, worst-reference effect, conditional bootstrap intervals and paired
   proposed-minus-baseline differences. Preserve TCGA case clusters during bootstrap so shared
   tumor/adjacent cases are resampled together; resample GTEx donors separately.
6. Retain negative and inconclusive results, zero-score candidate counts, all baselines, and all
   cancers. Never choose a favorable K, tissue, seed, or score after examining holdout results.

## Primary native experiment

The three native cohorts contain TPM measurements. TCGA cases are stratified by available tumor /
adjacent sample types, and GTEx donors are partitioned separately. Group-disjoint development and
holdout partitions use the fixed seed. Equal group sizes are capped by the smallest available
partition group and the configured cap. Colon Transverse is the prespecified primary COAD tissue;
Colon Sigmoid requires a separately named study, not pooled reference samples.

Only development observations determine the common complete gene universe and abundance filter:
retain a gene when its TPM meets the configured threshold in at least the configured fraction of
one development group. The primary filter is 1 TPM / 20% prevalence; zero TPM is a sensitivity arm.
Filtering each sensitivity subsample is exploratory. Bootstrap holdout inference instead keeps the
primary development universe fixed. Genes are joined by Ensembl ID, never ambiguous symbols.

Compare median-based log2 ratios, signed rank-biserial U effects, mean percentile ranks, an
RRA-style order-statistic ranking, a sign-consistent maximin effect, and an experimental
lower-quantile maximin score. The signed rank-biserial effect is invariant to a strictly monotone
transformation applied to both groups for the same gene; this does not eliminate cross-study
collection or composition bias.

The experimental score is the nonnegative lower 10% training-bootstrap quantile of the minimum
of the two reference effects, oriented by the full development effect. No novel statistical method
or stability-selection error-control theorem is claimed. RRA-style ranking assumes no valid
independent-list null here, because the reference lists share tumors; it provides scores, not
inferential p-values. The original eight-component consensus is not fitted anew by this experiment.

Each single-reference baseline predicts its own development direction. Aggregate methods predict
the direction of the sum of the two development rank-biserial effects. For every frozen top-K list,
replication requires the predicted direction and a signed heldout rank-biserial effect >= 0.3 under
both references. This endpoint deliberately measures cross-reference reproducibility, not accuracy
against known cancer genes, and can favor methods optimized for that criterion. Both heldout
reference-specific top-list Jaccards are reported as complementary descriptive endpoints.

Rank ties within 12 decimal places are resolved by canonical gene ID. Top-K lists can contain
zero-score genes when fewer than K genes have positive scores; the positive-score count makes this
limitation visible. Effect and replication intervals use 200 case/donor bootstrap draws with fixed
training choices. They do not account for all training-selection uncertainty or multiplicity over
methods/K/cancers. A pilot uses fewer draws and cannot establish a confirmatory improvement claim.

## Execution and artifacts

```bash
make run-controlled-reference-study
.venv/bin/python -m src.main run-controlled-reference-study \
  --study-config configs/controlled_reference_pilot.yml
.venv/bin/python -m src.main run-controlled-reference-study \
  --study-config configs/controlled_reference_paired_pilot.yml
```

Each study locks configuration, input bytes/checksums, the parent Git revision and implementation
checksum before producing results. The same study ID cannot silently change its protocol or input
snapshot. Worktree edits are distinguished by the implementation checksum; the parent Git commit
alone is not an attestation of uncommitted code. Final publication requires a committed revision and
rerun with a new study identifier.

- `outputs/research/<study_id>/study_plan.json`: immutable local protocol and input snapshot.
- `sensitivity.parquet`: development-only equal-size and scale/pseudocount experiments.
- `heldout_evaluation.parquet`: method metrics and paired bootstrap difference intervals.
- `training_candidates.parquet`: development-only gene selections and scores.
- `report.json`: cohort coverage, counts, claim boundaries, and artifact checksums.
- `data/research/<study_id>/sample_split_manifest.parquet`: private split manifest, excluded by
  the repository data ignore rule. Individual sample/case/donor IDs never enter aggregate outputs.

## Remaining research requirements

### Input correction discovered by the pilot

The first real-data pilot (`native_reference_pilot_v1`) stopped at the duplicate-measurement
guard. A whole-table diagnostic found 571,592 duplicate sample/gene groups in native TCGA TPM
data, including 26,444 groups with within-file duplicates. Inspection of raw STAR files confirmed
versioned `_PAR_Y` identifiers that the old normalizer collapsed into the corresponding base ID.
These counts describe the old silver snapshot, not the corrected dataset or biological findings.

Normalization now strips the numeric version while retaining `_PAR_Y`. Where a sample has multiple
quantification files in the same unit and workflow, ingestion selects one whole file by sorted
provenance path, independently of expression values. Conflicting workflows or duplicates remaining
within a selected file fail. This is a deterministic aliquot-selection policy, not an estimate of
measurement uncertainty; its sensitivity remains to be assessed before publication.

Rebuild silver and all downstream evidence before relying on existing results. Preserve the failed
pilot plan; use `native_reference_pilot_v2` for the corrected inputs. Do not merge the corrected
pilot results into an older manuscript ledger or claim the archived release reflects this repair.

### Engineering fault experiments

`make run-failure-experiments` exercises production functions against isolated synthetic inputs:
checksum corruption, interrupted transfer with retry, missing expression schema, duplicate
measurements, negative values, same-size evidence changes, and a changed frozen study protocol.
The JSON report is written to `outputs/research/failure_experiments.json`. Transport is mocked;
this does not measure real-network recovery, external-workflow superiority, or independent human
reproduction. Hypothetical unguarded behaviors are explanatory controls, not measured competitors.
The retry-disabled control is now executed through the same production downloader with zero
retries, and the size-only control directly checks the corrupted source's unchanged byte count.
These isolated control comparisons are not benchmarks against another published workflow.

### Known-truth simulation and review bundle

`make run-reference-truth-simulation` locks and runs five log-normal scenarios, each with twenty
independently simulated development/holdout datasets: clean signal, GTEx-specific bias,
adjacent-specific bias, shared-normal bias, and a no-signal null. Shared TCGA patient variation
preserves pairing; simulated development/holdout identities are distinct. Randomized gene labels
avoid truth-favoring tie resolution. The report includes all scenarios, top-k truth precision,
recall, average precision, reference replication, and paired Monte Carlo mean-difference intervals.
Intervals describe this constructed model, not the real TCGA/GTEx gene population.

The shared-normal-bias scenario is a deliberate identifiability counterexample: confounding shared
by both reference populations can yield perfect reference agreement and very poor truth recovery.
The null still forces top-k selection; it does not establish discovery error control. Strong clean
signals also yield saturated endpoints, limiting the evidence for a more complex ranking rule.

Build a hash-verified review bundle, keeping all methods and top-k results:

```bash
.venv/bin/python -m src.operations.research_review \
  --studies outputs/research/native_reference_pilot_v2 \
            outputs/research/native_reference_paired_pilot_v1
```

Use the completed `native_reference_v1` and corrected `native_reference_paired_v2` once the
corrected full paired run completes.
The review remains explicitly research-incomplete and does not update manuscript/release readiness.
Pilot holdouts have been inspected; later analyses on these cohorts must disclose that history
rather than claim untouched confirmatory validation. Parameters of the full profile were set before
the pilot results, and no performance-driven retuning has been performed.

### Paired-subsampling protocol correction

The first paired protocol kept patients matched for cohort selection and bootstrap draws but
subsampled tumor and adjacent-normal development columns independently. Its ranking/holdout
evaluations remain traceable, but its sensitivity grid must not be described as pair-preserving.
The corrected protocol draws the same case identities for both groups in every development
subsample, independently drawing the balanced GTEx donors. Tests cover reordered sample columns
and reject unmatched or duplicate identities. Ranking parameters have not been retuned.

Original artifacts are retained. The original implementation is archived under
`outputs/research/protocol_sources/73429ce3b64c08e29850cac110a140ae230208ef3da518de71f27a2d3a939dcb/`.
Current configs use new immutable identifiers: `native_reference_v2`, `native_reference_pilot_v3`,
`native_reference_paired_v2`, and `native_reference_paired_pilot_v2`. These do not overwrite the
completed native v1 or earlier pilots; their plans record the original implementation fingerprint.
The unpaired native logic is unchanged. The corrected full paired run is the required source for
paired-subsampling claims.

### Separate-environment reproduction

The existing Docker image reproduced the pilot in an isolated output root. Comparison requires
matching configuration, implementation fingerprint and input checksums, plus exact schemas and
identifiers and fixed floating-point tolerances (`atol=1e-10`, `rtol=1e-8`). All heldout metrics and
candidate ranks matched exactly; three sensitivity Spearman cells differed by approximately
6.14e-9 and failed the fixed tolerance. That failure is retained with numeric diagnostics in
`outputs/research/environment_reproduction.json`, not converted into a pass by posthoc tolerance
adjustment. This is same-author environment reproduction, not an independent investigator's
scientific validation. Platform and dependency differences are observed, not causally isolated.

### Additional evaluation

The primary experiment controls the tumor set across references but is not restricted to matched
patients. The separate `paired_only: true` configuration restricts TCGA to patients with both tumor
and adjacent-normal samples before partitioning, then selects identical patient sets for both
groups within each partition. GTEx donor counts are balanced against the selected pair counts.
Bootstrap draws preserve TCGA case pairing. The reported rank-biserial effect remains a marginal
group effect, not a paired-test p-value; pairing controls cohort membership and resampling.
This arm is reported separately and is not independent biological validation.

Native/recount3 comparisons require verified specimen crosswalks; current zero TCGA
sample-ID overlap was an artifact of comparing external IDs directly. The recount3 metadata can
map some exact GDC sample UUIDs. The upstream GDC file is labeled controlled, while the processed
[recount3 release](https://rna.recount.bio/docs/index.html) is public. The crosswalk tool has an
explicit public-derived mode and reports only aggregate matches; it never downloads controlled
GDC files. In the current extract, 19 TCGA and 87 GTEx recount3 samples have unambiguous exact
matches to the native silver tables. Gene annotation, expression units and analytical comparability
still require separate checks. Separate processing does not create an independent biological cohort.

Run the aggregate-only crosswalk audit with:

```bash
.venv/bin/python -m src.analytics.recount3_crosswalk --allow-public-derived
```

Without this explicit flag, the audit rejects selected rows whose upstream GDC file is marked
controlled. The output `outputs/research/recount3_specimen_crosswalk_audit.json` contains no
individual identifiers. It records source file checksums, cohort counts and excluded duplicates.

The separate frozen `matched_processing_v1` study expands the exact match set to 417 TCGA tumors
and 200 GTEx normals from cached public processed recount3 data. Its new silver table preserves
`_PAR_Y` loci and passes unique specimen-gene-key validation. Median within-specimen gene ranks
are correlated, but top-50 cancer effect-rank overlap is only 0-0.020 and the native boundary has
hundreds of ties. This unfavorable, tie-sensitive result is reported in
`docs/research_evaluation_findings.md`; it does not justify an independent biological claim.

Before a competitive research submission, add external-cohort evaluation or an appropriately
independent simulation with known truth, compare with published ranking methods beyond the present
heuristics, and quantify engineering utility with actual injected failures and independent human
reproduction. Completing the local study is not proof of RECOMB-level novelty.
