# Four-page PhD interview research brief

Prepared for discussion as of **19 October 2026**. This summary covers the
platform, the main biological sensitivity studies, numerical/external workflow
evaluation and subsequent exploratory method experiments. It is a research
portfolio brief; its scope and remaining scientific requirements are stated in
the document.

- `brief.pdf`: the compiled four-page document to read or share.
- `brief.tex`: editable LaTeX source; letter paper, 10-point text.
- `evidence_values.tex`: generated numerical values and cohort table.
- `matched_metrics.dat`: aggregate values used by the PGFPlots figure.
- `evidence_ledger.json`: claim sources, extraction boundaries and SHA-256 hashes.
- `latex_source.zip`: the LaTeX inputs, data, ledger and README in one archive.

Build from the repository root:

```sh
make build-interview-brief
```

The build requires the existing Python environment, `tectonic`, `pdfinfo` and
`pdftotext` (Poppler). Tectonic downloads missing standard LaTeX packages on the
first build. A conventional LaTeX installation can instead compile `brief.tex`
from this directory once the generated data files exist.
For Overleaf, the archive contains all document inputs; set `brief.tex` as the
main document. The source uses standard LaTeX packages, including PGFPlots.

The builder verifies the focused manuscript and frozen v5 files, regenerates
numbers from checked aggregate sources, compiles the source, requires exactly
four pages and no overfull boxes, and scans the source/PDF against known private
specimen identifiers. The plot uses separate scales for Kendall correlation and
top-list Jaccard; those quantities are not interchangeable. Manual visual review
also checks legibility and page boundaries.

The older `manuscript/` draft is historical. The focused quantitative manuscript
remains at `outputs/research/focused_engineering_review_v1/`; the brief adds the
later feasibility outcomes without rewriting frozen studies. Recorded source
hashes identify the working files, rather than asserting a clean release commit.

Affiliation and correspondence are omitted because exact wording was not
confirmed. Independent investigator reproduction, full author declarations and
publication approval remain pending. The brief contains aggregate results.
