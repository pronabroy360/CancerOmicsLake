"""Compose a new aggregate-only review without changing earlier evidence bundles."""
from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
from pathlib import Path

import polars as pl

from src.analytics.controlled_reference_study import sha256_file


def build_review(previous_root: Path = Path("outputs/research/global_evidence_review_v3"),
                 comparator_root: Path = Path("outputs/research/published_rra_baseline_v1"),
                 output_root: Path = Path("outputs/research/global_evidence_review_v4"),
                 private_root: Path = Path("data/research")) -> dict:
    prior = json.loads((previous_root / "review.json").read_text())
    report = json.loads((comparator_root / "report.json").read_text())
    plan_path = comparator_root / "study_plan.json"
    plan = json.loads(plan_path.read_text())
    from src.analytics.controlled_reference_study import _canonical
    import hashlib
    if (report["status"] != "completed" or report["publication_enabled"] is not False
            or report["individual_identifiers_exported"] is not False
            or hashlib.sha256(_canonical(plan).encode()).hexdigest() != report["plan_sha256"]):
        raise RuntimeError("Published RRA comparator is not frozen and complete")
    verified = []
    for item in (prior["resources"] + plan["implementation_resources"] + plan["input_resources"]
                 + plan["frozen_resources"] + report["outputs"]):
        path = Path(item["path"])
        if sha256_file(path) != item["sha256"]:
            raise RuntimeError(f"Review resource drift: {path}")
        verified.append({"path": str(path), "sha256": item["sha256"]})
    expected = {(s, c, k) for s in plan["studies"]
                for c in ("TCGA-BRCA", "TCGA-LUAD", "TCGA-COAD") for k in (25, 50, 100)}
    actual = {(r["study_id"], r["cancer_type"], r["top_k"]) for r in report["comparisons"]}
    if expected != actual or len(report["comparisons"]) != len(expected):
        raise RuntimeError("Comparator review is missing study/cancer/top-k cells")
    identifiers = set()
    for name in plan["studies"]:
        manifest = pl.read_parquet(private_root / name / "sample_split_manifest.parquet")
        identifiers.update(str(value) for column in ("sample_id", "unit_id")
                           for value in manifest[column].to_list() if value is not None and len(str(value)) > 5)
    payload = {"generated_at": datetime.now(UTC).isoformat(), "status": "research_incomplete",
               "publication_enabled": False, "previous_review": {"path": str(previous_root / "review.json"),
                                                                   "sha256": sha256_file(previous_root / "review.json")},
               "published_rra": {"study_id": report["study_id"], "package": report["r_package"],
                                 "image": report["r_image"], "comparisons": report["comparisons"],
                                 "limitations": report["limitations"]},
               "resources": verified + [{"path": str(comparator_root / filename),
                                          "sha256": sha256_file(comparator_root / filename)}
                                         for filename in ("study_plan.json", "report.json")],
               "remaining": ["Independent human reproduction", "External workflow utility comparison",
                             "Biological validation and substantive novelty assessment"]}
    text = json.dumps(payload, indent=2, allow_nan=False) + "\n"
    if any(identifier in text for identifier in identifiers):
        raise RuntimeError("Individual identifier in aggregate comparator review")
    output_root.mkdir(parents=True, exist_ok=True)
    lines = ["# Published RRA Comparator", "", "Post-v2 exploratory comparison; not independent validation.",
             "Scores are rankings only, never calibrated significance because the two input lists share tumors.",
             "All earlier review bundles are retained unchanged.", "",
             "| Study | Cancer | Top-k | RRA replication | Proposed minus RRA | 95% paired interval | Discordant selected |",
             "| --- | --- | ---: | ---: | ---: | --- | ---: |"]
    for row in sorted(report["comparisons"], key=lambda x: (x["study_id"], x["cancer_type"], x["top_k"])):
        lines.append(f"| {row['study_id']} | {row['cancer_type']} | {row['top_k']} | "
                     f"{row['replication_fraction']:.3f} | {row['proposed_minus_baseline_replication_fraction']:.3f} | "
                     f"[{row['proposed_minus_baseline_replication_fraction_ci_low']:.3f}, "
                     f"{row['proposed_minus_baseline_replication_fraction_ci_high']:.3f}] | "
                     f"{row['discordant_reference_direction_count']}/{row['selected_count']} |")
    lines += ["", "Independent reproduction, external workflows and biological validation remain unverified.",
              "Publication remains disabled."]
    draft = "\n".join(lines) + "\n"
    if any(identifier in draft for identifier in identifiers):
        raise RuntimeError("Individual identifier in aggregate comparator draft")
    review_path, draft_path = output_root / "review.json", output_root / "manuscript_addendum.md"
    if review_path.exists():
        old = json.loads(review_path.read_text())
        if {k: v for k, v in old.items() if k != "generated_at"} != {
                k: v for k, v in payload.items() if k != "generated_at"}:
            raise RuntimeError("Frozen comparator review differs on rerun")
        if not draft_path.exists() or draft_path.read_text() != draft:
            raise RuntimeError("Frozen comparator manuscript addendum differs on rerun")
        return old
    review_path.write_text(text)
    draft_path.write_text(draft)
    return payload


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--previous-root", type=Path, default=Path("outputs/research/global_evidence_review_v3"))
    parser.add_argument("--comparator-root", type=Path, default=Path("outputs/research/published_rra_baseline_v1"))
    parser.add_argument("--output-root", type=Path, default=Path("outputs/research/global_evidence_review_v4"))
    args = parser.parse_args()
    print(build_review(args.previous_root, args.comparator_root, args.output_root)["status"])
