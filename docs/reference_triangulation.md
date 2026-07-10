# Reference Triangulation Methodology

## Research Question

Does a cancer-gene expression direction remain stable when the normal reference changes from
TCGA solid-tissue adjacent normal to GTEx healthy tissue?

## Contrasts

`gold_reference_triangulation` computes three median-TPM contrasts for each cancer and gene:

- TCGA primary tumor versus TCGA solid-tissue normal.
- TCGA primary tumor versus mapped GTEx normal tissue.
- TCGA solid-tissue normal versus mapped GTEx normal tissue.

All contrasts use `log2((median TPM + 1) / (reference median TPM + 1))`. Directions are `up`
at log2 fold change >= 1, `down` at <= -1, and `stable` otherwise.

## Interpretation

- `concordant_up`, `concordant_down`, and `concordant_stable` indicate matching tumor directions
  under both normal references.
- `reference_sensitive` indicates that one reference produces a stable direction while the other
  crosses an effect threshold.
- `discordant` indicates opposing up/down directions and should block biological prioritization
  until investigated.
- `log2_fc_tcga_normal_vs_gtex` estimates the normal-reference shift for audit purposes; it is not
  a pure batch-effect estimate because adjacent normal and healthy donor tissue differ biologically.

`reference_stability_score` combines TCGA-normal sample support, directional agreement, and effect
similarity. It is an engineering calibration in `[0, 1]`, not a probability of biological truth.

## Guardrails

- TCGA adjacent normal can contain tumor-adjacent field effects and is not interchangeable with healthy tissue.
- GTEx and TCGA still differ in donor context, tissue collection, ischemic time, and study protocol.
- The mart tests reference sensitivity but does not remove all study effects.
- Bootstrap rank stability and uniformly reprocessed recount3 validation remain required before publication claims.

## Acquisition

Run `make run-metadata-strict` to query the dedicated open-access STAR adjacent-normal slice, then
`make run-download-tcga-normals`. The normal cap is independent of the tumor expression cap so
normal files cannot be displaced by deterministic file ordering.
