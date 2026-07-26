# Multi-Reference Ablation Evaluation

## Research Question

How sensitive are cancer-gene rankings and consensus candidates to the choice of normal reference
and to explicit reference-related components in the prioritization score?

This is a reproducibility and methodological-sensitivity evaluation. It does not identify a true
normal reference or establish biological, causal, or clinical validity.

## Direct Reference Comparison

The evaluation intersects genes available for all three methods within each cancer:

- `gtex_native`: native TCGA tumor versus GTEx healthy tissue.
- `tcga_adjacent`: native TCGA tumor versus TCGA adjacent normal.
- `recount3_uniform`: TCGA tumor versus GTEx normal from uniformly processed recount3 data.

Genes are deterministically ranked by absolute log2 fold change, breaking ties by gene symbol. Each
method pair is evaluated using:

- top-k overlap and Jaccard similarity,
- direction concordance among top-k overlaps,
- direction concordance over the common universe,
- direction concordance over the union of genes called up or down by either method,
- Spearman association of absolute effects,
- median absolute effect-magnitude difference.

Metrics are calculated separately for BRCA, COAD, and LUAD. To avoid dependence on one arbitrary
candidate-list cutoff, the default evaluation uses `top_k` values 25, 50, 100, and 250.
The agreement tier uses regulated-union direction concordance rather than stable-stable agreement.

## Consensus Component Ablation

The baseline consensus score has eight explicit weighted components. Four scenarios are evaluated:

- remove reference triangulation,
- remove external recount3 validation,
- remove paired TCGA support,
- remove all three explicit reference-related components.

After removal, retained weights are renormalized to sum to one. The ablated score is compared with
the baseline using top-k Jaccard, score association, rank displacement, score deltas, and retention
of baseline prioritized candidates under the unchanged full-model threshold. Fixed-threshold
retention is reported descriptively but does not determine the robustness tier because the threshold
was calibrated for the complete score.

This is a component ablation, not complete source removal. Priority, confidence, bootstrap, and
statistical components can retain upstream dependence on native or recount3 expression. The output
records this limitation explicitly.

## Reproduction

```bash
make run-reference-ablation
```

Outputs:

```text
data/gold/gold_reference_method_comparison.parquet
data/gold/gold_consensus_ablation_stability.parquet
outputs/reports/reference_ablation_report.json
```

The report records input paths, row counts, byte sizes, SHA-256 hashes, Git commit, component
weights, ablation definitions, direction threshold, and tier thresholds.

## Current Real-Data Acceptance

The current run evaluates 36,004 common genes per cancer, three method pairs, three cancers, and
four candidate-list sizes, producing 36 pairwise comparisons and 48 component ablations.

- Absolute-effect Spearman associations range from 0.618 to 0.812.
- Regulated-union direction concordance ranges from 0.124 to 0.396.
- Direct-reference top-k Jaccard ranges from 0.010 to 0.370.
- All 36 direct comparisons are `limited` under the predefined engineering tier.
- Single-component ablation score associations range from 0.780 to 0.956.
- Removing all three explicit reference components reduces score association to 0.672-0.700 and
  top-k Jaccard to 0.020-0.575 across cancers and list sizes.

These results show that genome-wide effect magnitudes can remain correlated while short candidate
lists are highly reference-sensitive. They support conservative multi-reference filtering, not a
claim that one reference is correct.

## Interpretation Guardrails

- Higher agreement means rankings are less sensitive to the tested reference change; it does not
  prove absence of confounding.
- TCGA adjacent tissue can contain field effects and differs biologically from healthy donor tissue.
- Uniform recount3 processing reduces pipeline differences but not cohort or collection differences.
- Engineering tiers are transparent summaries, not probabilities or clinical grades.
- Results should be reported for each cancer, not pooled into one pan-cancer statistic.
