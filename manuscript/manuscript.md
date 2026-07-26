# CancerOmicsLake: a provenance-aware multi-reference data lakehouse for reproducible cancer-omics research

**Manuscript status:** Methods/data-engineering draft generated from validated artifacts on 2026-07-26T04:36:25.528059+00:00.

**Author:** Pronab Chandra Roy

**Affiliation:** [AUTHOR TO COMPLETE]

**Corresponding email:** [AUTHOR TO COMPLETE]

## Abstract

**Background:** Public cancer-omics resources are large, heterogeneous, and sensitive to metadata,
processing, and normal-reference choices. Reproducible infrastructure is required before candidate
genes or pathways can be interpreted.

**Methods:** We developed CancerOmicsLake, an open-access-only lakehouse integrating TCGA breast
invasive carcinoma, colon adenocarcinoma, and lung adenocarcinoma with GTEx V8, uniformly processed
recount3 expression, and Reactome pathways. The platform implements bronze, silver, and gold data
contracts; DuckDB/dbt analytics; provenance and checksum capture; consequence-stratified mutation
summaries; quality gates; public-safe graph exports; and multi-reference sensitivity evaluation.

**Results:** The evaluated local profile contains 2,098 TCGA
patients, 2,682 TCGA samples,
37,002,600 TCGA expression rows,
11,240,000 GTEx expression rows, and
34,393 protein-altering mutation records.
Across 36,004 common genes per cancer, pairwise absolute-effect
Spearman associations were 0.618-0.812, whereas
regulated-direction concordance was 0.124-0.396
and top-list Jaccard similarity across K=25, 50, 100, and 250 was
0.010-0.370. Removing all three
explicit reference-related consensus components reduced score association to
0.672-0.700. The public graph
contained 55,194 nodes and
253,543 edges after individual-level entities were removed.

**Conclusions:** Genome-wide effect rankings can remain moderately correlated while short candidate
lists and regulated directions remain reference-sensitive. CancerOmicsLake contributes a
reproducible engineering and evaluation framework for conservative hypothesis generation, not a
clinical biomarker or causal discovery claim.

**Keywords:** bioinformatics data engineering; TCGA; GTEx; recount3; lakehouse; reproducibility;
knowledge graph; reference sensitivity

## 1. Introduction

The Cancer Genome Atlas (TCGA) established a foundational multi-omic resource for cancer research
[1], while GTEx created a broad reference atlas of non-diseased human tissue expression [2].
Integrating these resources is attractive for tumor-normal exploration but creates risks from
metadata heterogeneity, gene-identifier mismatch, distinct processing pipelines, tissue collection,
and cohort composition. Uniform resources such as recount3 reduce processing differences [3], but
do not remove biological or collection confounding.

Many exploratory analyses begin with notebooks that conceal acquisition decisions, incomplete
denominators, and changing candidate thresholds. CancerOmicsLake instead treats ingestion,
harmonization, validation, analytical modeling, and public release as first-class research objects.
The principal contribution is not a novel clinical biomarker model. It is an auditable
data-engineering method for assembling known analytical techniques into a reproducible,
multi-reference cancer-omics platform and quantifying how reference choice affects candidate lists.

## 2. Materials and Methods

### 2.1 Data sources and access policy

The study used open-access GDC data for TCGA-BRCA, TCGA-COAD, and TCGA-LUAD; GTEx V8 breast, lung,
transverse-colon, and sigmoid-colon expression; public recount3/Monorail summaries; and Reactome
release 97 pathway annotations [4]. Controlled-access files, credentials, and individual-level
public outputs were prohibited.

### 2.2 Lakehouse and warehouse architecture

Source files and acquisition metadata were retained in an immutable bronze layer. Typed,
identifier-normalized Parquet entities and facts formed the silver layer. Analysis-ready expression,
mutation, evidence, consensus, pathway, graph, and sensitivity marts formed the gold layer.
DuckDB and dbt provided local analytical execution and contract tests. Figure 1 summarizes the data
flow.

### 2.3 Expression harmonization

Ensembl version suffixes were removed while original identifiers were retained for audit. Expression
units and source workflows were explicitly labeled. Tumor-normal effects used log2 ratios with a
pseudocount of one. Native TCGA-GTEx effects were triangulated against TCGA adjacent normal and
uniformly processed recount3 effects. Adjacent normal was treated as a distinct reference that can
contain field effects, not as healthy tissue.

### 2.4 Mutation evidence

Open somatic mutation records were retained and grouped into protein-altering, synonymous,
non-coding/regulatory, and unclassified consequences. Candidate mutation evidence used only
protein-altering events and the downloaded mutation-profile cohort as denominator. This
consequence filter does not distinguish drivers from passengers or establish pathogenicity.

### 2.5 Statistical and stability evidence

Expression support used Mann-Whitney tests for independent source groups and Wilcoxon signed-rank
tests for case-matched TCGA tumor-adjacent pairs. Benjamini-Hochberg correction was applied within
cancer. Candidate rank uncertainty was assessed with 200 deterministic bootstrap iterations.
Consensus scores combined eight transparent components; discordant reference, external, statistical,
or paired evidence could explicitly reject a candidate.

### 2.6 Multi-reference and component-ablation evaluation

For each cancer, genes present under native GTEx, TCGA adjacent-normal, and recount3 contrasts were
intersected. Genes were ranked by absolute log2 fold change with gene-symbol tie breaking.
Pairwise top-list Jaccard, regulated-direction concordance, whole-universe absolute-effect Spearman
association, and effect differences were computed at K=25, 50, 100, and 250. Consensus sensitivity
was measured after removing reference-triangulation, external-validation, paired-support, or all
three explicit reference components and renormalizing retained weights. Non-ablated components can
retain upstream source dependence; therefore this is a component sensitivity analysis, not complete
source removal.

### 2.7 Pathway and graph layers

Reactome over-representation analysis used a post-intersection tested-gene background and
Benjamini-Hochberg correction within cancer and candidate set. The graph projected aggregate-safe
Gene, CancerType, Tissue, Dataset, and Pathway entities. Patient and Sample nodes remained internal
and were removed from API, dashboard, and release exports.

### 2.8 Quality, reproducibility, and release

The pipeline used configuration validation, checksums, schema/range/integrity checks, deterministic
selection, dbt tests, strict demo checks, and daily GitHub Actions. A FAIR release builder emitted
aggregate Parquet resources, schemas, SHA-256 hashes, provenance, citation metadata, and an
identifier-safety audit. All manuscript values were generated from the evidence ledger supplied
with this draft.

## 3. Results

### 3.1 Data processing and analytical products

CancerOmicsLake processed 3,444 TCGA files into
37,002,600 TCGA and
11,240,000 GTEx expression rows. The mutation layer retained
45,588 somatic records, including
34,393 protein-altering records across
126 downloaded mutation profiles.

### 3.2 Validation and candidate triage

External validation evaluated 108,012 cancer-gene pairs and marked
1,815 as directionally discordant. Matched TCGA analysis
evaluated 178,281 cancer-gene rows, including
25,544 paired-replicated results. The consensus layer evaluated
108,600 rows and retained 194
prioritized candidates and 4,875 watchlist candidates. These labels
are prioritization states rather than validated biomarkers.

### 3.3 Reference sensitivity

All three cancers had 36,004 genes in the common comparison
universe. Absolute-effect associations were moderate to high
(0.618-0.812), but regulated-direction agreement
(0.124-0.396) and candidate-set
Jaccard (0.010-0.370) were lower.
36 of 36 direct comparisons
were classified limited under the
predefined engineering tier (Figure 2; Supplementary Table S1).

### 3.4 Consensus ablation

Removing all explicit reference-related components yielded top-list Jaccard values of
0.020-0.575 and score
associations of 0.672-0.700.
Single-component removals were less disruptive but remained list-size and cancer dependent
(Figure 3; Supplementary Table S2). Fixed full-model threshold retention was reported
descriptively and did not determine robustness tiers.

### 3.5 Operational evidence

The quality gate recorded 58 passed checks and
0 warnings. The dbt model/test gate,
29 strict demo checks, and 9 project
milestones passed. Six warm DuckDB workloads had median
latencies of 0.264-4.758 ms in the
recorded single-machine environment. These timings demonstrate local responsiveness and are not a
cross-system performance comparison.

## 4. Discussion

The central empirical observation is that global effect magnitudes can correlate while top candidate
sets remain unstable. This distinction matters because candidate-focused studies frequently report
short lists rather than genome-wide agreement. The result argues against treating any single
tumor-normal reference as sufficient evidence and supports explicit triangulation, discordance
tracking, and ablation reporting.

The engineering contribution is the integration discipline: immutable acquisition records,
stable schemas, explicit denominators, open-access enforcement, uncertainty-aware candidate
ranking, public/private graph boundaries, and evidence-linked release packaging. This profile is
appropriate for a data or methods paper. It should not be framed as a new differential-expression
algorithm or a clinically validated biomarker study.

## 5. Limitations

1. TCGA and GTEx differ in collection, donor context, tissue composition, ischemic exposure, and
   processing; the analysis measures sensitivity but does not perform definitive batch correction.
2. recount3 reduces processing heterogeneity but does not remove cohort and biological confounding.
3. Mutation acquisition is capped and consequence stratification does not identify driver variants.
4. Pathway over-representation assumes a thresholded candidate set and does not account for gene
   dependence or pathway publication bias.
5. Component ablations do not remove every upstream dependency on a source.
6. No survival, drug-response, immune-deconvolution, or independent clinical endpoint is claimed.
7. Performance results come from one local environment and are not comparative benchmarks.

## 6. Conclusions

CancerOmicsLake demonstrates how open cancer-omics resources can be transformed into an auditable,
aggregate-safe research platform. Its multi-reference evaluation shows that candidate lists can be
substantially more fragile than genome-wide correlations imply. The platform is suitable for
reproducible hypothesis generation and data-engineering research, while downstream biological and
clinical validation remains necessary.

## Data and Code Availability

Code is available at https://github.com/pronabroy360/CancerOmicsLake. Raw source biomedical data are
not redistributed. A versioned aggregate-derived bundle can be generated with
`make build-fair-release`; a DOI must be added after repository deposit.

## Ethics and Compliance

Only open-access public resources were used. Controlled-access data were excluded. Public graph and
release surfaces remove Patient and Sample entities and block individual-like identifiers.

## Generative AI Disclosure

[AI DISCLOSURE TO COMPLETE] List the tools and model versions used for code, tests, documentation,
and manuscript drafting; describe the scope of assistance; and confirm that the human author
reviewed, edited, and validated all assisted outputs and retained responsibility for design choices,
scientific interpretation, and the submitted work.

## Author Contributions

**Pronab Chandra Roy:** Conceptualization, software, data engineering, methodology, validation,
visualization, and writing.
**Review and biological interpretation:** [COLLABORATOR TO COMPLETE]

## Competing Interests

[AUTHOR TO COMPLETE]

## Funding

[AUTHOR TO COMPLETE]

## References

1. The Cancer Genome Atlas Research Network, Weinstein JN, Collisson EA, et al. The Cancer Genome
   Atlas Pan-Cancer analysis project. *Nature Genetics*. 2013;45:1113-1120.
   doi:10.1038/ng.2764.
2. GTEx Consortium. The GTEx Consortium atlas of genetic regulatory effects across human tissues.
   *Science*. 2020;369:1318-1330. doi:10.1126/science.aaz1776.
3. Wilks C, Zheng SC, Chen FY, et al. recount3: summaries and queries for large-scale RNA-seq
   expression and splicing. *Genome Biology*. 2021;22:323.
   doi:10.1186/s13059-021-02533-6.
4. Milacic M, Beavers D, Conley P, et al. The Reactome Pathway Knowledgebase 2024.
   *Nucleic Acids Research*. 2024;52:D672-D678. doi:10.1093/nar/gkad1025.
