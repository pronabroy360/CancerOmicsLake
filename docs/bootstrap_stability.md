# Candidate Bootstrap Stability Methodology

## Research Question

Which prioritized cancer-gene signals retain their expression direction and rank when tumor,
TCGA adjacent-normal, and GTEx normal samples are resampled?

## Candidate Cohort

The default run uses the union of:

- The top 500 `gold_candidate_gene_priority` rows per cancer.
- Every `high` row from `gold_cancer_gene_evidence_confidence`, even when outside the top 500.

Each output row records `candidate_selection_reason` as `top_priority`, `high_confidence`, or
`top_priority_and_high_confidence`. This prevents strong mutation-supported candidates from
silently escaping expression-stability review.

Candidate selection controls which rows are published, not which genes participate in ranking.
Every gene available in the cancer-specific priority table and all three expression matrices forms
the eligible ranking universe. The output records its post-intersection size as
`ranking_universe_gene_count`.

## Resampling

For each cancer, 200 deterministic nonparametric bootstrap iterations independently sample with
replacement from:

- TCGA primary tumors.
- TCGA solid-tissue adjacent normals.
- Mapped GTEx normal tissues.

Each iteration recomputes median TPM, tumor-versus-normal log2 fold change, effect-magnitude rank,
direction, and top-50 membership under both normal references. Ranks and top-k membership are
calculated over the full eligible gene universe before candidate rows are selected for output. The
default seed is `20260710`, with fixed project-specific offsets.
Random draws are generated before execution and evaluated with four workers by default, preserving
deterministic results while parallelizing the expensive full-universe median calculations.

## Outputs

- Direction stability under each reference.
- Cross-reference direction-concordance and opposite-direction rates.
- Top-k selection probabilities.
- Median ranks and 95% percentile intervals.
- Median log2 fold changes and 95% percentile intervals.
- Rank precision derived from normalized rank-interval width.

The stability score is:

```text
0.25 * tcga_direction_stability
+ 0.25 * gtex_direction_stability
+ 0.25 * reference_concordance_rate
+ 0.25 * rank_precision
```

Tiers are `high >= 0.8`, `moderate >= 0.6`, `limited >= 0.4`, and `unstable < 0.4`.

## Guardrails

- Output is candidate-restricted, but expression-effect ranking uses the full eligible gene universe.
- This does not bootstrap the upstream priority score, evidence tiers, mutation component, or complete
  consensus-selection algorithm, and it is not a genome-wide differential-expression test.
- Resampling measures sensitivity to the observed samples; it cannot detect biases shared by all samples.
- Adjacent normal is tumor-proximal tissue and is not equivalent to an independent healthy control.
- The score is not a probability of biological truth, clinical utility, or external replication.
- Uniformly reprocessed recount3 validation remains the next independent processing benchmark.

## Current Run

The current 200-iteration run ranks 36,004 jointly available genes per cancer before publishing 500
candidate rows per cancer. Across the 1,500 published rows, 713 are bootstrap-high, 782 moderate,
and five limited. The current evidence-confidence mart contains no `high` rows requiring forced
inclusion outside the top-500 cohort.
