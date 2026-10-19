# CancerOmicsLake research synopsis, revision 2

Updated 19 October 2026 for PhD outreach/interview discussion. This four-page
synopsis develops one central argument: broad effect concordance, top-list
stability and numerical acceptance are different properties of a research result.
The platform and executed sensitivity studies provide the evidence.

- `brief.pdf`: revised four-page PDF.
- `brief.tex`: editable LaTeX source.
- `evidence_values.tex` and `matched_metrics.dat`: generated aggregate values.
- `evidence_ledger.json`: claim sources, boundaries and artifact hashes.
- `latex_source.zip`: all LaTeX inputs and the evidence ledger.
- `reviewer_notes.md`: document review, corrections and remaining research limits.

```sh
make build-interview-brief
```

Revision 2 was generated with a project-local builder that requires the full
local frozen evidence cache, the project Python environment, Tectonic and
Poppler (`pdfinfo`, `pdftotext`). The cache is not distributed in this
public-facing package. The source archive can be compiled independently with a conventional LaTeX
installation or Overleaf, using `brief.tex` as the main document. Standard
TikZ/PGFPlots packages supply the diagrams and scientific plots; no external
image assets are needed.

Figures 1 and 2 show implemented dependencies and the matched processing design.
Figure 3 shows observed metrics with descriptive 95% paired-bootstrap intervals.
The top-list intervals concern tie-averaged overlap and differ from the separate
tie-only quantiles. The two panels have different axes and statistics.

Revision 1 is retained under `manuscript/interview_brief/`. The new version adds
diagrams, uncertainty intervals, reference-study group sizes and numerical
failure denominators. It retains the full research trajectory and unfavorable
results. No underlying study or frozen evidence was changed.

The builder verifies the focused manuscript and frozen sources, claim hashes,
four-page count, layout and known private identifiers. This is an outreach
synopsis backed by the repository's detailed methods and evidence. Independent
human reproduction, causal/biological validation and confirmed author
declarations remain outstanding. Improved presentation does not satisfy those
research requirements.
