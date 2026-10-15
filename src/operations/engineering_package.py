"""Build an aggregate-only v5 evidence package, with execution and human gates separate."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import shutil
import subprocess
import tarfile

import polars as pl
import yaml

from src.analytics.controlled_reference_study import sha256_file
from src.operations.engineering_evidence import resource, verify, write_once

ROOT = Path("outputs/research/global_evidence_review_v5")


def author_gates(metadata: dict) -> list[dict]:
    manuscript = metadata.get("manuscript", {})
    author, declarations, ai = [manuscript.get(k, {}) for k in ("author", "declarations", "ai_assistance")]
    def confirmed(value) -> bool:
        return isinstance(value, str) and bool(value.strip()) and not any(
            word in value.lower() for word in ("pending", "to complete", "[author", "[ai disclosure"))
    return [{"gate": "author_identity", "passed": bool(author.get("metadata_verified") and
                 all(confirmed(author.get(k)) for k in ("name", "affiliation", "corresponding_email"))),
             "required": ["affiliation", "corresponding_email", "identity confirmation"]},
            {"gate": "declarations", "passed": bool(declarations.get("declarations_verified") and
                 confirmed(declarations.get("funding")) and confirmed(declarations.get("competing_interests"))),
             "required": ["funding statement", "competing-interests statement", "confirmation"]},
            {"gate": "AI_disclosure_and_responsibility", "passed": bool(ai.get("human_review_confirmed") and
                 ai.get("author_responsibility_confirmed") and ai.get("tools") and all(
                     confirmed(t.get("model")) and confirmed(t.get("name")) and
                     not t.get("author_confirmation_required", True) for t in ai["tools"])),
             "required": ["exact products/models", "human manuscript review", "author responsibility"]},
            {"gate": "independent_reproduction", "passed": False,
             "required": ["independent investigator execution record and confirmation"]},
            {"gate": "publication_approval", "passed": False,
             "required": ["explicit final publication approval; preparation only remains authorized"]}]


def no_identifiers(paths: list[Path], identifiers: set[str]) -> None:
    for path in paths:
        text = path.read_text(encoding="utf-8")
        if any(value in text for value in identifiers):
            raise ValueError(f"Individual specimen identifier in aggregate package: {path.name}")
        if re.search(r"github_pat_[A-Za-z0-9_]{30,}|ghp_[A-Za-z0-9]{30,}|-----BEGIN (?:RSA |EC )?PRIVATE KEY-----", text):
            raise ValueError(f"Credential pattern in aggregate package: {path.name}")


def _deduplicate(items: list[dict]) -> list[dict]:
    unique = {}
    for item in items:
        path = item["path"]
        if path in unique and item["sha256"] != unique[path]["sha256"]:
            raise ValueError(f"Conflicting evidence versions: {path}")
        unique[path] = {"path": path, "sha256": item["sha256"]}
    return sorted(unique.values(), key=lambda r: r["path"])


def build_package() -> dict:
    previous = Path("outputs/research/global_evidence_review_v4")
    v3_path = Path("outputs/research/global_evidence_review_v3/review.json")
    numerical_path = Path("outputs/research/engineering_numerical_v1/report.json")
    workflow_path = Path("outputs/research/engineering_workflow_v1/report.json")
    capability_path = Path("outputs/reports/comparative_evaluation_report.json")
    acceptance_path = Path("outputs/research/engineering_acceptance_v1/verification.json")
    v3 = json.loads(v3_path.read_text())
    v4 = json.loads((previous / "review.json").read_text())
    numerical, workflow = [json.loads(p.read_text()) for p in (numerical_path, workflow_path)]
    capability = json.loads(capability_path.read_text())
    acceptance = json.loads(acceptance_path.read_text())
    verify(acceptance["code_resources"] + [acceptance["pytest_log"]])
    if not acceptance["tests_passed"] or acceptance["silver_quality_status"] == "failed":
        raise ValueError("Software/quality acceptance failed; do not package")
    if numerical["execution_status"] != "completed" or workflow["execution_status"] != "completed":
        raise ValueError("Engineering executions must finish before packaging")
    sources = [resource(p) for p in (previous / "review.json", v3_path, numerical_path, workflow_path,
               capability_path, acceptance_path,
               Path("src/operations/engineering_package.py"), Path("research/engineering_figures.R"),
               Path("docs/method_research_protocol.md"), Path("configs/manuscript_metadata.yml"))]
    sources += v4["resources"] + numerical["resources"] + workflow["resources"]
    # Verify every earlier review file, including drafts/tables absent from its resource list.
    for directory in Path("outputs/research").glob("*evidence_review*"):
        if directory == ROOT:
            continue
        sources += [resource(p) for p in directory.rglob("*") if p.is_file()]
    sources = _deduplicate(sources)
    verify(sources)
    if (ROOT / "package_manifest.json").exists():
        old = json.loads((ROOT / "package_manifest.json").read_text())
        verify([{**item, "path": str(ROOT / item["path"])} for item in old["files"]])
        review = json.loads((ROOT / "review.json").read_text())
        if review["resources"] != sources:
            raise ValueError("V5 package inputs differ; create a new review version")
        return review
    ROOT.mkdir(parents=True, exist_ok=True)
    tables = ROOT / "tables"
    tables.mkdir(exist_ok=True)
    evidence = ROOT / "evidence"
    evidence.mkdir(exist_ok=True)
    for name, path in (("numerical", numerical_path), ("workflow", workflow_path),
                       ("processing_v2", Path("outputs/research/matched_processing_v2/report.json")),
                       ("rra", Path("outputs/research/published_rra_baseline_v1/report.json")),
                       ("verification", acceptance_path), ("historical_capability", capability_path)):
        shutil.copyfile(path, evidence / f"{name}.json")
    source_root = ROOT / "source"
    code_files = [p for directory in (Path("src"), Path("configs"), Path("research"))
                  for p in directory.rglob("*") if p.is_file() and
                  (p.suffix in (".py", ".R", ".yml") or p.name.startswith("Dockerfile"))]
    code_files += [Path(name) for name in ("Makefile", "Dockerfile", "docker-compose.yml", "requirements.txt",
                                          ".dockerignore", ".gitignore", "LICENSE") if Path(name).is_file()]
    code_files += [Path("scripts/finalize_engineering_evidence.sh")]
    code_files += [Path("docs") / name for name in ("engineering_completion.md", "method_research_protocol.md",
                                                   "independent_reproduction_handoff.md")]
    code_files += [Path("outputs/research/protocol_sources") / sha / "controlled_reference_study.py" for sha in (
        "73429ce3b64c08e29850cac110a140ae230208ef3da518de71f27a2d3a939dcb",
        "dcb5d1c0a62aa3a465eea8c987ef42e84b44464eb6849a3f0ace3254dc42a0e1")]
    code_files += [Path("outputs/research") / name / "study_plan.json" for name in (
        "native_reference_pilot_v2", "native_reference_global_v1", "native_reference_paired_global_v1")]
    for path in code_files:
        target = source_root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
    source_notice = ("# Source snapshot\n\nThis captures the working source used for the engineering evidence, including "
                    "uncommitted source files. Source hashes in the study plans remain authoritative. "
                    "No data/, .env, token, credential, Git metadata, or downloaded external test dataset is included. "
                    "The benchmark calls the separately licensed NetworkDataCompanion/edgeR software from the "
                    "digest-pinned tcga-data-nf image; upstream URLs, versions and function provenance are in evidence/workflow.json.\n")
    (source_root / "README.md").write_text(source_notice)
    rra = v4["published_rra"]["comparisons"]
    effects = v3["processing_v2"]["effect_concordance"]
    topk = v3["processing_v2"]["topk"]
    rows = []
    for name in ("native_reference_global_v1", "native_reference_paired_global_v1"):
        frame = pl.read_parquet(Path("outputs/research") / name / "heldout_evaluation.parquet")
        rows += [{"study_id": name, **r} for r in frame.to_dicts()]
    pl.from_dicts(rows, infer_schema_length=None).write_csv(tables / "all_existing_methods.csv")
    pl.from_dicts(rra, infer_schema_length=None).write_csv(tables / "published_rra.csv")
    pl.from_dicts(effects, infer_schema_length=None).write_csv(tables / "processing_effects.csv")
    pl.from_dicts(topk, infer_schema_length=None).write_csv(tables / "processing_topk.csv")
    pl.DataFrame(workflow["comparisons"]).write_csv(tables / "workflow_correctness.csv")
    pl.DataFrame(workflow["timings"]).write_csv(tables / "workflow_timings.csv")
    pl.from_dicts(workflow["failure_experiments"], infer_schema_length=None).write_csv(tables / "failure_experiments.csv")
    pl.DataFrame([{"tool": r["tool"], "task_id": r["task_id"], "task_status": r["task_status"],
                   "tool_version": r["tool_version"], "limitations": " | ".join(r["limitations"])}
                  for r in capability["tasks"]]).write_csv(tables / "historical_capability_matrix.csv")
    pl.DataFrame([{"environment": k, "spearman": v["spearman"], "gene_count": v["gene_count"],
                   "filtered_gene_count": v["filtered_gene_count"]} for k, v in numerical["diagnostics"].items()]).write_csv(
                   tables / "numerical_environments.csv")
    metadata = yaml.safe_load(Path("configs/manuscript_metadata.yml").read_text())
    gates = author_gates(metadata)
    write_once(ROOT / "submission_checklist.json", {"publication_enabled": False, "gates": gates,
               "scientific_limits": ["Independent biological validation remains absent",
                                     "A novel computational-method contribution is unestablished",
                                     "Existing inspected holdouts cannot be reused as untouched confirmation"]})
    native = workflow.get("native_script_integration", [])
    payload = {"schema_version": "1.0", "review_id": ROOT.name,
               "engineering_execution_status": "completed", "numerical_acceptance": numerical["numerical_acceptance"],
               "workflow_evidence_completeness": workflow["evidence_completeness"],
               "workflow_module_equivalence": workflow["comparability_passed"],
               "historical_capability_status_counts": {s: sum(r["task_status"] == s for r in capability["tasks"])
                                                        for s in ("passed", "partial", "unsupported", "failed")},
               "software_verification": acceptance,
               "native_script_integration_completed": sum(r["execution_status"] == "completed" for r in native),
               "native_script_integration_comparable": sum(r["comparable"] for r in native),
               "native_script_integration_total": len(native),
               "publication_enabled": False, "independent_human_reproduction": False,
               "submission_status": "blocked_pending_human_gates", "measurement_counts": v3["measurement_counts"],
               "known_negative_results": ["No top-50 advantage over simple maximin in the corrected studies",
                   "Weak tie-aware top-gene overlap across native/recount3 processing",
                   "Original numerical tolerance remains unchanged; failed replay checks are retained"],
               "resources": sources}
    write_once(ROOT / "review.json", payload)
    ledger = {"review_id": ROOT.name, "resources": sources, "claims": [
        {"id": "cached_processing", "statement": "617 exact available specimens support processing-sensitivity analysis",
         "evidence": [str(v3_path)], "claim_boundary": "Available matched specimens; not independent biological validation"},
        {"id": "numerical_scope", "statement": "One historical Spearman statistic generated three failed top-k rows",
         "evidence": [str(numerical_path)], "claim_boundary": "Strict numerical acceptance remains reported separately"},
        {"id": "workflow_utility", "statement": "Common preparation tasks were measured in two complete passes",
         "evidence": [str(workflow_path)], "claim_boundary": "Shared R backend; added Polars adapter; no end-to-end or native-hardware superiority claim"},
        {"id": "candidate_limit", "statement": "No top-50 gain over maximin was established",
         "evidence": [str(v3_path)], "claim_boundary": "RRA differences do not establish a novel method"}]}
    write_once(ROOT / "evidence_ledger.json", ledger)
    numerical_lines = []
    for row in numerical["array_comparisons"]:
        numerical_lines.append(f"- {row['first']} versus {row['second']}: first differing intermediate = "
                               f"`{row['earliest_bitwise_difference'] or 'none'}`.")
    replay_lines = []
    for row in numerical["corrected_global_replays"]:
        failed = sum(d["cells_outside_fixed_tolerance"] for c in row["checks"] for d in c["numeric_diagnostics"])
        replay_lines.append(f"- {row['study_id']}: strict comparison {row['status']}; manifests identical "
                            f"{row['manifests_identical']}; {failed} numeric table cells outside tolerance.")
    os_comparison = next(r for r in numerical["array_comparisons"]
                         if r["first"] == "macos142" and r["second"] == "linux142")
    effect_difference = max(r.get("max_absolute_difference", 0.) for r in os_comparison["stages"]
                            if r["stage"].startswith("effect_"))
    rank_difference = max(r.get("max_absolute_difference", 0.) for r in os_comparison["stages"]
                          if r["stage"].startswith("ranks_"))
    mean_times = pl.DataFrame(workflow["timings"]).group_by("tool").agg(
        pl.col("median_seconds").median().alias("median_of_workload_medians")).to_dicts()
    benchmark_text = "; ".join(f"{r['tool']}: {r['median_of_workload_medians']:.3f} seconds" for r in mean_times)
    capability_text = ", ".join(f"{n} {s}" for s, n in payload["historical_capability_status_counts"].items())
    draft = f"""# CancerOmicsLake: auditable engineering and processing sensitivity for public cancer-omics data

Status: current exploratory engineering draft, generated from verified v5 evidence. Publication is disabled.

Author: Pronab Chandra Roy. Affiliation and corresponding email: pending confirmed author wording.

## Abstract

CancerOmicsLake integrates public TCGA and GTEx data with layered storage, typed warehouse contracts,
validation, provenance and aggregate graph exports. The current native silver snapshot contains
{v3['measurement_counts']['tcga']:,} TCGA and {v3['measurement_counts']['gtex']:,} GTEx expression measurements.
An exact-specimen processing analysis used 617 available specimens (417 TCGA, 200 GTEx). Broad signed
effects showed moderate concordance while leading-gene lists remained sensitive to processing and ties.
This study adds a controlled numerical diagnosis and a cached-input comparison with published preparation
methods. Numerical acceptance, output equivalence and independent reproduction are reported separately.
The contribution is an auditable engineering and sensitivity-evaluation framework; a novel ranking
method, clinical validity and independent biological confirmation remain unestablished.

## Introduction and related work

TCGA/GTEx exploration and harmonization are established by GEPIA2 [1], Wang et al. [2] and recount3 [3].
The published tcga-data-nf workflow [4] provides acquisition, preparation and regulatory-network analysis.
CancerOmicsLake therefore does not claim that combining these sources or using containers is new.
Its evaluated scope is source-to-artifact auditability, explicit failure semantics, analytical contracts
and the measured sensitivity of candidate rankings to reference and processing choices. Rank aggregation
is compared with the published RRA implementation [5]; stability-selection guarantees [6] are not
transferred to the experimental lower-quantile score.

## Methods

All studies use cached open-access files or publicly released recount3 processed data. No controlled
GDC files were acquired. Native TPM and recount3 coverage are distinct quantities and were not compared
as equal numerical units. Corrected candidate studies use one global case/donor partition across cancers.
The heldout samples have been inspected; subsequent diagnostics and comparator additions are exploratory.
Top-25/50/100 selections, specimen manifests, software and input hashes are frozen in separate protocols.
Patient/donor bootstrap intervals are conditional descriptive intervals. Tie-resolution distributions
measure computational tie uncertainty and do not represent biological uncertainty.

The numerical diagnosis fixes rtol=1e-8 and atol=1e-10, reproduces archived source, and varies Polars
1.42.1 versus 1.44.2 within macOS and Linux with NumPy/SciPy versions held fixed. Intermediate arrays
and identifiers remain private. The two corrected full studies are replayed in the pinned Linux runtime.

The external study pins tcga-data-nf commit 1069eb9c01b97640fd532ffac8551096d2a2790a. Its actual
NetworkDataCompanion normalization/filter functions provide the reference. Both comparison paths use
the same edgeR TMM coverage-CPM backend; CancerOmicsLake adds a Polars filtering/export adapter for
this benchmark. Seven cached source/tissue groups use nested 10/20/30-unit samples and all raw genes.
Filtering uses expression >=1 in at least 20% of specimens, with purity filtering and batch correction
disabled. Both paths run sequentially in the same AMD64 image under emulation on an ARM host, with
four CPUs and a 12-GB memory limit, two warmups and seven measurements, repeated in a second pass.
Per-workload times exclude the initial raw-table read; batch wall times include startup and reads.
Memory peaks refer to entire tool batches. Native-script integration is recorded independently from
direct-module measurements; no Nextflow runtime comparison is claimed.
The extension serializes a full-precision normalized intermediate and starts a Python child process
for each iteration, while the reference filters and writes directly in R. Those costs are included;
the experiment compares these adapters and does not isolate intrinsic Polars-versus-R engine speed.

## Results

### Processing and candidate sensitivity

Across 55,660 shared genes, signed-effect Kendall tau-b was 0.556-0.571 and thresholded direction
agreement was 89.8%-90.5%. Tie-aware top-50 mean Jaccard remained 0.0026-0.0058. The predefined
informative-gene filter did not remove this weak leading-list agreement. All source-specific and
filtered results, denominators and intervals are supplied in the processing tables.

At top-50 the lower-quantile method exceeded official RRA heldout replication by 0.02-0.10, with one
paired interval including zero. It showed no top-50 advantage over simple maximin in the corrected
full studies. RRA scores are used only for ranking because both input lists share tumor samples.
The shared-normal-bias simulation remains a counterexample to equating cross-reference replication
with biological truth.

### Numerical reproducibility

The three historical failing rows represent {numerical['distinct_historical_statistics']} distinct
Spearman statistic, repeated for three top-k settings. The fixed-tolerance numerical acceptance is
**{numerical['numerical_acceptance']}**. The following results are retained without tolerance changes:

{chr(10).join(numerical_lines)}

{chr(10).join(replay_lines)}

Intermediate-stage agreement localizes the discrepancy; OS and library labels alone are not causal
explanations. Exact candidate or heldout agreement does not imply every sensitivity statistic passes.
Within each OS the two tested Polars versions produce identical diagnostic arrays. Across OSes,
the first divergence is in log2 effects (maximum absolute difference {effect_difference:.3g}), after
matching input arrays, medians and ratios. The diagnostic rank changes reach {rank_difference:g}.
This identifies the observed numerical stage and tie sensitivity without assigning a platform-wide
causal explanation or changing the original statistic.

### External workflow engineering evaluation

The study contains {len(workflow['comparisons'])} workload equivalence cells and
{len(workflow['timings'])} tool/pass/workload summaries. Common-module equivalence passed:
**{workflow['comparability_passed']}**. Native-script integrations completed
{payload['native_script_integration_completed']}/{len(native)}, with equivalent outputs in
{payload['native_script_integration_comparable']}/{len(native)}. Every failed integration remains visible.
Descriptive medians across workload medians were {benchmark_text}; these are conditional measurements
of these adapters and this emulated environment, not a universal workflow performance ranking.
Correctness, individual workload timings, ranges, normalization costs and full-batch peaks are supplied
separately. Fault reports identify whether a check belongs to the shared adapter or evidence guard;
manual restart evidence is not labeled native automatic resume.
The interruption probe pauses after a successful input read; it does not establish mid-export crash
safety or interrupted-network-download recovery for the external workflow.
The earlier portal/package capability snapshot is retained separately ({capability_text}). Its
evidence-completeness status does not convert partial tasks into successful executions, and its
historical source-specific cohort quantities are not relabeled as current matched cohorts.

## Discussion and limitations

The measured numerical discrepancy and weak top-list processing overlap limit strong claims of
portable candidate ordering. Matched specimens control membership, but do not identify processing,
annotation or biological causes by themselves. The engineering benchmark shares a normalization
backend, excludes network acquisition and regulatory-network inference, and includes a newly added
CancerOmicsLake adapter. It cannot establish end-to-end superiority. Identical software outputs from
the author are distinct from an independent investigator's reproduction, which remains unverified.
The work supports an engineering/evaluation contribution. A new computational method must first
demonstrate gains over maximin under explicit assumptions and on fresh evidence.

## Data, code and reproducibility

The package contains aggregate tables, figures, checksums, an evidence ledger and reproduction
instructions. Private study measurements, specimen manifests and per-gene intermediates stay under
data/research; cached original sources remain in bronze storage.
Public release and DOI deposit remain disabled pending author approval and the submission gates.

## Author declarations

Affiliation, corresponding email, funding, competing interests and exact AI products/models require
confirmed author wording. Human review and responsibility confirmations remain pending. No declaration
is inferred from a blank field. See submission_checklist.json.

## References

1. Tang et al. GEPIA2. Nucleic Acids Research (2019). doi:10.1093/nar/gkz430.
2. Wang et al. Unifying cancer and normal RNA sequencing data. Scientific Data (2018). doi:10.1038/sdata.2018.61.
3. Wilks et al. recount3. Genome Biology (2021). doi:10.1186/s13059-021-02533-6.
4. Fanfani et al. Reproducible processing of TCGA regulatory networks. GigaScience (2025). doi:10.1093/gigascience/giaf126.
5. Kolde et al. Robust rank aggregation. Bioinformatics (2012). doi:10.1093/bioinformatics/btr709.
6. Meinshausen and Buhlmann. Stability selection. JRSS B (2010). doi:10.1111/j.1467-9868.2010.00740.x.
"""
    (ROOT / "manuscript.md").write_text(draft)
    (ROOT / "README.md").write_text("# Engineering evidence v5\n\nPreparation only; publication disabled.\n\n"
        "Read manuscript.md, review.json and submission_checklist.json together. Every failed or partial result is retained.\n"
        "Tables and figures contain cohort aggregates. Private source inputs are referenced by hashes, not included.\n"
        "Run `make run-engineering-numerical`, `make run-engineering-workflow` and `make build-engineering-package` "
        "in the original frozen workspace. For a new machine, follow docs/engineering_completion.md and record a new "
        "execution identity rather than overwriting an old plan. Independent human reproduction remains pending.\n")
    (ROOT / "reproduce.sh").write_text("#!/bin/sh\nset -eu\nmake run-engineering-numerical\nmake run-engineering-workflow\nmake build-engineering-package\n")
    image = workflow["image_id"]
    subprocess.run(["docker", "run", "--rm", "--platform", "linux/amd64", "--network", "none",
                    "-v", f"{Path.cwd()}:/app", "-w", "/app", image, "Rscript",
                    "research/engineering_figures.R", str(ROOT)], check=True)
    identifiers = set()
    for path in Path("data/research").glob("*/sample_split_manifest.parquet"):
        frame = pl.read_parquet(path)
        for column in ("sample_id", "unit_id"):
            if column in frame.columns:
                identifiers.update(str(v) for v in frame[column].to_list() if v is not None and len(str(v)) > 5)
    matched = json.loads(Path("outputs/research/matched_processing_v1/report.json").read_text())
    frame = pl.read_parquet(matched["private_manifest_resource"]["path"])
    for column in ("native_sample_id", "recount_sample_id", "unit_id"):
        identifiers.update(str(v) for v in frame[column].to_list() if v is not None and len(str(v)) > 5)
    files = sorted(p for p in ROOT.rglob("*") if p.is_file() and p.name != "package_manifest.json")
    no_identifiers(files, identifiers)
    verify(sources)
    manifest = {"status": "verified_preparation_only", "publication_enabled": False,
                "file_count": len(files) + 1, "individual_identifier_scan": {"strings_checked": len(identifiers), "matches": 0},
                "files": [{"path": str(p.relative_to(ROOT)), "sha256": sha256_file(p), "bytes": p.stat().st_size}
                          for p in files]}
    write_once(ROOT / "package_manifest.json", manifest)
    archive = Path("outputs/releases/canceromicslake-engineering-v5.tar.gz")
    archive.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive, "w:gz") as stream:
        for path in sorted(ROOT.rglob("*")):
            if path.is_file():
                stream.add(path, arcname=f"canceromicslake-engineering-v5/{path.relative_to(ROOT)}")
    print(f"Prepared {len(files)+1} files; {len(identifiers)} identifier strings checked; publication disabled")
    return payload


if __name__ == "__main__":
    argparse.ArgumentParser().parse_args()
    print(build_package()["submission_status"])
