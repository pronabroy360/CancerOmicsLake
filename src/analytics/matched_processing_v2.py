"""Versioned, aggregate-only follow-up to the frozen matched-processing v1 study."""
from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
import hashlib
import json
from importlib.metadata import version
from pathlib import Path
import subprocess
import xml.sax.saxutils as xml

import numpy as np
import polars as pl
import yaml

from src.analytics.controlled_reference_study import lock_plan, sha256_file
from src.analytics.matched_processing_metrics import paired_expression
from src.analytics.matched_processing_v2_metrics import (
    bootstrap_indices, chunked_effects, concordance, effect_distribution,
    informative_genes, tie_overlap,
)


@dataclass(frozen=True)
class Config:
    study_id: str = "matched_processing_v2"
    expected_matched_specimens: int = 617
    seed: int = 20261014
    top_k: tuple[int, ...] = (25, 50, 100)
    detection_prevalence: float = .20
    minimum_informative_genes: int = 100
    direction_effect_threshold: float = .20
    tie_draws: int = 1000
    bootstrap_repeats: int = 200
    bootstrap_tie_draws: int = 100
    gene_chunk_size: int = 512
    primary_colon_tissue: str = "Colon - Transverse"

    def __post_init__(self) -> None:
        if (self.study_id != "matched_processing_v2" or self.expected_matched_specimens < 1 or
                self.seed < 0 or not 0 < self.detection_prevalence <= 1 or
                not 0 < self.direction_effect_threshold <= 1 or
                self.minimum_informative_genes < 100 or self.tie_draws < 1 or
                self.bootstrap_repeats < 1 or self.bootstrap_tie_draws < 1 or
                self.gene_chunk_size < 1 or not self.top_k or
                any(type(k) is not int or k < 1 for k in self.top_k) or
                self.primary_colon_tissue not in ("Colon - Transverse", "Colon - Sigmoid")):
            raise ValueError("Invalid matched-processing v2 configuration")


def load_config(path: str | Path) -> Config:
    payload = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or set(payload) - set(Config.__dataclass_fields__):
        raise ValueError("Invalid or unknown matched-processing v2 configuration fields")
    payload["top_k"] = tuple(payload.get("top_k", (25, 50, 100)))
    return Config(**payload)


def resource(path: Path) -> dict:
    return {"path": str(path), "bytes": path.stat().st_size, "sha256": sha256_file(path)}


def _row_count(path: Path) -> int:
    return pl.scan_parquet(path).select(pl.len()).collect().item()


def prepare(config_path: str | Path, v1_root: str | Path, silver_dir: str | Path,
            private_root: str | Path, output_root: str | Path) -> tuple[Config, pl.DataFrame, dict, Path, Path]:
    config = load_config(config_path)
    v1, silver = Path(v1_root), Path(silver_dir)
    private, output = Path(private_root) / config.study_id, Path(output_root) / config.study_id
    previous = json.loads((v1 / "report.json").read_text(encoding="utf-8"))
    if (previous["status"] != "completed" or previous["matched_specimens"] != config.expected_matched_specimens or
            previous["individual_identifiers_exported"] or not previous["public_derived_mode"]):
        raise ValueError("v1 release, privacy or specimen contract is not satisfied")
    sources = [v1 / "study_plan.json", v1 / "report.json",
               Path(previous["private_manifest_resource"]["path"]),
               silver / "silver_expression_tcga.parquet", silver / "silver_expression_gtex.parquet",
               silver / "silver_expression_recount3_matched_processing_v1.parquet"]
    for item in [previous["private_manifest_resource"], previous["expression_resource"]]:
        path = Path(item["path"])
        if path.stat().st_size != item["bytes"] or sha256_file(path) != item["sha256"]:
            raise ValueError(f"v1 frozen artifact has changed: {path}")
    previous_plan = json.loads((v1 / "study_plan.json").read_text(encoding="utf-8"))
    canonical = json.dumps(previous_plan, sort_keys=True, separators=(",", ":"), allow_nan=False)
    if hashlib.sha256(canonical.encode()).hexdigest() != previous["plan_sha256"]:
        raise ValueError("v1 frozen plan hash does not match its report")
    for item in previous_plan["input_resources"] + previous_plan["implementation_resources"]:
        path = Path(item["path"])
        if path.stat().st_size != item["bytes"] or sha256_file(path) != item["sha256"]:
            raise ValueError(f"v1 frozen input or implementation has changed: {path}")
    manifest = pl.read_parquet(sources[2]).sort("source", "cohort", "recount_sample_id")
    if manifest.height != config.expected_matched_specimens or manifest.select(
            "source", "recount_sample_id").is_duplicated().any():
        raise ValueError("v1 private specimen manifest is incomplete or ambiguous")
    for source, column in (("TCGA", "sample_id"), ("GTEx", "gtex_sample_id")):
        block = manifest.filter(pl.col("source") == source)
        units = (pl.scan_parquet(silver / f"silver_expression_{source.lower()}.parquet")
                 .filter(pl.col(column).is_in(block["native_sample_id"].to_list()))
                 .select("expression_unit").unique().collect()["expression_unit"].to_list())
        if units != ["TPM"]:
            raise ValueError(f"Matched native {source} values are not exclusively TPM: {units}")
    recount_units = (pl.scan_parquet(sources[-1]).select("expression_unit").unique()
                     .collect()["expression_unit"].to_list())
    if recount_units != ["AUC-scaled coverage count (40M target)"]:
        raise ValueError("Matched recount3 expression unit is not the frozen coverage scale")
    code = [Path(__file__), Path(chunked_effects.__code__.co_filename),
            Path(paired_expression.__code__.co_filename)]
    try:
        revision = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True,
                                  text=True, check=False).stdout.strip() or "unavailable"
    except OSError:
        revision = "unavailable"
    plan = {"protocol_version": "2.0_post_v1_exploratory", "config": asdict(config),
            "v1_plan_sha256": previous["plan_sha256"], "input_resources": [resource(p) for p in sources],
            "input_row_counts": {p.stem: _row_count(p) for p in sources if p.suffix == ".parquet"},
            "implementation_resources": [resource(p) for p in code],
            "dependencies": {name: version(name) for name in ("numpy", "polars", "scipy", "PyYAML")},
            "code_revision": revision, "public_derived_mode": True}
    plan_sha = lock_plan(output / "study_plan.json", plan)
    private.mkdir(parents=True, exist_ok=True)
    return config, manifest, plan, private, output


def _group_matrices(frame: pl.DataFrame, sample_ids: list[str], genes: list[str]) -> tuple[np.ndarray, np.ndarray]:
    index = pl.DataFrame({"gene_id": genes})
    arrays = []
    for column in ("native_value", "recount_value"):
        wide = frame.select("gene_id", "recount_sample_id", column).pivot(
            index="gene_id", on="recount_sample_id", values=column)
        array = index.join(wide, on="gene_id", how="left").select(sample_ids).to_numpy()
        if not np.isfinite(array).all() or (array < 0).any():
            raise ValueError("Incomplete, negative or nonfinite matched expression matrix")
        arrays.append(array)
    return arrays[0], arrays[1]


def load_cohort(manifest: pl.DataFrame, silver_dir: Path, cancer: str,
                code: str, tissue: str) -> tuple[np.ndarray, dict, dict, dict]:
    tumor_manifest = manifest.filter((pl.col("source") == "TCGA") & (pl.col("cohort") == code))
    normal_manifest = manifest.filter((pl.col("source") == "GTEx") & (pl.col("tissue_site") == tissue))
    if not tumor_manifest.height or not normal_manifest.height:
        raise ValueError(f"No matched tumor or normal specimens for {cancer}")
    recount = silver_dir / "silver_expression_recount3_matched_processing_v1.parquet"
    tumor = paired_expression(tumor_manifest, silver_dir / "silver_expression_tcga.parquet", recount, "TCGA")
    normal = paired_expression(normal_manifest, silver_dir / "silver_expression_gtex.parquet", recount, "GTEx")
    tumor_ids = sorted(tumor_manifest["recount_sample_id"].to_list())
    normal_ids = sorted(normal_manifest["recount_sample_id"].to_list())
    common = (pl.concat([tumor, normal]).group_by("gene_id")
              .agg(pl.col("recount_sample_id").n_unique().alias("n"))
              .filter(pl.col("n") == len(tumor_ids) + len(normal_ids))
              .sort("gene_id")["gene_id"].to_list())
    if len(common) < 100:
        raise ValueError(f"Insufficient complete shared genes for {cancer}")
    matrices = {}
    for group, frame, ids in (("tumor", tumor, tumor_ids), ("normal", normal, normal_ids)):
        native, recounted = _group_matrices(frame.filter(pl.col("gene_id").is_in(common)), ids, common)
        matrices[group] = (native, recounted)
    def ordered_units(block: pl.DataFrame, ids: list[str]) -> list[str]:
        lookup = dict(zip(block["recount_sample_id"], block["unit_id"], strict=True))
        return [lookup[sample] for sample in ids]
    units = {"tumor": ordered_units(tumor_manifest, tumor_ids),
             "normal": ordered_units(normal_manifest, normal_ids)}
    audit = {"cancer_type": cancer, "normal_tissue": tissue, "complete_shared_genes": len(common),
             "matched_tumors": len(tumor_ids), "matched_normals": len(normal_ids),
             "tumor_cases": len(set(units["tumor"])), "normal_donors": len(set(units["normal"]))}
    paired = {"native": (matrices["tumor"][0], matrices["normal"][0]),
              "recount3": (matrices["tumor"][1], matrices["normal"][1])}
    return np.asarray(common), paired, units, audit


def _metric_rows(genes: np.ndarray, effects: dict[str, np.ndarray], mask: np.ndarray,
                 config: Config, cancer: str, universe: str, seed: int) -> tuple[dict, list[dict]]:
    count = int(mask.sum())
    row = {"cancer_type": cancer, "universe": universe, "gene_count": count,
           "status": "completed" if count >= max(config.minimum_informative_genes, max(config.top_k))
           else "incomplete_too_few_genes"}
    if row["status"] != "completed":
        return row, []
    native, recount = effects["native"][mask], effects["recount3"][mask]
    row.update(concordance(native, recount, config.direction_effect_threshold))
    for label, values in (("native", native), ("recount3", recount)):
        row.update({f"{label}_{key}": value for key, value in effect_distribution(values).items()})
    rng = np.random.default_rng(seed)
    top_rows = []
    for k in config.top_k:
        top_rows.append({"cancer_type": cancer, "universe": universe, "top_k": k,
                         **tie_overlap(genes[mask], native, recount, k, config.tie_draws, rng)})
    return row, top_rows


def _interval(values: list[float | None]) -> tuple[float | None, float | None]:
    valid = [v for v in values if v is not None and np.isfinite(v)]
    return (float(np.quantile(valid, .025)), float(np.quantile(valid, .975))) if valid else (None, None)


def _bootstrap(matrices: dict, units: dict, genes: np.ndarray, masks: dict[str, np.ndarray],
               config: Config, cancer: str, private: Path) -> tuple[list[dict], list[dict]]:
    rng = np.random.default_rng(config.seed + {"TCGA-BRCA": 0, "TCGA-COAD": 1,
                                                "TCGA-LUAD": 2}[cancer] * 1000)
    concordance_draws, overlap_draws = [], []
    for replicate in range(config.bootstrap_repeats):
        if replicate and replicate % 25 == 0:
            print(f"v2 {cancer}: {replicate}/{config.bootstrap_repeats} biological resamples", flush=True)
        sample = {group: bootstrap_indices(units[group], rng) for group in ("tumor", "normal")}
        effects = {name: chunked_effects(tumor, normal, sample["tumor"], sample["normal"],
                                         config.gene_chunk_size)
                   for name, (tumor, normal) in matrices.items()}
        for universe, mask in masks.items():
            if mask.sum() < max(config.minimum_informative_genes, max(config.top_k)):
                continue
            result = concordance(effects["native"][mask], effects["recount3"][mask],
                                 config.direction_effect_threshold)
            concordance_draws.append({"cancer_type": cancer, "universe": universe,
                                      "replicate": replicate, **result})
            for k in config.top_k:
                tie = tie_overlap(genes[mask], effects["native"][mask], effects["recount3"][mask],
                                  k, config.bootstrap_tie_draws, rng)
                overlap_draws.append({"cancer_type": cancer, "universe": universe,
                                     "replicate": replicate, "top_k": k,
                                     "tie_mean_jaccard": tie["tie_mean_jaccard"]})
    pl.DataFrame(concordance_draws).write_parquet(private / f"{cancer}_concordance_draws.parquet")
    pl.DataFrame(overlap_draws).write_parquet(private / f"{cancer}_overlap_draws.parquet")
    return concordance_draws, overlap_draws


def annotation_audit(manifest: pl.DataFrame, silver_dir: Path) -> list[dict]:
    recount_path = silver_dir / "silver_expression_recount3_matched_processing_v1.parquet"
    result = []
    for source, cohort in (("TCGA", "BRCA"), ("TCGA", "LUAD"), ("TCGA", "COAD"),
                           ("GTEx", "BREAST"), ("GTEx", "LUNG"), ("GTEx", "COLON")):
        block = manifest.filter((pl.col("source") == source) & (pl.col("cohort") == cohort))
        column = "sample_id" if source == "TCGA" else "gtex_sample_id"
        detail = "pipeline_workflow" if source == "TCGA" else "source_version"
        native = (pl.scan_parquet(silver_dir / f"silver_expression_{source.lower()}.parquet")
                  .filter(pl.col(column).is_in(block["native_sample_id"].to_list())))
        recount = (pl.scan_parquet(recount_path).filter((pl.col("source") == source) &
                                                   pl.col("sample_id").is_in(block["recount_sample_id"].to_list())))
        if "gene_symbol" not in native.collect_schema():
            native = native.with_columns(pl.lit("unknown").alias("gene_symbol"))
        if "gene_symbol" not in recount.collect_schema():
            recount = recount.with_columns(pl.lit("unknown").alias("gene_symbol"))
        native_map = native.select("gene_id", "gene_symbol").unique().collect()
        recount_map = recount.select("gene_id", "gene_symbol").unique().collect()
        native_genes = set(native_map["gene_id"])
        recount_genes = set(recount_map["gene_id"])
        shared = native_genes & recount_genes
        native_symbols = {gene: set(values) for gene, values in native_map.group_by("gene_id").agg(
            pl.col("gene_symbol").unique()).iter_rows()}
        recount_symbols = {gene: set(values) for gene, values in recount_map.group_by("gene_id").agg(
            pl.col("gene_symbol").unique()).iter_rows()}
        workflow = (native.select(detail).unique().collect()[detail].to_list()
                    if detail in native.collect_schema() else ["unknown"])
        external = (recount.select("external_annotation").unique().collect()["external_annotation"].to_list()
                    if "external_annotation" in recount.collect_schema() else ["unknown"])
        result.append({"source": source, "cohort": cohort, "matched_specimens": block.height,
                       "native_gene_ids": len(native_genes), "recount_gene_ids": len(recount_genes),
                       "shared_gene_ids": len(shared), "native_only_gene_ids": len(native_genes - recount_genes),
                       "recount_only_gene_ids": len(recount_genes - native_genes),
                       "native_multi_symbol_gene_ids": sum(len(v) > 1 for v in native_symbols.values()),
                       "recount_multi_symbol_gene_ids": sum(len(v) > 1 for v in recount_symbols.values()),
                       "shared_symbol_conflicts": sum(
                           {str(v).upper() for v in native_symbols[g]} !=
                           {str(v).upper() for v in recount_symbols[g]} for g in shared),
                       "native_par_y_genes": sum(g.endswith("_PAR_Y") for g in native_genes),
                       "recount_par_y_genes": sum(g.endswith("_PAR_Y") for g in recount_genes),
                       "native_workflow_or_version": sorted(str(v) if v is not None else "unknown" for v in workflow),
                       "recount_annotation": sorted(str(v) if v is not None else "unknown" for v in external)})
    return result


def _write_figure(rows: list[dict], path: Path) -> None:
    chosen = [r for r in rows if r["universe"] == "all_shared" and r["top_k"] == 50]
    lines = ['<svg xmlns="http://www.w3.org/2000/svg" width="850" height="320">',
             '<rect width="100%" height="100%" fill="#f7f7f2"/>',
             '<text x="25" y="35" font-family="sans-serif" font-size="19">Tie-aware top-50 overlap</text>',
             '<text x="25" y="57" font-family="sans-serif" font-size="12">Point tie-resolution mean; bootstrap intervals are in the table</text>']
    for i, row in enumerate(chosen):
        y = 95 + i * 70
        label = xml.escape(row["cancer_type"])
        value = row["tie_mean_jaccard"]
        lines.extend([f'<text x="25" y="{y + 18}" font-family="sans-serif">{label}</text>',
                      f'<rect x="180" y="{y}" width="500" height="24" fill="#d0ddd4"/>',
                      f'<rect x="180" y="{y}" width="{500 * value:.2f}" height="24" fill="#147d70"/>',
                      f'<text x="700" y="{y + 18}" font-family="sans-serif">{value:.3f}</text>'])
    lines.append("</svg>")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_study(config_path: str | Path = "configs/matched_processing_v2.yml",
              v1_root: str | Path = "outputs/research/matched_processing_v1",
              silver_dir: str | Path = "data/silver",
              private_root: str | Path = "data/research",
              output_root: str | Path = "outputs/research", prepare_only: bool = False) -> dict:
    config, manifest, plan, private, output = prepare(config_path, v1_root, silver_dir,
                                                      private_root, output_root)
    plan_sha = sha256_file(output / "study_plan.json")
    if prepare_only:
        return {"status": "prepared", "study_id": config.study_id,
                "matched_specimens": manifest.height, "plan_file_sha256": plan_sha}
    report_path = output / "report.json"
    if report_path.exists():
        report = json.loads(report_path.read_text(encoding="utf-8"))
        if report["plan_file_sha256"] != plan_sha:
            raise ValueError("v2 report uses a different frozen plan")
        for item in report["outputs"] + report["private_resources"]:
            path = Path(item["path"])
            if path.stat().st_size != item["bytes"] or sha256_file(path) != item["sha256"]:
                raise ValueError("v2 completed output was modified")
        return report
    all_metrics, all_top, all_audit, all_boot_c, all_boot_o = [], [], [], [], []
    silver = Path(silver_dir)
    for cancer, code, tissue in (("TCGA-BRCA", "BRCA", "Breast - Mammary Tissue"),
                                 ("TCGA-COAD", "COAD", config.primary_colon_tissue),
                                 ("TCGA-LUAD", "LUAD", "Lung")):
        genes, matrices, units, audit = load_cohort(manifest, silver, cancer, code, tissue)
        all_audit.append(audit)
        mask = informative_genes(matrices, config.detection_prevalence)
        masks = {"all_shared": np.ones(len(genes), dtype=bool), "informative": mask}
        audit["informative_genes"] = int(mask.sum())
        for group in ("tumor", "normal"):
            native = matrices["native"][0 if group == "tumor" else 1]
            recount = matrices["recount3"][0 if group == "tumor" else 1]
            audit[f"{group}_detection_discordant_cells"] = int(((native > 0) != (recount > 0)).sum())
            audit[f"{group}_detection_cells"] = int(native.size)
        effects = {name: chunked_effects(tumor, normal,
                                         np.arange(tumor.shape[1]), np.arange(normal.shape[1]),
                                         config.gene_chunk_size)
                   for name, (tumor, normal) in matrices.items()}
        pl.DataFrame({"gene_id": genes, "native_effect": effects["native"],
                      "recount_effect": effects["recount3"], "informative": mask}).write_parquet(
                          private / f"{cancer}_gene_effects.parquet")
        for i, (universe, selected) in enumerate(masks.items()):
            metric, top = _metric_rows(genes, effects, selected, config, cancer, universe,
                                       config.seed + 100 * len(all_audit) + i)
            all_metrics.append(metric)
            all_top.extend(top)
        if any(int(selected.sum()) >= max(config.minimum_informative_genes, max(config.top_k))
               for selected in masks.values()):
            b_concordance, b_overlap = _bootstrap(matrices, units, genes, masks, config, cancer, private)
            all_boot_c.extend(b_concordance)
            all_boot_o.extend(b_overlap)
        del matrices, effects
    previous = json.loads((Path(v1_root) / "report.json").read_text(encoding="utf-8"))
    old = {(r["cancer_type"], r["top_k"]): r for r in previous["effect_summary"]}
    for row in all_top:
        row["v1_deterministic_jaccard"] = (old[(row["cancer_type"], row["top_k"])]["top_k_jaccard"]
                                             if row["universe"] == "all_shared" else None)
        if (row["universe"] == "all_shared" and
                not np.isclose(row["deterministic_jaccard"], row["v1_deterministic_jaccard"], atol=1e-12)):
            raise ValueError("v2 all-gene deterministic result differs from frozen v1")
        selected = [r["tie_mean_jaccard"] for r in all_boot_o if
                    (r["cancer_type"], r["universe"], r["top_k"]) ==
                    (row["cancer_type"], row["universe"], row["top_k"])]
        row["bootstrap_ci_low"], row["bootstrap_ci_high"] = _interval(selected)
        row["bootstrap_replicates"] = len(selected)
    for row in all_metrics:
        selected = [r for r in all_boot_c if (r["cancer_type"], r["universe"]) ==
                    (row["cancer_type"], row["universe"])]
        for name in ("kendall_tau_b", "direction_agreement"):
            row[f"{name}_bootstrap_ci_low"], row[f"{name}_bootstrap_ci_high"] = _interval(
                [r[name] for r in selected])
        row["bootstrap_replicates"] = len(selected)
    annotations = annotation_audit(manifest, silver)
    metrics_path, top_path = output / "effect_concordance.csv", output / "topk_tie_sensitivity.csv"
    annotation_path, cohort_path = output / "annotation_workflow_audit.json", output / "cohort_audit.json"
    pl.DataFrame(all_metrics).write_csv(metrics_path)
    pl.DataFrame(all_top).write_csv(top_path)
    annotation_path.write_text(json.dumps(annotations, indent=2, allow_nan=False) + "\n")
    cohort_path.write_text(json.dumps(all_audit, indent=2, allow_nan=False) + "\n")
    figure = output / "tie_aware_overlap.svg"
    _write_figure(all_top, figure)
    private_paths = sorted(private.glob("*.parquet"))
    report = {"status": "completed", "study_id": config.study_id,
              "generated_at": datetime.now(UTC).isoformat(), "plan_file_sha256": plan_sha,
              "matched_specimens": manifest.height, "public_derived_mode": True,
              "individual_identifiers_exported": False,
              "interpretation": "Post-v1 exploratory processing sensitivity; ties and annotation differences are not causal evidence.",
              "units": {"native": "TPM", "recount3": "AUC-scaled coverage count (40M target)"},
              "v1_report_resource": resource(Path(v1_root) / "report.json"),
              "outputs": [resource(p) for p in (metrics_path, top_path, annotation_path, cohort_path, figure)],
              "private_resources": [resource(p) for p in private_paths],
              "cohorts": all_audit, "effect_concordance": all_metrics, "topk": all_top,
              "annotation_workflow_audit": annotations}
    report_path.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/matched_processing_v2.yml")
    parser.add_argument("--v1-root", default="outputs/research/matched_processing_v1")
    parser.add_argument("--silver-dir", default="data/silver")
    parser.add_argument("--private-root", default="data/research")
    parser.add_argument("--output-root", default="outputs/research")
    parser.add_argument("--prepare-only", action="store_true")
    args = parser.parse_args()
    result = run_study(args.config, args.v1_root, args.silver_dir,
                       args.private_root, args.output_root, args.prepare_only)
    print(f"Matched processing v2 {result['status']}: {result['matched_specimens']} specimens")
