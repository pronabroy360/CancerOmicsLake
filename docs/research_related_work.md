# Related Work and Contribution Boundaries

## External preparation comparison (2026-10-15)

The separate cached-input benchmark uses the actual preparation implementation from
[`tcga-data-nf` at the pinned commit](https://github.com/QuackenbushLab/tcga-data-nf/tree/1069eb9c01b97640fd532ffac8551096d2a2790a).
Its installed NetworkDataCompanion functions apply edgeR TMM normalization and inclusive
expression/prevalence filtering. Both measured paths share that normalization backend;
the CancerOmicsLake Polars adapter is a benchmark extension. Therefore this is an
interoperability, repeatability and bounded preparation-cost comparison, not independent
normalization-method validation or an end-to-end Nextflow speed comparison. Native-script
integration and module timing have separate outcomes. See `docs/engineering_completion.md`.

The completed post-v2 RRA comparator uses the official package only for **ranking**, with full
adjacent-normal and GTEx lists on the same development genes. Shared tumor specimens invalidate
an independent-list-null interpretation of its scores as significance. Its container run and
hash-verified v4 review are complete. The lower-quantile method showed better top-50 heldout
replication than RRA in six cells, but not an advantage over simple maximin in the corrected
prior full studies. This is a bounded baseline result, not a novel-method claim.

Reviewed 2026-10-04 using primary papers. This is a targeted literature assessment, not an
exhaustive systematic novelty search. A unique combination of technologies is not automatically
a research advance.

| Existing work | Overlap | What CancerOmicsLake must demonstrate |
| --- | --- | --- |
| [GEPIA2 (2019)](https://doi.org/10.1093/nar/gkz430) | TCGA/GTEx integration, interactive expression analysis, API | Added value in auditable acquisition, warehouse contracts and reference-sensitivity evaluation; integration alone is established. |
| [tcga-data-nf (2025)](https://doi.org/10.1093/gigascience/giaf126) | Reproducible TCGA multiomic processing, recount3/GTEx acquisition, containers, metadata and networks | Direct workflow comparison of lineage, denominator semantics, recovery and reproducibility; its networks have a different analytical purpose. |
| [Wang et al. (2018)](https://doi.org/10.1038/sdata.2018.61) | TCGA/GTEx harmonization and study-specific confounding | Separately controlled cohort, reference and processing effects; the existence of batch effects is established. |
| [Arora et al. (2020)](https://doi.org/10.1038/s41598-020-59516-z) | Pipeline differences in estimated gene expression | Matched sample and gene comparisons before attributing rank changes to processing or reference. |
| [Kolde et al. (2012)](https://doi.org/10.1093/bioinformatics/btr709) | Robust rank aggregation of gene lists | Comparison against published aggregation approaches; a lower-quantile or maximin score is not automatically a new method. |
| [Meinshausen and Buhlmann (2010)](https://doi.org/10.1111/j.1467-9868.2010.00740.x) | Subsampling-based stability selection | Do not transfer its error-control results to the present scoring heuristic without proving its assumptions and guarantees. |

## Candidate contribution

CancerOmicsLake can be positioned as a provenance-aware engineering and evaluation framework for
reference-sensitive cancer-omics prioritization. The empirical question is whether a prespecified,
reference-aware selection strategy improves heldout reproducibility compared with single-reference
and aggregation baselines at comparable output sizes and across all evaluated cancers.

The existing low top-list overlap is descriptive evidence. Global expression scale, pseudocount,
small or differently selected cohorts and tissue composition can contribute to that overlap. A
controlled experiment must establish which conclusions survive these alternatives. Reprocessing
corroboration must not be called external biological validation.

## Evaluation obligations

Report the actual execution status of each comparator task. The current comparison gate checks
evidence completeness, including partial results; it does not prove that all tasks succeeded or that
CancerOmicsLake outperforms another tool. Add tcga-data-nf to the workflow comparison and implement
equivalent tasks before claiming an engineering advantage. Acquisition metadata counts, downloaded
files, successfully parsed files and profiled biological units need separate labels and denominators.

RECOMB suitability requires a substantial supported computational contribution. A software or
technical-note route can instead be supported by demonstrable utility and reproducibility. Decide
between those routes after inspecting the controlled experiment, not by selecting favorable results.
