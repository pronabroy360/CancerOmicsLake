# Independent Biological Review Checklist

An independent cancer genomics or computational biology reviewer should complete this checklist
before any presubmission enquiry. Engineering authors should not self-approve it.

## Reviewer Identity

- Name, affiliation, ORCID, review date, and conflicts are recorded.
- The reviewed Git commit and manuscript evidence commit are recorded.
- The reviewer confirms access to the manuscript, tables, supplements, and evidence ledger.

## Expression Evidence

- TCGA tumor, TCGA adjacent normal, GTEx, and recount3 cohorts are described correctly.
- Expression units and workflow differences are not presented as directly exchangeable.
- Cross-source comparisons are described as sensitivity analyses, not definitive batch correction.
- Adjacent normal is not described as healthy tissue.
- Multiple-testing correction scope and effect-size definitions are appropriate.

## Mutation Evidence

- Protein-altering consequence groups are biologically defensible and documented.
- The profiled-sample denominator matches the downloaded mutation cohort.
- Mutation frequency is not interpreted as driver status, pathogenicity, or druggability.
- Capped mutation acquisition is visible in the limitations.

## Candidate And Pathway Evidence

- Prioritized and watchlist labels are treated as hypotheses, not biomarkers.
- Directional discordance and rejection reasons are visible.
- Bootstrap rank intervals are interpreted as uncertainty rather than validation.
- Reactome over-representation limitations, gene dependence, and publication bias are stated.
- No pathway enrichment result is described as pathway activation or mechanism.

## Multi-Reference Evaluation

- The shared gene universe and top-k construction are scientifically reasonable.
- Jaccard, direction concordance, and Spearman statistics answer distinct questions.
- Component ablation is not described as complete source removal.
- The conclusion that short lists are more reference-sensitive than global effects is supported by
  the supplied tables and is not generalized beyond the evaluated cohorts.

## Claims And Ethics

- Title, abstract, results, discussion, and conclusion respect the same claim boundary.
- No clinical, causal, therapeutic, diagnostic, or survival claim is present.
- Open-access and aggregate-publication rules are correctly represented.
- Demographic or individual-level information is not exposed.
- The reviewer identifies any gene-specific statement requiring literature validation.

## Decision

Choose one:

- `approved`: no biological correction is required.
- `approved_with_revisions`: listed revisions must be completed and checked.
- `not_approved`: claims or methods require substantial revision.

Copy `docs/attestations/biological_review.example.yml` to
`docs/attestations/biological_review.yml` only when a real reviewer is engaged. Never fabricate or
pre-fill an approval.
