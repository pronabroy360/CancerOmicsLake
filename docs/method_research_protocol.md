# Subsequent Computational-Method Research Protocol

Status: design requirements only. No new algorithm or novelty claim is asserted by this document.

## Scientific target

A future method must improve on simple reference maximin under explicit assumptions. Beating RRA
alone is insufficient: the corrected existing studies showed no top-50 advantage over maximin.
The engineering paper and all observed candidate results remain the development record.

## Required assumptions and failure cases

The method must state its estimand, what reference populations represent, and which sources of
dependence it handles. Existing tests must cover clean data, GTEx-specific bias, adjacent-specific
bias, shared-normal bias and the null. Additional constructed cases must address correlated
reference errors, unequal sample sizes, detection censoring, saturated/tied effects, variable
sample composition and annotation/mapping failures. Shared reference agreement cannot identify
biological truth when every reference shares the same bias. Any proposed guarantee must either
prove identifiability under stated assumptions or require additional information.
Numerical tie/equivalence rules must be defined before new evaluation; rounding inspected effects
or widening the old tolerance to eliminate observed discrepancies is not a valid confirmation step.

## Evaluation and separation

Compare maximin, the current lower-quantile score, single-reference effects, mean ranks and the
official RRA ranking implementation at the same top-25/50/100 sizes. Keep case/donor groups together
globally and fit filters/settings using development data only. Report truth precision, average
precision, worst-reference replication, selection stability, failures, runtime and memory.
Reference replication is not a substitute for truth recovery in constructed data.

Existing native, paired and matched-processing holdouts have been inspected and cannot become an
untouched confirmation set by renaming a study. A new confirmatory protocol requires an independent
cohort or new data partition that has not influenced algorithm choices, with sample-size planning
and a justified primary endpoint before access. All current synthetic scenarios are development
scenarios; genuinely new simulation scenarios/seeds must be frozen before their confirmatory use.

## Go/no-go gate

Proceed toward a methods manuscript only after a fixed method and theorem/assumptions or clear
algorithmic advance are documented, it improves on maximin on the prespecified primary endpoint
with uncertainty, and favorable results survive the named failure cases. Retain shared-bias and
null failures. If improvement is absent, publish the engineering/sensitivity evidence with the
negative result and continue method development separately. Biological or clinical claims require
their own evidence and expertise; none is inferred from the present candidate ranking.
