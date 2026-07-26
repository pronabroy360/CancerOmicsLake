from __future__ import annotations

import csv
from datetime import UTC, datetime
import hashlib
from html import escape
import json
from pathlib import Path
import shutil
import subprocess
from typing import Any

import polars as pl


REQUIRED_REPORTS = {
    "quality": "silver_data_quality_report.json",
    "dbt": "dbt_execution_report.json",
    "demo": "demo_check_report.json",
    "completion": "project_completion_report.json",
    "benchmark": "research_benchmark_report.json",
    "reference_ablation": "reference_ablation_report.json",
    "graph": "graph_metrics_report.json",
    "consensus": "consensus_candidate_report.json",
    "external": "external_expression_validation_report.json",
    "paired": "paired_expression_support_report.json",
    "pathway": "pathway_enrichment_report.json",
}

REQUIRED_GOLD = {
    "cohort": "gold_cohort_summary.parquet",
    "mutation_by_cancer": "gold_mutation_frequency_by_cancer.parquet",
    "reference_comparison": "gold_reference_method_comparison.parquet",
    "consensus_ablation": "gold_consensus_ablation_stability.parquet",
}


def _git_commit() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else "unknown"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"Expected JSON object evidence at {path}")
    return payload


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise RuntimeError(f"Refusing to write empty manuscript table: {path.name}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _format_int(value: Any) -> str:
    return f"{int(value):,}"


def _format_float(value: Any, digits: int = 3) -> str:
    return f"{float(value):.{digits}f}"


def _color(value: float, minimum: float, maximum: float) -> str:
    fraction = 0.5 if maximum <= minimum else (value - minimum) / (maximum - minimum)
    fraction = max(0.0, min(1.0, fraction))
    start = (239, 243, 226)
    end = (8, 91, 99)
    rgb = tuple(round(left + (right - left) * fraction) for left, right in zip(start, end))
    return f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"


def _heatmap_svg(
    rows: list[str],
    columns: list[str],
    values: dict[tuple[str, str], float],
    title: str,
    subtitle: str,
    legend_label: str,
) -> str:
    cell_width = 112
    cell_height = 42
    left = 280
    top = 116
    width = left + len(columns) * cell_width + 56
    height = top + len(rows) * cell_height + 108
    numeric = list(values.values())
    minimum = min(numeric)
    maximum = max(numeric)
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        "<style>text{font-family:Georgia,serif;fill:#17343a}.title{font-size:22px;font-weight:700}.sub{font-size:12px;fill:#52676b}.label{font-size:12px}.value{font:600 12px ui-monospace,monospace}.legend{font-size:11px;fill:#52676b}</style>",
        '<rect width="100%" height="100%" fill="#fbfaf4"/>',
        f'<text x="24" y="34" class="title">{escape(title)}</text>',
        f'<text x="24" y="57" class="sub">{escape(subtitle)}</text>',
    ]
    for index, column in enumerate(columns):
        x = left + index * cell_width + cell_width / 2
        parts.append(
            f'<text x="{x}" y="{top - 18}" text-anchor="middle" class="label">{escape(column)}</text>'
        )
    for row_index, row in enumerate(rows):
        y = top + row_index * cell_height
        parts.append(
            f'<text x="{left - 12}" y="{y + 26}" text-anchor="end" class="label">{escape(row)}</text>'
        )
        for column_index, column in enumerate(columns):
            value = float(values[(row, column)])
            x = left + column_index * cell_width
            fill = _color(value, minimum, maximum)
            text_fill = "#ffffff" if value > (minimum + maximum) / 2 else "#17343a"
            parts.extend(
                [
                    f'<rect x="{x + 2}" y="{y + 2}" width="{cell_width - 4}" height="{cell_height - 4}" rx="3" fill="{fill}"/>',
                    f'<text x="{x + cell_width / 2}" y="{y + 27}" text-anchor="middle" class="value" style="fill:{text_fill}">{value:.3f}</text>',
                ]
            )
    legend_y = top + len(rows) * cell_height + 36
    parts.append(
        f'<text x="24" y="{legend_y}" class="legend">{escape(legend_label)}: {minimum:.3f} to {maximum:.3f}</text>'
    )
    parts.append(
        f'<text x="24" y="{legend_y + 22}" class="legend">Generated from validated aggregate CancerOmicsLake marts.</text>'
    )
    parts.append("</svg>")
    return "\n".join(parts)


def _architecture_svg() -> str:
    stages = [
        ("PUBLIC SOURCES", ("GDC / GTEx / recount3", "Reactome pathways")),
        ("BRONZE", ("Immutable files + checksums", "Source provenance")),
        ("SILVER", ("Typed samples, genes,", "expression, mutations")),
        ("GOLD", ("Research marts + ablation", "Quality evidence")),
        ("RESEARCH SURFACES", ("DuckDB / dbt / API", "Dashboard / graph")),
    ]
    width = 1280
    height = 330
    box_width = 216
    gap = 28
    start = 32
    colors = ["#dbe8cc", "#b8d7c5", "#72b5ad", "#287d82", "#173f4a"]
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        "<style>text{font-family:Georgia,serif}.title{font-size:24px;font-weight:700;fill:#17343a}.stage{font-size:13px;font-weight:700}.desc{font-size:12px}.arrow{stroke:#c1773f;stroke-width:3;fill:none}</style>",
        '<rect width="100%" height="100%" fill="#fbfaf4"/>',
        '<text x="32" y="42" class="title">CancerOmicsLake evidence flow</text>',
        '<text x="32" y="66" font-size="12" fill="#52676b">Open-access inputs become aggregate, traceable research evidence through explicit quality boundaries.</text>',
        '<defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8 z" fill="#c1773f"/></marker></defs>',
    ]
    for index, ((stage, description_lines), color) in enumerate(zip(stages, colors)):
        x = start + index * (box_width + gap)
        text_color = "#ffffff" if index >= 3 else "#17343a"
        parts.extend(
            [
                f'<rect x="{x}" y="112" width="{box_width}" height="126" rx="8" fill="{color}"/>',
                f'<text x="{x + 16}" y="144" class="stage" fill="{text_color}">{escape(stage)}</text>',
                f'<text x="{x + 16}" y="174" class="desc" fill="{text_color}">{escape(description_lines[0])}</text>',
                f'<text x="{x + 16}" y="194" class="desc" fill="{text_color}">{escape(description_lines[1])}</text>',
            ]
        )
        if index < len(stages) - 1:
            arrow_start = x + box_width + 4
            arrow_end = x + box_width + gap - 5
            parts.append(
                f'<path d="M {arrow_start} 175 L {arrow_end} 175" class="arrow" marker-end="url(#arrow)"/>'
            )
    parts.append(
        '<text x="32" y="286" font-size="12" fill="#52676b">Compliance boundary: controlled-access data and individual identifiers are excluded from public release surfaces.</text>'
    )
    parts.append("</svg>")
    return "\n".join(parts)


def _evidence_resource(name: str, path: Path, row_count: int | None = None) -> dict[str, Any]:
    payload = {
        "name": name,
        "path": str(path),
        "bytes": path.stat().st_size,
        "sha256": _sha256(path),
    }
    if row_count is not None:
        payload["row_count"] = row_count
    return payload


def _claim(claim_id: str, statement: str, value: Any, source: str) -> dict[str, Any]:
    return {
        "claim_id": claim_id,
        "statement": statement,
        "value": value,
        "source": source,
    }


def _status_guard(
    reports: dict[str, dict[str, Any]],
    fair_manifest: dict[str, Any],
    git_commit: str,
    strict_provenance: bool,
) -> None:
    accepted = {
        "quality": {"passed", "passed_with_warnings"},
        "dbt": {"passed"},
        "demo": {"passed"},
        "completion": {"complete"},
        "benchmark": {"passed"},
        "reference_ablation": {"completed"},
        "graph": {"passed"},
        "consensus": {"completed"},
        "external": {"completed"},
        "paired": {"completed"},
        "pathway": {"completed"},
    }
    failures = [
        f"{name}={reports[name].get('status')}"
        for name, allowed in accepted.items()
        if reports[name].get("status") not in allowed
    ]
    if failures:
        raise RuntimeError(f"Manuscript evidence status gate failed: {', '.join(failures)}")
    if reports["dbt"].get("action") != "test":
        raise RuntimeError("Manuscript evidence requires a passing dbt test report")
    if reports["demo"].get("check_count") != len(reports["demo"].get("checks", [])):
        raise RuntimeError("Manuscript demo evidence has inconsistent check counts")
    if reports["completion"].get("completed_milestones") != reports["completion"].get(
        "total_milestones"
    ):
        raise RuntimeError("Manuscript evidence requires all project milestones")
    if not reports["graph"].get("public_safe"):
        raise RuntimeError("Manuscript evidence requires a public-safe graph report")
    if fair_manifest.get("identifier_safety", {}).get("status") != "passed":
        raise RuntimeError("Manuscript evidence requires a passing FAIR identifier audit")
    if strict_provenance:
        versioned_commits = {
            "benchmark": reports["benchmark"].get("git_commit"),
            "reference_ablation": reports["reference_ablation"].get("git_commit"),
            "fair_manifest": fair_manifest.get("git_commit"),
        }
        stale = {
            name: commit
            for name, commit in versioned_commits.items()
            if commit != git_commit
        }
        if stale:
            raise RuntimeError(
                f"Manuscript evidence does not match Git commit {git_commit}: {stale}"
            )


def _summarize_reference_table(reference: pl.DataFrame) -> list[dict[str, Any]]:
    return (
        reference.filter(pl.col("top_k") == 100)
        .select(
            [
                "cancer_type",
                "method_a",
                "method_b",
                "common_gene_count",
                "top_k_overlap_count",
                "top_k_jaccard",
                "regulated_direction_concordance",
                "spearman_abs_effect",
                "agreement_tier",
            ]
        )
        .sort(["cancer_type", "method_a", "method_b"])
        .to_dicts()
    )


def _summarize_ablation_table(ablation: pl.DataFrame) -> list[dict[str, Any]]:
    return (
        ablation.filter(pl.col("top_k") == 100)
        .select(
            [
                "cancer_type",
                "ablation_scenario",
                "retained_weight",
                "top_k_overlap_count",
                "top_k_jaccard",
                "spearman_consensus_score",
                "median_baseline_top_k_rank_shift",
                "fixed_threshold_retention_rate",
                "sensitivity_tier",
            ]
        )
        .sort(["cancer_type", "ablation_scenario"])
        .to_dicts()
    )


def _manuscript_text(evidence: dict[str, Any]) -> str:
    cohort = evidence["cohort"]
    results = evidence["results"]
    verification = evidence["verification"]
    generated_at = evidence["generated_at"]
    return f"""# CancerOmicsLake: a provenance-aware multi-reference data lakehouse for reproducible cancer-omics research

**Manuscript status:** Methods/data-engineering draft generated from validated artifacts on {generated_at}.

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

**Results:** The evaluated local profile contains {_format_int(cohort['tcga_patient_count'])} TCGA
patients, {_format_int(cohort['tcga_sample_count'])} TCGA samples,
{_format_int(cohort['tcga_expression_row_count'])} TCGA expression rows,
{_format_int(cohort['gtex_expression_row_count'])} GTEx expression rows, and
{_format_int(cohort['protein_altering_mutation_record_count'])} protein-altering mutation records.
Across {_format_int(results['common_gene_count'])} common genes per cancer, pairwise absolute-effect
Spearman associations were {results['spearman_min']:.3f}-{results['spearman_max']:.3f}, whereas
regulated-direction concordance was {results['regulated_direction_min']:.3f}-{results['regulated_direction_max']:.3f}
and top-list Jaccard similarity across K=25, 50, 100, and 250 was
{results['reference_jaccard_min']:.3f}-{results['reference_jaccard_max']:.3f}. Removing all three
explicit reference-related consensus components reduced score association to
{results['all_reference_rho_min']:.3f}-{results['all_reference_rho_max']:.3f}. The public graph
contained {_format_int(verification['public_graph_nodes'])} nodes and
{_format_int(verification['public_graph_edges'])} edges after individual-level entities were removed.

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

CancerOmicsLake processed {_format_int(cohort['tcga_file_count'])} TCGA files into
{_format_int(cohort['tcga_expression_row_count'])} TCGA and
{_format_int(cohort['gtex_expression_row_count'])} GTEx expression rows. The mutation layer retained
{_format_int(cohort['mutation_record_count'])} somatic records, including
{_format_int(cohort['protein_altering_mutation_record_count'])} protein-altering records across
{_format_int(cohort['mutation_profiled_sample_count'])} downloaded mutation profiles.

### 3.2 Validation and candidate triage

External validation evaluated {_format_int(results['external_rows'])} cancer-gene pairs and marked
{_format_int(results['external_discordant'])} as directionally discordant. Matched TCGA analysis
evaluated {_format_int(results['paired_rows'])} cancer-gene rows, including
{_format_int(results['paired_replicated'])} paired-replicated results. The consensus layer evaluated
{_format_int(results['consensus_rows'])} rows and retained {_format_int(results['prioritized'])}
prioritized candidates and {_format_int(results['watchlist'])} watchlist candidates. These labels
are prioritization states rather than validated biomarkers.

### 3.3 Reference sensitivity

All three cancers had {_format_int(results['common_gene_count'])} genes in the common comparison
universe. Absolute-effect associations were moderate to high
({results['spearman_min']:.3f}-{results['spearman_max']:.3f}), but regulated-direction agreement
({results['regulated_direction_min']:.3f}-{results['regulated_direction_max']:.3f}) and candidate-set
Jaccard ({results['reference_jaccard_min']:.3f}-{results['reference_jaccard_max']:.3f}) were lower.
{results['limited_reference_comparisons']} of {results['reference_comparisons']} direct comparisons
were classified limited under the
predefined engineering tier (Figure 2; Supplementary Table S1).

### 3.4 Consensus ablation

Removing all explicit reference-related components yielded top-list Jaccard values of
{results['all_reference_jaccard_min']:.3f}-{results['all_reference_jaccard_max']:.3f} and score
associations of {results['all_reference_rho_min']:.3f}-{results['all_reference_rho_max']:.3f}.
Single-component removals were less disruptive but remained list-size and cancer dependent
(Figure 3; Supplementary Table S2). Fixed full-model threshold retention was reported
descriptively and did not determine robustness tiers.

### 3.5 Operational evidence

The quality gate recorded {verification['quality_passed']} passed checks and
{verification['quality_warnings']} warnings. The dbt model/test gate,
{verification['demo_checks']} strict demo checks, and {verification['milestones']} project
milestones passed. Six warm DuckDB workloads had median
latencies of {verification['benchmark_min_ms']:.3f}-{verification['benchmark_max_ms']:.3f} ms in the
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
"""


def build_manuscript_package(
    gold_dir: str | Path = "data/gold",
    reports_dir: str | Path = "outputs/reports",
    fair_manifest_path: str | Path = "outputs/releases/v0.1.0/manifest.json",
    output_dir: str | Path = "manuscript",
    strict_provenance: bool = True,
) -> dict[str, Any]:
    gold_root = Path(gold_dir)
    reports_root = Path(reports_dir)
    fair_path = Path(fair_manifest_path)
    report_paths = {
        name: reports_root / filename for name, filename in REQUIRED_REPORTS.items()
    }
    gold_paths = {name: gold_root / filename for name, filename in REQUIRED_GOLD.items()}
    missing = [
        str(path)
        for path in [*report_paths.values(), *gold_paths.values(), fair_path]
        if not path.exists()
    ]
    if missing:
        raise RuntimeError(f"Manuscript package missing required evidence: {', '.join(missing)}")

    reports = {name: _read_json(path) for name, path in report_paths.items()}
    fair_manifest = _read_json(fair_path)
    git_commit = _git_commit()
    _status_guard(reports, fair_manifest, git_commit, strict_provenance)

    cohort_frame = pl.read_parquet(gold_paths["cohort"])
    mutation = pl.read_parquet(gold_paths["mutation_by_cancer"])
    reference = pl.read_parquet(gold_paths["reference_comparison"])
    ablation = pl.read_parquet(gold_paths["consensus_ablation"])
    if cohort_frame.height != 1 or mutation.is_empty() or reference.is_empty() or ablation.is_empty():
        raise RuntimeError("Manuscript package requires non-empty aggregate gold evidence")
    cohort = cohort_frame.row(0, named=True)

    reference_jaccard = reference.get_column("top_k_jaccard")
    regulated_direction = reference.get_column("regulated_direction_concordance")
    spearman = reference.get_column("spearman_abs_effect")
    all_reference = ablation.filter(
        pl.col("ablation_scenario") == "without_explicit_reference_components"
    )
    if all_reference.is_empty():
        raise RuntimeError("Manuscript package requires the full explicit-reference ablation")

    external_tiers = {
        row["validation_tier"]: row["len"]
        for row in reports["external"]["tier_counts"]
    }
    paired_tiers = {
        row["paired_support_tier"]: row["len"]
        for row in reports["paired"]["tier_counts"]
    }
    benchmark_medians = [
        workload["latency_ms"]["median"]
        for workload in reports["benchmark"]["workloads"]
        if workload["status"] == "passed"
    ]
    quality_checks = reports["quality"].get("checks", [])
    failed_quality = [
        check for check in quality_checks if check.get("status") == "failed"
    ]
    if failed_quality:
        raise RuntimeError(f"Manuscript package found {len(failed_quality)} failed quality checks")

    evidence = {
        "generated_at": datetime.now(UTC).isoformat(),
        "git_commit": git_commit,
        "cohort": cohort,
        "results": {
            "common_gene_count": int(reference.get_column("common_gene_count").min()),
            "reference_comparisons": reference.height,
            "limited_reference_comparisons": reference.filter(
                pl.col("agreement_tier") == "limited"
            ).height,
            "reference_jaccard_min": float(reference_jaccard.min()),
            "reference_jaccard_max": float(reference_jaccard.max()),
            "regulated_direction_min": float(regulated_direction.min()),
            "regulated_direction_max": float(regulated_direction.max()),
            "spearman_min": float(spearman.min()),
            "spearman_max": float(spearman.max()),
            "all_reference_jaccard_min": float(
                all_reference.get_column("top_k_jaccard").min()
            ),
            "all_reference_jaccard_max": float(
                all_reference.get_column("top_k_jaccard").max()
            ),
            "all_reference_rho_min": float(
                all_reference.get_column("spearman_consensus_score").min()
            ),
            "all_reference_rho_max": float(
                all_reference.get_column("spearman_consensus_score").max()
            ),
            "external_rows": int(reports["external"]["row_count"]),
            "external_discordant": int(external_tiers.get("discordant", 0)),
            "paired_rows": int(reports["paired"]["row_count"]),
            "paired_replicated": int(paired_tiers.get("paired_replicated", 0)),
            "consensus_rows": int(reports["consensus"]["row_count"]),
            "prioritized": int(reports["consensus"]["prioritized_count"]),
            "watchlist": int(reports["consensus"]["watchlist_count"]),
        },
        "verification": {
            "quality_checks": len(quality_checks),
            "quality_passed": sum(
                check.get("status") == "passed" for check in quality_checks
            ),
            "quality_warnings": sum(
                check.get("status") == "warning" for check in quality_checks
            ),
            "dbt_status": str(reports["dbt"]["status"]),
            "demo_checks": int(reports["demo"]["check_count"]),
            "milestones": int(reports["completion"]["completed_milestones"]),
            "public_graph_nodes": int(reports["graph"]["node_count"]),
            "public_graph_edges": int(reports["graph"]["edge_count"]),
            "benchmark_min_ms": float(min(benchmark_medians)),
            "benchmark_max_ms": float(max(benchmark_medians)),
            "fair_resources": int(fair_manifest["resource_count"]),
        },
    }

    output = Path(output_dir)
    build = output.parent / f".{output.name}.building"
    if build.exists():
        shutil.rmtree(build)
    (build / "tables").mkdir(parents=True)
    (build / "figures").mkdir(parents=True)
    (build / "supplement").mkdir(parents=True)

    inventory_rows = [
        {"metric": key, "value": value, "evidence": REQUIRED_GOLD["cohort"]}
        for key, value in cohort.items()
    ]
    inventory_rows.extend(
        [
            {
                "metric": "public_graph_nodes",
                "value": reports["graph"]["node_count"],
                "evidence": REQUIRED_REPORTS["graph"],
            },
            {
                "metric": "public_graph_edges",
                "value": reports["graph"]["edge_count"],
                "evidence": REQUIRED_REPORTS["graph"],
            },
            {
                "metric": "fair_release_resources",
                "value": fair_manifest["resource_count"],
                "evidence": fair_path.name,
            },
        ]
    )
    reference_rows = _summarize_reference_table(reference)
    ablation_rows = _summarize_ablation_table(ablation)
    verification_rows = [
        {"gate": "dbt model/test gate", "result": reports["dbt"].get("action", "test"), "status": evidence["verification"]["dbt_status"]},
        {
            "gate": "Quality checks",
            "result": (
                f"{evidence['verification']['quality_passed']} passed; "
                f"{evidence['verification']['quality_warnings']} warnings"
            ),
            "status": reports["quality"]["status"],
        },
        {"gate": "Strict demo checks", "result": evidence["verification"]["demo_checks"], "status": "passed"},
        {"gate": "PRD milestones", "result": evidence["verification"]["milestones"], "status": "complete"},
        {"gate": "Benchmark workloads", "result": len(benchmark_medians), "status": "passed"},
        {"gate": "FAIR identifier audit", "result": evidence["verification"]["fair_resources"], "status": "passed"},
    ]
    _write_csv(build / "tables/table_1_dataset_inventory.csv", inventory_rows)
    _write_csv(build / "tables/table_2_reference_comparison_k100.csv", reference_rows)
    _write_csv(build / "tables/table_3_consensus_ablation_k100.csv", ablation_rows)
    _write_csv(build / "tables/table_4_reproducibility_gates.csv", verification_rows)
    reference.write_csv(build / "supplement/table_s1_reference_comparison_all_k.csv")
    ablation.write_csv(build / "supplement/table_s2_consensus_ablation_all_k.csv")

    (build / "figures/figure_1_architecture.svg").write_text(
        _architecture_svg(), encoding="utf-8"
    )
    comparison_rows = sorted(
        {
            f"{row['cancer_type']} | {row['method_a']} vs {row['method_b']}"
            for row in reference.to_dicts()
        }
    )
    k_columns = [str(value) for value in sorted(reference["top_k"].unique().to_list())]
    comparison_values = {
        (
            f"{row['cancer_type']} | {row['method_a']} vs {row['method_b']}",
            str(row["top_k"]),
        ): float(row["top_k_jaccard"])
        for row in reference.to_dicts()
    }
    (build / "figures/figure_2_reference_jaccard.svg").write_text(
        _heatmap_svg(
            comparison_rows,
            k_columns,
            comparison_values,
            "Normal-reference candidate-list agreement",
            "Top-K Jaccard across three tumor-normal effect methods and three cancers",
            "Jaccard similarity",
        ),
        encoding="utf-8",
    )
    scenario_labels = {
        "without_reference_triangulation": "Remove triangulation",
        "without_external_validation": "Remove external validation",
        "without_paired_support": "Remove paired support",
        "without_explicit_reference_components": "Remove all explicit reference components",
    }
    ablation_rows_labels = [
        f"{cancer} | {scenario_labels[scenario]}"
        for cancer in sorted(ablation["cancer_type"].unique().to_list())
        for scenario in scenario_labels
    ]
    ablation_values = {
        (
            f"{row['cancer_type']} | {scenario_labels[row['ablation_scenario']]}",
            str(row["top_k"]),
        ): float(row["top_k_jaccard"])
        for row in ablation.to_dicts()
    }
    (build / "figures/figure_3_ablation_jaccard.svg").write_text(
        _heatmap_svg(
            ablation_rows_labels,
            [str(value) for value in sorted(ablation["top_k"].unique().to_list())],
            ablation_values,
            "Consensus candidate stability under component ablation",
            "Baseline-versus-ablated Top-K Jaccard; retained component weights are renormalized",
            "Jaccard similarity",
        ),
        encoding="utf-8",
    )

    manuscript = _manuscript_text(evidence)
    (build / "manuscript.md").write_text(manuscript, encoding="utf-8")
    (build / "supplement/reproducibility_checklist.md").write_text(
        f"""# Reproducibility Checklist

- [x] Git commit recorded: `{git_commit}`
- [x] Open-access-only acquisition policy
- [x] Source and derived-file checksums
- [x] Configuration-driven cohort selection
- [x] Deterministic candidate ranking and tie breaking
- [x] Cancer-wise multiple-testing correction
- [x] Multi-reference sensitivity analysis at K=25, 50, 100, 250
- [x] Public graph identifier filtering
- [x] Aggregate FAIR release identifier audit
- [x] Python, dbt, quality, demo, and benchmark gates
- [ ] Independent biological review
- [ ] External clinical validation
- [ ] DOI assigned to derived-data release
- [ ] Author affiliation, funding, and competing-interest fields completed
""",
        encoding="utf-8",
    )

    evidence_paths: list[tuple[str, Path, int | None]] = []
    for name, path in report_paths.items():
        evidence_paths.append((f"report:{name}", path, None))
    for name, path in gold_paths.items():
        rows = pl.scan_parquet(path).select(pl.len()).collect().item()
        evidence_paths.append((f"gold:{name}", path, int(rows)))
    evidence_paths.append(("fair_manifest", fair_path, None))
    resources = [
        _evidence_resource(name, path, rows) for name, path, rows in evidence_paths
    ]
    claims = [
        _claim("C01", "TCGA patient count", cohort["tcga_patient_count"], "gold:cohort"),
        _claim("C02", "TCGA sample count", cohort["tcga_sample_count"], "gold:cohort"),
        _claim(
            "C03",
            "Protein-altering mutation record count",
            cohort["protein_altering_mutation_record_count"],
            "gold:cohort",
        ),
        _claim(
            "C04",
            "Reference comparison common genes per cancer",
            evidence["results"]["common_gene_count"],
            "gold:reference_comparison",
        ),
        _claim(
            "C05",
            "Direct-reference Top-K Jaccard range",
            [
                evidence["results"]["reference_jaccard_min"],
                evidence["results"]["reference_jaccard_max"],
            ],
            "gold:reference_comparison",
        ),
        _claim(
            "C06",
            "Regulated-direction concordance range",
            [
                evidence["results"]["regulated_direction_min"],
                evidence["results"]["regulated_direction_max"],
            ],
            "gold:reference_comparison",
        ),
        _claim(
            "C07",
            "Absolute-effect Spearman range",
            [
                evidence["results"]["spearman_min"],
                evidence["results"]["spearman_max"],
            ],
            "gold:reference_comparison",
        ),
        _claim(
            "C08",
            "Prioritized consensus candidates",
            evidence["results"]["prioritized"],
            "report:consensus",
        ),
        _claim(
            "C09",
            "Public graph node and edge counts",
            [
                evidence["verification"]["public_graph_nodes"],
                evidence["verification"]["public_graph_edges"],
            ],
            "report:graph",
        ),
        _claim(
            "C10",
            "Passing standard quality checks",
            evidence["verification"]["quality_passed"],
            "report:quality",
        ),
    ]
    ledger = {
        "schema_version": "1.0",
        "generated_at": evidence["generated_at"],
        "git_commit": git_commit,
        "status": "passed",
        "scope": "aggregate_publication_evidence",
        "resources": resources,
        "claims": claims,
        "limitations": [
            "Evidence values are computational outputs and require scientific interpretation.",
            "Cross-source expression sensitivity is measured but not fully batch corrected.",
            "The package is a manuscript draft, not evidence of peer review or acceptance.",
        ],
    }
    (build / "evidence_ledger.json").write_text(
        json.dumps(ledger, indent=2), encoding="utf-8"
    )
    (build / "README.md").write_text(
        """# CancerOmicsLake Manuscript Package

This directory is generated by `make build-manuscript-package`.

- `manuscript.md`: journal-neutral methods/data-engineering draft
- `tables/`: manuscript-facing aggregate CSV tables
- `figures/`: editable SVG figures
- `supplement/`: full multi-K results and reproducibility checklist
- `evidence_ledger.json`: claim-to-source mapping with SHA-256 hashes

Complete author placeholders and obtain biological review before submission. Re-run the generator
after any evidence-producing pipeline change.
""",
        encoding="utf-8",
    )

    output_files = sorted(path for path in build.rglob("*") if path.is_file())
    package_manifest = {
        "schema_version": "1.0",
        "generated_at": evidence["generated_at"],
        "git_commit": git_commit,
        "status": "passed",
        "file_count": len(output_files) + 1,
        "hashed_file_count": len(output_files),
        "files": [
            {
                "path": path.relative_to(build).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": _sha256(path),
            }
            for path in output_files
        ],
    }
    (build / "package_manifest.json").write_text(
        json.dumps(package_manifest, indent=2), encoding="utf-8"
    )
    if output.exists():
        shutil.rmtree(output)
    build.replace(output)
    return {
        "status": "passed",
        "generated_at": evidence["generated_at"],
        "git_commit": git_commit,
        "output_directory": str(output),
        "file_count": package_manifest["file_count"],
        "claim_count": len(claims),
        "reference_comparison_rows": reference.height,
        "consensus_ablation_rows": ablation.height,
    }
