# Publication Strategy

Verified against official journal guidance on 2026-07-26.

## Recommended Route

### 1. GigaScience Technical Note - primary target

This is the best current fit because the contribution is an open, tested computational method for
handling large-scale biomedical data. GigaScience evaluates reproducibility, usability, and utility,
and its Technical Notes cover open-source tools and computational methods for large-scale data.

Current strengths:

- Open-source implementation with Docker, tests, CI, test fixtures, and documentation.
- Real TCGA, GTEx, recount3, mutation, pathway, and graph evidence.
- FAIR aggregate release with checksums, schemas, provenance, and identifier audits.
- Explicit multi-reference sensitivity and component-ablation evaluation.

Submission blockers:

- Complete the preregistered comparison against existing community tools.
- Deposit a frozen code/data release and add its DOI.
- Obtain independent biological review.
- Complete author, affiliation, funding, conflict, and AI-assistance disclosures.
- Confirm that a fresh reviewer machine can execute the defined demonstration.

Official criteria:

- [GigaScience Technical Note criteria](https://academic.oup.com/gigascience/pages/technical_note)
- [GigaScience author instructions](https://academic.oup.com/gigascience/pages/instructions_to_authors)
- [GigaScience minimum reporting checklist](https://academic.oup.com/gigascience/pages/minimum_standards_of_reporting_checklist)

### 2. Bioinformatics Advances Application Note - secondary target

The software, database/ontology, data-mining, visualization, and cancer categories fit. The main
risk is novelty: its software scope rejects straightforward application of established methods and
expects a substantial methodological advance. An Application Note is also limited to four pages,
200 abstract words, ten references, and three figures or tables.

Use this route if the comparative evaluation demonstrates a clear workflow capability that existing
tools do not provide and the manuscript can be compressed around that capability.

- [Bioinformatics Advances author guidelines](https://academic.oup.com/bioinformaticsadvances/pages/author-guidelines)

### 3. Database - conditional target

Database welcomes biological database and database-tool descriptions and encourages a biological
discovery or testable hypothesis. It requires an openly available web resource without login and
expects availability for at least two years. This route becomes credible only after a stable public
deployment, maintenance commitment, and biological collaborator sign-off.

- [Database instructions for authors](https://academic.oup.com/database/pages/instructions_for_authors)

### 4. Journal of Open Source Software - later software paper

JOSS is not the immediate route. Its current screening requires more than six months of public
development, demonstrated research use, iterative open history, and strong open-source practices.
It also requires the software paper not to focus on new research results. Revisit after sustained
public development and external adoption.

- [JOSS submission requirements](https://joss.readthedocs.io/en/latest/submitting.html)
- [JOSS paper format](https://joss.readthedocs.io/en/latest/paper.html)

## Claim Positioning

Use:

> CancerOmicsLake is a provenance-aware data engineering and evaluation method that integrates
> established cancer-omics resources and quantifies candidate sensitivity to normal-reference
> choice.

Do not use:

- "Novel biomarker discovery"
- "Validated therapeutic target"
- "Batch effects eliminated"
- "Driver mutation identification"
- "Clinical decision support"
- "Causal cancer mechanism"

## Submission Sequence

1. Execute `docs/comparative_evaluation_protocol.md`.
2. Obtain review using `docs/biological_review_checklist.md`.
3. Create a frozen GitHub release and DOI-backed software/data deposits.
4. Complete all manuscript placeholders and AI-assistance disclosure.
5. Run `make run-submission-readiness-strict`.
6. Send a short presubmission enquiry to GigaScience describing the Technical Note fit.
7. Format the accepted draft using the journal template only after editorial fit is confirmed.

The executable gate confirms packaging readiness, not acceptance probability or biological truth.
