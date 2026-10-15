"""Build a new private review bundle without modifying the v1 or v2 reviews."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import polars as pl

from src.analytics.controlled_reference_study import sha256_file
from src.operations.research_review import build_research_review


def _check(item: dict) -> dict:
    path = Path(item["path"])
    if path.stat().st_size != item["bytes"] or sha256_file(path) != item["sha256"]:
        raise ValueError(f"v2 review source hash mismatch: {path}")
    return {"path": str(path), "sha256": item["sha256"]}


def load_v2(root: Path) -> tuple[dict, dict, list[dict]]:
    plan_path, report_path = root / "study_plan.json", root / "report.json"
    plan, report = json.loads(plan_path.read_text()), json.loads(report_path.read_text())
    if (report["status"] != "completed" or report["individual_identifiers_exported"] or
            not report["public_derived_mode"] or sha256_file(plan_path) != report["plan_file_sha256"]):
        raise ValueError("v2 processing study is incomplete or plan/privacy contract failed")
    checked = [{"path": str(p), "sha256": sha256_file(p)} for p in (plan_path, report_path)]
    for item in (plan["input_resources"] + plan["implementation_resources"] +
                 report["outputs"] + report["private_resources"] + [report["v1_report_resource"]]):
        checked.append(_check(item))
    if report["matched_specimens"] != plan["config"]["expected_matched_specimens"]:
        raise ValueError("v2 matched specimen count conflicts with frozen plan")
    return plan, report, checked


def _no_ids(text: str, identifiers: set[str]) -> None:
    if any(identifier in text for identifier in identifiers):
        raise ValueError("Individual specimen identifier found in aggregate review")


def build_v3_review(studies: list[str | Path], v1_root: str | Path,
                    v2_root: str | Path, output_root: str | Path,
                    simulation_root: str | Path = "outputs/research/reference_truth_simulation_v1",
                    failure_path: str | Path = "outputs/research/failure_experiments.json") -> dict:
    root, output = Path(v2_root), Path(output_root)
    _, v2, resources = load_v2(root)
    v1_report = json.loads(Path(v1_root, "report.json").read_text())
    if (sha256_file(Path(v1_root, "report.json")) != v2["v1_report_resource"]["sha256"] or
            v1_report["matched_specimens"] != v2["matched_specimens"]):
        raise ValueError("v1 and v2 matched-processing evidence disagree")
    manifest_path = Path(v1_report["private_manifest_resource"]["path"])
    manifest = pl.read_parquet(manifest_path)
    identifiers = {str(value) for col in ("native_sample_id", "recount_sample_id", "unit_id")
                   for value in manifest[col].to_list() if value is not None and len(str(value)) > 5}
    for item in v2["outputs"]:
        _no_ids(Path(item["path"]).read_text(), identifiers)
    payload = build_research_review(studies, simulation_root, failure_path, output, v1_root)
    payload["processing_v2"] = {
        "study_id": v2["study_id"], "matched_specimens": v2["matched_specimens"],
        "cohorts": v2["cohorts"], "effect_concordance": v2["effect_concordance"],
        "topk": v2["topk"], "annotation_workflow_audit": v2["annotation_workflow_audit"],
        "interpretation": v2["interpretation"]}
    payload["resources"].extend(resources)
    payload["resources"].extend({"path": str(path), "sha256": sha256_file(path)} for path in
                                (Path(__file__), Path(build_research_review.__code__.co_filename)))
    payload["publication_enabled"] = False
    payload["remaining"] = ["Independent reproduction and biological review",
                            "External cohort evaluation and full published-method comparator implementations",
                            "Engineering comparison against external workflows",
                            "Evidence of a substantive novel computational contribution"]
    review_text = json.dumps(payload, indent=2, allow_nan=False) + "\n"
    _no_ids(review_text, identifiers)
    (output / "review.json").write_text(review_text, encoding="utf-8")
    draft_path = output / "manuscript_draft.md"
    draft = draft_path.read_text(encoding="utf-8")
    section = ["### Post-v1 Tie and Annotation Diagnostic", "",
               "This post-v1 exploratory analysis reused exactly the same specimens and frozen input snapshot. "
               "Tie resolution is a computational sensitivity distribution, not a confidence interval. "
               "Case/donor bootstrap intervals are descriptive and conditional. Native TPM and recount3 "
               "coverage were never compared as numerical units.", "",
               "| Cancer | Universe | Genes | Kendall tau-b | Top-50 tie mean | Top-50 bootstrap interval |",
               "| --- | --- | ---: | ---: | ---: | --- |"]
    top = {(row["cancer_type"], row["universe"]): row for row in v2["topk"] if row["top_k"] == 50}
    for row in v2["effect_concordance"]:
        match = top.get((row["cancer_type"], row["universe"]))
        if match is None:
            section.append(f"| {row['cancer_type']} | {row['universe']} | {row['gene_count']} | incomplete | incomplete | incomplete |")
            continue
        tau = row["kendall_tau_b"]
        interval = (f"[{match['bootstrap_ci_low']:.3f}, {match['bootstrap_ci_high']:.3f}]"
                    if match["bootstrap_ci_low"] is not None else "unavailable")
        tau_label = f"{tau:.3f}" if tau is not None else "undefined"
        section.append(f"| {row['cancer_type']} | {row['universe']} | {row['gene_count']} | "
                       f"{tau_label} | {match['tie_mean_jaccard']:.3f} | {interval} |")
    section.extend(["", "A high within-specimen expression-rank correlation does not imply stable "
                    "cross-group effect rankings. Detection and annotation audits document possible "
                    "mismatches but cannot establish causation. All unfavorable comparisons are retained. "
                    "No independent cohort or reviewer has validated these findings.", ""])
    draft = draft.replace("### Engineering Faults", "\n".join(section) + "\n### Engineering Faults")
    _no_ids(draft, identifiers)
    draft_path.write_text(draft, encoding="utf-8")
    readme = output / "README.md"
    readme.write_text(readme.read_text(encoding="utf-8") +
                      "\nThis v3 bundle adds frozen matched-processing v2 diagnostics without changing older reviews. "
                      "Specimen and per-gene intermediate data remain private. Publication is disabled.\n")
    return payload


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--studies", nargs="+", required=True)
    parser.add_argument("--v1-root", default="outputs/research/matched_processing_v1")
    parser.add_argument("--v2-root", default="outputs/research/matched_processing_v2")
    parser.add_argument("--output", default="outputs/research/global_evidence_review_v3")
    args = parser.parse_args()
    result = build_v3_review(args.studies, args.v1_root, args.v2_root, args.output)
    print(f"Review status={result['status']} publication_enabled={result['publication_enabled']}")
