# Independent Biological Review Request

## Suggested Request

> I am seeking an independent biological/methodological review of CancerOmicsLake, an
> open-access-only TCGA-GTEx data-engineering and reproducibility project intended for a methods or
> technical-note submission. I am requesting review of biological interpretation, mutation
> consequence semantics, expression-comparison caveats, statistical claims, pathway interpretation,
> and the boundaries between engineering evidence and biological conclusions. This request does not
> ask the reviewer to validate a clinical biomarker or causal mechanism.

## Review Target

- Repository: `https://github.com/pronabroy360/CancerOmicsLake`
- Evidence-producing commit: `011de8b54019f7836893d1d2228b25f8eba041af`
- Manuscript package: `manuscript/`
- Claim ledger: `manuscript/evidence_ledger.json`
- Review checklist: `docs/biological_review_checklist.md`
- Attestation template: `docs/attestations/biological_review.example.yml`
- Comparative protocol: `docs/comparative_evaluation_protocol.md`

## Requested Checks

1. Are TCGA, GTEx, recount3, and adjacent-normal comparisons described with adequate collection,
   tissue-composition, and batch-confounding caveats?
2. Are protein-altering mutation categories and profiled-sample denominators represented correctly?
3. Are multiple-testing, bootstrap, consensus, and reference-ablation results interpreted within
   their actual estimands?
4. Are candidate and pathway outputs consistently framed as hypothesis-generating?
5. Do the abstract, results, discussion, figures, and tables avoid causal, clinical, diagnostic, or
   biomarker-validation overclaims?
6. Are important biological limitations or alternative explanations missing?

## Handoff

The reviewer should record required revisions and only set `status: approved` after reviewing the
actual commit and all required checklist sections. Copy the completed attestation to
`docs/attestations/biological_review.yml`.

Authorship is not implied by review alone. Discuss authorship separately using the target journal's
contribution criteria. The engineering author must not self-approve this attestation.
