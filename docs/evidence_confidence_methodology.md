# Evidence Confidence Methodology

## Research Question

Can a cancer-gene ranking distinguish candidate importance from the reliability of the data supporting that rank?

`gold_candidate_gene_priority` estimates exploratory importance. `gold_cancer_gene_evidence_confidence`
separately estimates whether the available mutation, expression, graph, integrity, and provenance evidence is
sufficiently supported to interpret that priority score. The confidence score is a transparent engineering
calibration, not a probability of biological truth or clinical validity.

## Components

All component scores are bounded to `[0, 1]`.

- Mutation confidence combines profiled-sample support and mutated-sample support:
  `0.55 * min(profiled_samples / 100, 1) + 0.45 * min(mutated_samples / 20, 1)`.
- Batch-sensitivity confidence compares the raw fold-change direction with the within-cohort rank/robust-z
  direction. High-support concordance scores `1.0`; directional discordance scores `0.0`.
- Expression confidence combines tumor and normal sample support, keeps a `0.5` ceiling, and multiplies it by
  `0.5 + 0.5 * batch_sensitivity_confidence`. Agreement can retain the ceiling; discordance halves it.
- Graph confidence combines presence of a cancer-gene relationship edge and normalized gene degree.
  It is structural corroboration and must not be presented as independent biological validation.
- Quality confidence verifies row-level frequency, denominator, and sample-count integrity.
- Traceability confidence measures the non-stub provenance ratio of contributing source rows.

When mutation and expression evidence both exist, biological confidence uses `60%` mutation and `40%`
expression confidence. When only one modality exists, the available modality is used without imputing the
missing modality.

The final calibration is:

```text
overall_confidence =
    0.750 * biological_confidence
  + 0.100 * graph_confidence
  + 0.075 * quality_confidence
  + 0.075 * traceability_confidence
```

Tiers are `high >= 0.75`, `moderate >= 0.50`, `limited >= 0.25`, and `low < 0.25`.

## Guardrails

- Every TCGA-GTEx comparison remains `high` or `elevated` batch risk until harmonized processing exists;
  sensitivity concordance never produces a low-risk label.
- Raw directions use `raw_up` at log2 fold change >= 1, `raw_down` at <= -1, and `raw_stable` otherwise.
- Concordance is `concordant`, `discordant`, `inconclusive`, or `unavailable`, with machine-readable caveats.
- Sparse tumor, normal, or mutation denominators generate machine-readable caveats.
- Missing or stub-like provenance lowers traceability confidence.
- Priority and confidence remain separate fields so strong effects cannot hide weak support.
- Dashboard and API responses explicitly prohibit clinical interpretation.

## Validation Plan

Before publication, the weighting and thresholds should be treated as preregistered hypotheses and tested by:

1. Sensitivity analysis over component weights and support thresholds.
2. Bootstrap stability of cancer-gene ranks across sample resamples.
3. Comparison with batch-corrected recount-style TCGA-GTEx expression data.
4. External concordance against independent cancer cohorts and curated driver-gene resources.
5. Ablation analysis showing the contribution of mutation, expression, graph, and provenance components.
6. Calibration plots comparing confidence tiers with rank reproducibility under held-out samples.

The potentially publishable contribution is the provenance-aware, modality-separated evaluation framework and
its empirical validation. Novelty must be established through a formal literature review before making a novelty claim.

## Current Data Readiness

The live GTEx V8 profile now contributes 50 breast, 50 lung, 50 transverse-colon, and 50 sigmoid-colon samples,
covering 56,200 source genes per tissue. The current tumor-vs-normal mart contains 36,004 intersecting genes per
cancer project. Normal-reference support is adequate for engineering and exploratory work, but the comparison
remains batch-effect limited. Current aggressive TCGA STAR-TPM support is 95 BRCA, 94 LUAD, and 96 COAD tumor
samples, which is adequate for stronger exploratory evidence scoring. Batch-aware modeling remains the primary
prerequisite before making publication-grade biological claims.

The first batch-sensitivity layer is documented in `docs/batch_effect_sensitivity.md`. It adds
within-cohort rank and robust-z deltas as a scale-reduced sensitivity analysis, but it is still
not equivalent to full batch correction. Evidence confidence now consumes its directional concordance
as a conservative penalty, making disagreements directly auditable rather than hiding them in one risk label.
