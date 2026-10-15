"""Build a reviewable, non-publication readiness summary from verified study artifacts."""
import argparse
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path

import polars as pl

from src.analytics.controlled_reference_study import sha256_file


def _load_study(root: Path) -> tuple[dict, dict, list[dict]]:
    report_path, plan_path = root / "report.json", root / "study_plan.json"
    report = json.loads(report_path.read_text())
    plan = json.loads(plan_path.read_text())
    canonical = json.dumps(plan, sort_keys=True, separators=(",", ":"), allow_nan=False)
    if hashlib.sha256(canonical.encode()).hexdigest() != report["plan_sha256"]:
        raise ValueError(f"Study plan integrity mismatch: {root}")
    resources = [{"path": str(p), "sha256": sha256_file(p)} for p in (report_path, plan_path)]
    for artifact in report.get("outputs", []):
        path = Path(artifact["path"])
        if not path.resolve().is_relative_to(root.resolve()) or sha256_file(path) != artifact["sha256"]:
            raise ValueError(f"Study artifact integrity mismatch: {path}")
        resources.append({"path": str(path), "sha256": artifact["sha256"]})
    return report, plan, resources


def _load_processing(root: Path) -> tuple[dict, list[dict]]:
    report_path, plan_path = root / "report.json", root / "study_plan.json"
    report = json.loads(report_path.read_text())
    plan = json.loads(plan_path.read_text())
    canonical = json.dumps(plan, sort_keys=True, separators=(",", ":"), allow_nan=False)
    if hashlib.sha256(canonical.encode()).hexdigest() != report["plan_sha256"]:
        raise ValueError("Matched-processing plan integrity mismatch")
    if report["status"] != "completed" or report["individual_identifiers_exported"]:
        raise ValueError("Matched-processing study is incomplete or public outputs contain identifiers")
    resources = [{"path": str(path), "sha256": sha256_file(path)} for path in (report_path, plan_path)]
    for item in (plan["input_resources"] + plan["implementation_resources"] + report["outputs"] +
                 [report["private_manifest_resource"], report["private_metrics_resource"]]):
        path = Path(item["path"])
        if sha256_file(path) != item["sha256"] or path.stat().st_size != item["bytes"]:
            raise ValueError(f"Matched-processing artifact integrity mismatch: {path}")
        resources.append({"path": str(path), "sha256": item["sha256"]})
    if report["matched_specimens"] != sum(row["matched_samples"] for row in plan["selection_summary"]):
        raise ValueError("Matched-processing specimen count inconsistent with frozen plan")
    return report, resources


def build_research_review(studies: list[str | Path], simulation_root: str | Path,
                          failure_path: str | Path, output_root: str | Path,
                          processing_root: str | Path | None = None) -> dict:
    output = Path(output_root)
    output.mkdir(parents=True, exist_ok=True)
    tables, study_summaries, resources = [], [], []
    measurement_counts = {}
    for study in studies:
        root = Path(study)
        report, plan, verified = _load_study(root)
        if report["status"] != "completed":
            raise ValueError(f"Incomplete study: {root}")
        if report.get("global_group_leakage_count", 0) != 0:
            raise ValueError(f"Global donor/case leakage in study: {root}")
        for source in plan["input_resources"]:
            if sha256_file(Path(source["path"])) != source["sha256"]:
                raise ValueError("Study input snapshot no longer matches current silver data")
            dataset = Path(source["path"]).stem.removeprefix("silver_expression_")
            count = pl.scan_parquet(source["path"]).select(pl.len()).collect().item()
            if dataset in measurement_counts and measurement_counts[dataset] != count:
                raise ValueError("Review combines inconsistent input measurement counts")
            measurement_counts[dataset] = count
        frame = pl.read_parquet(root / "heldout_evaluation.parquet")
        tables.append(frame.with_columns(pl.lit(report["study_id"]).alias("study_id")))
        comparison = frame.filter((pl.col("method") == "reference_maximin") & (pl.col("top_k") == 50))
        study_summaries.append({"study_id": report["study_id"], "pilot": report["pilot"],
                                "paired_only": plan["config"].get("paired_only", False),
                                "partition_scope": report.get("partition_scope", "historical_per_cancer_only"),
                                "global_group_leakage_count": report.get("global_group_leakage_count"),
                                "cohort_audit": report["cohort_audit"],
                                "lower_quantile_minus_maximin_at_k50": comparison.select(
                                    "cancer_type", "proposed_minus_baseline_replication_fraction",
                                    "proposed_minus_baseline_replication_fraction_ci_low",
                                    "proposed_minus_baseline_replication_fraction_ci_high").to_dicts()})
        resources.extend(verified)
    evaluations = pl.concat(tables)
    table_path = output / "heldout_methods.csv"
    evaluations.sort("study_id", "cancer_type", "top_k", "method").write_csv(table_path)

    simulation = Path(simulation_root)
    truth_report, _, verified = _load_study(simulation)
    truth_path = simulation / "truth_metrics.parquet"
    if sha256_file(truth_path) != truth_report["output_sha256"]:
        raise ValueError("Simulation artifact integrity mismatch")
    resources.extend(verified + [{"path": str(truth_path), "sha256": sha256_file(truth_path)}])
    truth = pl.read_parquet(truth_path)
    truth_summary = truth.group_by("scenario", "method", "top_k").agg(
        pl.col("precision_at_k").mean(), pl.col("heldout_reference_replication_fraction").mean()
    ).sort("scenario", "method", "top_k")
    truth_summary.write_csv(output / "simulation_methods.csv")
    counterexample = truth_summary.filter((pl.col("scenario") == "shared_normal_bias") &
                                          (pl.col("method") == "reference_stability_lower_quantile") &
                                          (pl.col("top_k") == 25)).to_dicts()
    fault_path = Path(failure_path)
    faults = json.loads(fault_path.read_text())
    if faults["status"] != "passed" or not all(row["passed"] for row in faults["scenarios"]):
        raise ValueError("Failure experiments are not all passed")
    resources.append({"path": str(fault_path), "sha256": sha256_file(fault_path)})
    processing = None
    if processing_root is not None:
        processing, checked = _load_processing(Path(processing_root))
        resources.extend(checked)
        if not processing["public_derived_mode"]:
            raise ValueError("Matched-processing review requires explicit public-derived release evidence")
    remaining = ["Independent reproduction and biological review",
                 "External cohort evaluation and full published-method comparator implementations",
                 "Engineering comparison against external workflows",
                 "Evidence of a substantive novel computational contribution"]
    if processing is None:
        remaining.insert(1, "Verified specimen-matched native/recount3 processing comparison")
    payload = {"generated_at": datetime.now(UTC).isoformat(), "status": "research_incomplete",
               "measurement_counts": measurement_counts,
               "publication_enabled": False, "studies": study_summaries,
               "shared_bias_counterexample": counterexample, "failure_scenarios_passed": len(faults["scenarios"]),
               "independent_reproduction": faults["independent_reproduction"], "resources": resources,
               "processing_study": {"study_id": processing["study_id"],
                                    "matched_specimens": processing["matched_specimens"],
                                    "effect_summary": processing["effect_summary"],
                                    "specimen_summary": processing["specimen_summary"]} if processing else None,
               "remaining": remaining,
               "interpretation": "Reference reproducibility is not biological truth. Conditional intervals and constructed simulations do not establish novelty."}
    (output / "review.json").write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n")
    (output / "README.md").write_text(
        "# Research Evidence Review\n\n"
        "Status: research incomplete; publication disabled.\n\n"
        "`heldout_methods.csv` contains every method/cancer/top-k result for the listed studies; "
        "`simulation_methods.csv` contains all constructed scenarios. `review.json` records "
        "source checksums, paired-study coverage, comparison intervals and remaining requirements.\n\n"
        "Agreement with both reference populations does not establish biological truth. "
        "The shared-normal-bias simulation is an explicit counterexample. There is no "
        "independent human reproduction or proven novel-method claim.\n")
    lines = ["# Reference-Sensitive Cancer-Omics Evaluation: A Reproducibility and Failure-Analysis Draft",
             "", "**Exploratory working draft. Publication disabled; independent review pending.**", "",
             "## Partition Audit", "",
             ("All included studies report a globally consistent donor/case partition across configured cancers. "
              "Shared donors still create dependence across cancer estimates; these are not independent cohorts."
              if all(s["partition_scope"] == "global_across_all_configured_projects" and
                     s["global_group_leakage_count"] == 0 for s in study_summaries)
              else "Historical studies are included without a verified global donor/case partition. "
                   "Their within-cancer checks must not support a globally leakage-free claim. "
                   "A subsequent private-manifest audit found 26 GTEx donors crossing folds across cancers "
                   "in native v1 and paired v2. Corrected global-partition runs are required."), "",
             "## Abstract", "",
             "CancerOmicsLake evaluates reproducible cancer-omics infrastructure and reference-sensitive "
             "gene prioritization. Patient/donor-separated studies compare fixed development selections "
             "on held-out samples using balanced normal references, expression "
             "filtering, subsampling, and scale/pseudocount sensitivity. Constructed truth scenarios "
             "and isolated production-guard failures complement the cohort experiments. These experiments "
             "do not establish a novel ranking method or validate biomarkers.", "",
             "## Related Work", "",
             "[GEPIA2](https://doi.org/10.1093/nar/gkz430) already supports integrated TCGA/GTEx "
             "expression analysis. [tcga-data-nf](https://doi.org/10.1093/gigascience/giaf126) demonstrates "
             "reproducible TCGA workflow infrastructure. [Wang et al.](https://doi.org/10.1038/sdata.2018.61) "
             "address cross-source harmonization, while [Arora et al.](https://doi.org/10.1038/s41598-020-59516-z) "
             "show processing-dependent expression variation on matched samples. Integration or reference "
             "sensitivity alone is therefore not novel. This draft examines traceable evaluation and "
             "failure behavior; external-workflow superiority remains untested.", "",
             "## Methods", "",
             "Whole TCGA patients and GTEx donors are separated before development-only filtering and "
             "ranking. Where a paired arm is listed in this bundle, it uses the same TCGA cases for "
             "tumor and adjacent-normal samples. "
             "TCGA case bootstrap draws preserve pairing; GTEx donors are resampled separately. Held-out "
             "intervals are conditional on the selected development universe and rankings, not "
             "unconditional discovery guarantees. Repeated development subsamples overlap and are "
             "descriptive sensitivity experiments. Native TPM units do not eliminate processing, "
             "collection or tissue-composition confounding.", "",
             "Baselines include single-reference fold change, rank-biserial effects, mean ranks, "
             "an RRA-style heuristic and simple reference maximin. The proposed lower-quantile bootstrap "
             "maximin score is experimental; published RRA and stability-selection error guarantees "
             "are not claimed. Top-k sizes and numerical parameters were fixed before pilot results. "
             "Pilot holdouts have been inspected, so subsequent cohort analyses are not represented "
             "as untouched confirmatory validation.", "", "## Results", ""]
    lines.append("Verified input snapshot: " + ", ".join(f"{count:,} {name.upper()} expression measurement rows"
                                                          for name, count in sorted(measurement_counts.items())) +
                 ". These are not source-file, donor or patient counts.")
    lines.extend(["", "### Lower-Quantile Score Versus Simple Maximin", "",
                  "Every method/cancer/top-k result is retained in [the full table](heldout_methods.csv). "
                  "The following top-50 paired differences are reference-replication fractions, "
                  "not biological-validation rates or multiplicity-adjusted tests.", "",
                  "| Study | Cancer | Difference | Conditional interval |", "| --- | --- | ---: | --- |"])
    for study in study_summaries:
        for row in study["lower_quantile_minus_maximin_at_k50"]:
            lines.append(f"| {study['study_id']} | {row['cancer_type']} | "
                         f"{row['proposed_minus_baseline_replication_fraction']:.3f} | "
                         f"[{row['proposed_minus_baseline_replication_fraction_ci_low']:.3f}, "
                         f"{row['proposed_minus_baseline_replication_fraction_ci_high']:.3f}] |")
    lines.extend(["", "### Constructed Shared-Bias Counterexample", ""])
    for row in counterexample:
        lines.append(f"At top-{row['top_k']}, mean truth precision was {row['precision_at_k']:.3f} "
                     f"despite reference replication {row['heldout_reference_replication_fraction']:.3f}. "
                     "This constructed scenario shows that shared reference bias can mimic tumor biology; "
                     "it is not a measured error rate for real cancer genes.")
    if processing is not None:
        lines.extend(["", "### Exact-Specimen Processing Sensitivity", "",
                      f"The pre-metric-frozen processing audit matched {processing['matched_specimens']} "
                      "specimens across native TPM and publicly released recount3 AUC-scaled coverage. "
                      "Within-specimen rank agreement was measured on shared genes with paired-unit "
                      "bootstrap intervals. Expression values were not compared as common units. "
                      "Case/donor identities and per-specimen metrics remain private.", "",
                      "| Cancer | Matched tumors | Matched normals | Top-50 Jaccard | Shared genes | Native cutoff ties |", "| --- | ---: | ---: | ---: | ---: | ---: |"])
        for row in processing["effect_summary"]:
            if row["top_k"] == 50:
                lines.append(f"| {row['cancer_type']} | {row['matched_tumor_specimens']} | "
                             f"{row['matched_normal_specimens']} | {row['top_k_jaccard']:.3f} | "
                             f"{row['shared_top_genes']} | {row['native_boundary_tie_count']} |")
        lines.extend(["", "These are descriptive within-specimen processing comparisons. Shared "
                      "specimens are not an independent biological validation cohort. Top-25 "
                      "effect lists have no shared genes in any cancer; top-50 lists share only "
                      "zero to two. Hundreds of native effects tie at the cutoff, so top-list "
                      "overlap is strongly tie-sensitive. Direction agreement among only shared "
                      "top genes cannot establish general directional concordance. Paired-unit "
                      "bootstrap intervals cover specimen medians, not effect-list overlap."])
    outstanding = ("published-method implementations, external workflow comparisons and independent "
                   "reproduction" if processing else
                   "specimen-matched processing comparisons, published-method implementations, external "
                   "workflow comparisons and independent reproduction")
    lines.extend(["", "### Engineering Faults", "",
                  f"{len(faults['scenarios'])} offline synthetic scenarios passed production guards. "
                  "Retry-disabled and byte-count-only controls isolate specific guardrail benefits. "
                  "Transport is mocked; real-network resume performance and external-tool superiority "
                  "are not established.", "", "## Limitations and Conclusion", "",
                  "Reference agreement is not biological truth, and saturated reference-replication "
                  "endpoints limit discrimination between strong ranking strategies. These results "
                  "support an engineering and evaluation contribution, not an established novel "
                  "statistical method or a RECOMB acceptance claim. External validation, verified "
                  + outstanding + " remain outstanding. All author metadata and publication/deposit "
                  "approvals remain unconfirmed.", "",
                  "Evidence sources and checksums: [review.json](review.json). This draft does not "
                  "replace or reseal the older manuscript package or authorize public release."])
    (output / "manuscript_draft.md").write_text("\n".join(lines) + "\n")
    return payload


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--studies", nargs="+", required=True)
    parser.add_argument("--simulation", default="outputs/research/reference_truth_simulation_v1")
    parser.add_argument("--failures", default="outputs/research/failure_experiments.json")
    parser.add_argument("--processing", default=None)
    parser.add_argument("--output", default="outputs/research/evidence_review")
    args = parser.parse_args()
    build_research_review(args.studies, args.simulation, args.failures, args.output, args.processing)
