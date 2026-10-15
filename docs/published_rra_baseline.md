# Published Robust Rank Aggregation Baseline

This completed post-v2 study compares the official `RobustRankAggreg` 1.2.1 implementation against the
existing native and patient-paired global reference studies. It does not revise those frozen
studies, the matched-processing studies, or their reviews. It is exploratory, not independent
confirmation or biological validation.

## Run

```sh
make build-published-rra
make prepare-published-rra
make run-published-rra
make build-published-rra-review
```

The first step requires Docker Desktop and network access to build the R image. `prepare` locks
the local image content digest, package version, seed `20261015`, source hashes, input hashes,
and existing study/manifest hashes before any metrics. If Docker is unavailable, no official
RRA result may be reported. A changed image, code file, input, or frozen study requires a new
study ID; do not overwrite `published_rra_baseline_v1`.

The Python coordinator checks the existing selected specimens, globally separated case/donor
partitions, development-only gene filter, candidate lists, and heldout metrics against their
frozen artifacts. It sends complete adjacent and GTEx gene ranks to the official R package,
then evaluates top-25/50/100 on the same heldout samples with paired case/donor resampling.
Intermediate gene ranks and scores remain under `data/research/`. Only aggregate comparisons,
hashes, cohort counts, and limitations enter the new `global_evidence_review_v4` bundle.

RRA is used **only as a ranking baseline**. The two ranked lists share tumor specimens, so its
independent-list null does not justify calibrated p-values here. Its score is not a differential-
expression p-value, FDR, or clinical evidence. Direction-discordant selections are retained and
reported, not silently filtered. Earlier `rra_style` results remain a separate heuristic.
The new report includes its top-k overlap with the official implementation. For two complete
lists and approximate scoring, the formulas may be nearly equivalent; a high overlap must be
reported as baseline redundancy rather than additional independent-method support.

This comparison does not close the external-workflow, independent-human-reproduction,
biological-validation, or novel-method gaps. Publication remains disabled.

## Observed Result

The official container run completed all six cancer/study cells and 18 top-k comparisons.
At top-50, the proposed method minus published RRA heldout replication fraction was
0.02-0.10 across the six cells; the paired descriptive interval includes zero for one cell.
The official RRA versus earlier `rra_style` top-50 Jaccard was 0.515-0.887, so they are
related but not interchangeable under their different tie rules. Between zero and four of
each RRA top-50 set had conflicting reference-effect directions. This result does **not**
establish an advantage over maximin: the corrected prior full studies found no top-50
lower-quantile replication advantage over that simpler baseline in any cancer.

The aggregate results are in `outputs/research/published_rra_baseline_v1/` and the separate
hash-verified `outputs/research/global_evidence_review_v4/`. No individual specimen IDs occur
in those new aggregate files. These are conditional heldout comparisons, not external
biological confirmation or evidence that RRA scores are valid p-values here.
