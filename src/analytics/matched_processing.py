"""Frozen exact-specimen processing comparison on the public recount3 release."""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
import gzip
from importlib.metadata import version
import json
from pathlib import Path
import subprocess

import numpy as np
import polars as pl
import yaml

from src.analytics.controlled_reference_study import lock_plan, rank_biserial, sha256_file
from src.analytics.recount3_crosswalk import RECOUNT3_RELEASE_EVIDENCE
from src.ingestion.recount3_expression import (
    ANNOTATION, COHORTS, OUTPUT_SCHEMA, _harmonize_cohort, _parse_gene_annotation,
)
from src.analytics.matched_processing_metrics import (
    effect_rank_rows, paired_expression, specimen_metrics, summarize_specimens,
    write_effect_figure, write_summary_figure,
)


@dataclass(frozen=True)
class MatchedConfig:
    study_id: str = "matched_processing_v1"
    seed: int = 20261013
    allow_public_derived: bool = False
    minimum_common_genes: int = 1000
    bootstrap_repeats: int = 1000
    top_k: tuple[int, ...] = (25, 50, 100)
    primary_colon_tissue: str = "Colon - Transverse"

    def __post_init__(self) -> None:
        if not self.study_id.isidentifier() or self.seed < 0 or self.minimum_common_genes < 2:
            raise ValueError("Invalid matched-processing study identity, seed or gene threshold")
        if self.bootstrap_repeats < 20 or not self.top_k or min(self.top_k) < 1:
            raise ValueError("Invalid bootstrap count or top-k values")
        if self.primary_colon_tissue not in ("Colon - Transverse", "Colon - Sigmoid"):
            raise ValueError("Primary colon tissue must be a configured GTEx colon tissue")


def load_config(path: str | Path) -> MatchedConfig:
    payload = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Matched-processing configuration must be a mapping")
    unknown = set(payload) - set(MatchedConfig.__dataclass_fields__)
    if unknown:
        raise ValueError(f"Unknown matched-processing settings: {sorted(unknown)}")
    if "top_k" in payload:
        payload["top_k"] = tuple(payload["top_k"])
    return MatchedConfig(**payload)


def _resource(path: Path) -> dict:
    return {"path": str(path), "bytes": path.stat().st_size, "sha256": sha256_file(path)}


def _cohort_paths(bronze: Path, cohort: dict) -> dict[str, Path]:
    source, code = str(cohort["source"]), str(cohort["project"])
    prefix = source.lower()
    root = bronze / prefix / code
    return {
        "metadata": root / f"{prefix}.{prefix}.{code}.MD.gz",
        "qc": root / f"{prefix}.recount_qc.{code}.MD.gz",
        "counts": root / f"{prefix}.gene_sums.{code}.{ANNOTATION}.gz",
    }


def _read_tsv(path: Path, columns: list[str]) -> pl.DataFrame:
    with gzip.open(path, "rb") as stream:
        return pl.read_csv(stream, separator="\t", columns=columns, infer_schema_length=0)


def _native_registries(silver: Path) -> dict[str, dict[str, dict]]:
    tcga = (pl.scan_parquet(silver / "silver_expression_tcga.parquet")
            .select("project_id", "sample_id", "case_id", "sample_type").unique().collect())
    gtex = (pl.scan_parquet(silver / "silver_expression_gtex.parquet")
            .select("gtex_sample_id", "donor_id", "tissue_site").unique().collect())
    registries: dict[str, dict[str, dict]] = {"TCGA": {}, "GTEx": {}}
    for row in tcga.iter_rows(named=True):
        key = row["sample_id"]
        if key in registries["TCGA"]:
            raise ValueError("Native TCGA sample maps to multiple cases/projects")
        registries["TCGA"][key] = row
    for row in gtex.iter_rows(named=True):
        key = row["gtex_sample_id"]
        if key in registries["GTEx"]:
            raise ValueError("Native GTEx sample maps to multiple donors/tissues")
        registries["GTEx"][key] = row
    return registries


def _count_columns(path: Path) -> set[str]:
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        header = [stream.readline() for _ in range(3)][-1]
    if not header.startswith("gene_id\t"):
        raise ValueError(f"Unexpected recount3 count-file header: {path}")
    return set(header.rstrip("\n").split("\t")[1:])


def match_cohort(cohort: dict, paths: dict[str, Path], native: dict[str, dict],
                 allow_public_derived: bool) -> tuple[pl.DataFrame, dict]:
    """Return a private exact-match table and aggregate selection reasons."""
    source, code = str(cohort["source"]), str(cohort["project"])
    if source == "TCGA":
        columns = ["external_id", "gdc_cases.samples.sample_id", "gdc_cases.case_id",
                   "cgc_sample_sample_type", "gdc_access"]
        specimen_key, unit_key = "gdc_cases.samples.sample_id", "gdc_cases.case_id"
    else:
        columns = ["external_id", "SAMPID", "SUBJID", "SMTSD"]
        specimen_key, unit_key = "SAMPID", "SUBJID"
    metadata = _read_tsv(paths["metadata"], columns)
    if metadata["external_id"].n_unique() != metadata.height:
        raise ValueError(f"Duplicate recount3 external ID in {source}/{code}")
    qc = _read_tsv(paths["qc"], ["external_id", "bc_auc.all_reads_all_bases"])
    if qc["external_id"].n_unique() != qc.height:
        raise ValueError(f"Duplicate recount3 QC external ID in {source}/{code}")
    qc_values = {row["external_id"]: row["bc_auc.all_reads_all_bases"] for row in qc.iter_rows(named=True)}
    eligible = []
    invalid_qc = 0
    for row in metadata.iter_rows(named=True):
        tissue = "" if source == "TCGA" else row["SMTSD"]
        if source == "TCGA" and row["cgc_sample_sample_type"] != "Primary Tumor":
            continue
        if source == "GTEx" and tissue not in cohort["tissues"]:
            continue
        try:
            auc = float(qc_values.get(row["external_id"], ""))
        except (TypeError, ValueError):
            invalid_qc += 1
            continue
        if not np.isfinite(auc) or auc <= 0:
            invalid_qc += 1
            continue
        specimen, unit = row[specimen_key], row[unit_key]
        if not specimen or not unit or specimen == "NA" or unit == "NA":
            raise ValueError(f"Missing specimen/case/donor mapping in {source}/{code}")
        eligible.append((row, auc, specimen, unit, tissue))
    specimen_counts = Counter(item[2] for item in eligible)
    ambiguous_ids = {key for key, count in specimen_counts.items() if count > 1}
    matched = []
    for row, auc, specimen, unit, tissue in eligible:
        if specimen in ambiguous_ids:
            continue
        target = native.get(specimen)
        if target is None:
            continue
        if source == "TCGA":
            if row["gdc_access"] != "open" and not allow_public_derived:
                raise PermissionError("Underlying GDC file is controlled; enable public-derived recount3 mode")
            if target["project_id"] != cohort["project_id"] or target["sample_type"] != "Primary Tumor":
                raise ValueError(f"TCGA sample project/type mismatch in {code}")
            if target["case_id"] != unit:
                raise ValueError(f"TCGA case mismatch in {code}")
        elif target["donor_id"] != unit or target["tissue_site"] != tissue:
            raise ValueError(f"GTEx donor/tissue mismatch in {code}")
        matched.append({"source": source, "cohort": code, "project_id": str(cohort["project_id"]),
                        "tissue_site": tissue, "recount_sample_id": row["external_id"],
                        "native_sample_id": specimen, "unit_id": unit, "auc": auc,
                        "sample_type": "Primary Tumor" if source == "TCGA" else "Normal"})
    available = _count_columns(paths["counts"])
    missing = {row["recount_sample_id"] for row in matched} - available
    if missing:
        raise ValueError(f"Matched recount3 sample absent from counts header: {source}/{code}")
    summary = {"source": source, "cohort": code, "eligible_metadata_rows": len(eligible),
               "invalid_qc_rows": invalid_qc, "excluded_duplicate_specimens": len(ambiguous_ids),
               "excluded_duplicate_specimen_files": sum(specimen_counts[key] for key in ambiguous_ids),
               "matched_samples": len(matched)}
    if not matched:
        raise ValueError(f"No exact matched specimens: {source}/{code}")
    return pl.DataFrame(matched).sort("recount_sample_id"), summary


def prepare_study(config_path: str | Path, bronze_dir: str | Path = "data/bronze/recount3",
                  silver_dir: str | Path = "data/silver", output_root: str | Path = "outputs/research",
                  private_root: str | Path = "data/research") -> tuple[MatchedConfig, pl.DataFrame, dict, Path, Path]:
    config = load_config(config_path)
    bronze, silver = Path(bronze_dir), Path(silver_dir)
    root, private = Path(output_root) / config.study_id, Path(private_root) / config.study_id
    resources = [_resource(silver / f"silver_expression_{name}.parquet") for name in ("tcga", "gtex")]
    resources.append(_resource(bronze / f"human.gene_sums.{ANNOTATION}.gtf.gz"))
    registries = _native_registries(silver)
    parts, counts = [], []
    for cohort in COHORTS:
        paths = _cohort_paths(bronze, cohort)
        resources.extend(_resource(path) for path in paths.values())
        part, summary = match_cohort(cohort, paths, registries[cohort["source"]], config.allow_public_derived)
        parts.append(part)
        counts.append(summary)
    manifest = pl.concat(parts).sort("source", "cohort", "recount_sample_id")
    if manifest.select("source", "recount_sample_id").is_duplicated().any():
        raise ValueError("A recount3 sample was selected in multiple cohorts")
    code_files = [Path(__file__), Path(_harmonize_cohort.__code__.co_filename),
                  Path(rank_biserial.__code__.co_filename),
                  Path(specimen_metrics.__code__.co_filename)]
    try:
        revision = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True,
                                  text=True, check=False).stdout.strip() or "unavailable"
    except OSError:
        revision = "unavailable"
    plan = {"protocol_version": "1.0", "config": asdict(config), "input_resources": resources,
            "implementation_resources": [_resource(path) for path in code_files],
            "dependencies": {name: version(name) for name in ("numpy", "polars", "scipy", "PyYAML")},
            "code_revision": revision, "selection_summary": counts,
            "public_derived_release_evidence": list(RECOUNT3_RELEASE_EVIDENCE)}
    plan_hash = lock_plan(root / "study_plan.json", plan)
    private.mkdir(parents=True, exist_ok=True)
    manifest_path = private / "matched_specimens.parquet"
    if manifest_path.exists():
        if not pl.read_parquet(manifest_path).equals(manifest):
            raise RuntimeError("Frozen private match manifest differs; use a new study ID")
    else:
        manifest.write_parquet(manifest_path)
    return config, manifest, {"plan_sha256": plan_hash, "private_manifest_sha256": sha256_file(manifest_path),
                              "selection_summary": counts}, root, private


def extract_matched(config: MatchedConfig, manifest: pl.DataFrame, root: Path, private: Path,
                    bronze_dir: str | Path = "data/bronze/recount3",
                    silver_dir: str | Path = "data/silver") -> tuple[Path, list[dict]]:
    bronze, silver = Path(bronze_dir), Path(silver_dir)
    output = silver / f"silver_expression_recount3_{config.study_id}.parquet"
    annotation = _parse_gene_annotation(bronze / f"human.gene_sums.{ANNOTATION}.gtf.gz")
    normalized = annotation.with_columns(pl.col("raw_gene_id").str.replace(
        r"\.\d+(_PAR_Y)?$", "${1}").alias("gene_id"))
    if normalized["gene_id"].is_duplicated().any():
        raise ValueError("Recount3 annotation collapses distinct genes after normalization")
    part_dir = private / "expression_parts"
    part_dir.mkdir(parents=True, exist_ok=True)
    paths, summaries = [], []
    for cohort in COHORTS:
        source, code = cohort["source"], cohort["project"]
        block = manifest.filter((pl.col("source") == source) & (pl.col("cohort") == code))
        selected = block.select(pl.col("recount_sample_id").alias("external_id"),
                                "sample_type", "tissue_site", "project_id", "auc")
        part = _harmonize_cohort(cohort, _cohort_paths(bronze, cohort)["counts"], selected, annotation)
        if part.height != block.height * annotation.height or part.filter(~pl.col("expression_value").is_finite()).height:
            raise ValueError(f"Incomplete or nonfinite recount3 measurements: {source}/{code}")
        if part.select("sample_id", "gene_id").is_duplicated().any():
            raise ValueError(f"Duplicate recount3 measurement key: {source}/{code}")
        if part["sample_id"].n_unique() != block.height:
            raise ValueError(f"Missing extracted recount3 specimens: {source}/{code}")
        path = part_dir / f"{source}_{code}.parquet"
        if path.exists():
            if not pl.read_parquet(path).equals(part):
                raise RuntimeError("Frozen recount3 cohort part differs; use a new study ID")
        else:
            part.write_parquet(path, compression="zstd")
        paths.append(path)
        summaries.append({"source": source, "cohort": code, "samples": block.height,
                          "measurement_rows": part.height, "sha256": sha256_file(path)})
        del part
    temporary = output.with_suffix(".parquet.tmp")
    pl.concat([pl.scan_parquet(path) for path in paths], how="vertical_relaxed").sink_parquet(
        temporary, compression="zstd")
    if output.exists():
        if sha256_file(output) != sha256_file(temporary):
            raise RuntimeError("Versioned matched-expression output differs; use a new study ID")
        temporary.unlink()
    else:
        temporary.replace(output)
    return output, summaries


def compare_matched(config: MatchedConfig, manifest: pl.DataFrame, expression_path: Path,
                    root: Path, private: Path, silver_dir: str | Path) -> dict:
    silver = Path(silver_dir)
    specimen_rows = []
    for cohort in COHORTS:
        source, code = cohort["source"], cohort["project"]
        block = manifest.filter((pl.col("source") == source) & (pl.col("cohort") == code))
        native_path = silver / f"silver_expression_{source.lower()}.parquet"
        pairs = paired_expression(block, native_path, expression_path, source)
        context = {row["recount_sample_id"]: row for row in block.iter_rows(named=True)}
        for key, frame in pairs.group_by("recount_sample_id"):
            sample = key[0]
            row = context[sample]
            stats = specimen_metrics(frame, frame["native_gene_count"][0],
                                     frame["recount_gene_count"][0], config.minimum_common_genes)
            specimen_rows.append({"source": source, "cohort": code, "tissue_site": row["tissue_site"],
                                  "unit_id": row["unit_id"], "native_sample_id": row["native_sample_id"],
                                  "recount_sample_id": sample, **stats})
        del pairs
    private_metrics = pl.DataFrame(specimen_rows).sort("source", "cohort", "recount_sample_id")
    if private_metrics.height != manifest.height:
        raise ValueError("Missing per-specimen processing metric")
    private_metrics_path = private / "specimen_metrics.parquet"
    private_metrics.write_parquet(private_metrics_path)
    summary = summarize_specimens(private_metrics, config.bootstrap_repeats, config.seed)
    summary_path = root / "specimen_summary.csv"
    summary.write_csv(summary_path)
    effects = []
    for cancer, code, tissue in (("TCGA-BRCA", "BRCA", "Breast - Mammary Tissue"),
                                 ("TCGA-COAD", "COAD", config.primary_colon_tissue),
                                 ("TCGA-LUAD", "LUAD", "Lung")):
        tumor_block = manifest.filter((pl.col("source") == "TCGA") & (pl.col("cohort") == code))
        normal_block = manifest.filter((pl.col("source") == "GTEx") & (pl.col("tissue_site") == tissue))
        tumor = paired_expression(tumor_block, silver / "silver_expression_tcga.parquet", expression_path, "TCGA")
        normal = paired_expression(normal_block, silver / "silver_expression_gtex.parquet", expression_path, "GTEx")
        effects.extend(effect_rank_rows(tumor, normal, cancer, tissue, config.top_k, config.minimum_common_genes))
        del tumor, normal
    effect_frame = pl.DataFrame(effects).sort("cancer_type", "top_k")
    effect_path = root / "effect_rank_summary.csv"
    effect_frame.write_csv(effect_path)
    specimen_figure, effect_figure = root / "specimen_agreement.svg", root / "effect_rank_overlap.svg"
    write_summary_figure(summary, specimen_figure)
    write_effect_figure(effect_frame, effect_figure)
    return {"private_metrics_sha256": sha256_file(private_metrics_path),
            "specimen_summary": summary.to_dicts(), "effect_summary": effect_frame.to_dicts(),
            "public_outputs": [_resource(path) for path in (summary_path, effect_path, specimen_figure, effect_figure)]}


def run_study(config_path: str | Path = "configs/matched_processing_v1.yml",
              bronze_dir: str | Path = "data/bronze/recount3",
              silver_dir: str | Path = "data/silver", output_root: str | Path = "outputs/research",
              private_root: str | Path = "data/research", prepare_only: bool = False) -> dict:
    config, manifest, audit, root, private = prepare_study(
        config_path, bronze_dir, silver_dir, output_root, private_root)
    if prepare_only:
        return {"status": "prepared", "study_id": config.study_id, "matched_specimens": manifest.height, **audit}
    report_path = root / "report.json"
    if report_path.exists():
        existing = json.loads(report_path.read_text())
        if existing.get("plan_sha256") != audit["plan_sha256"]:
            raise RuntimeError("Existing matched-processing report uses a different frozen plan")
        for resource in existing["outputs"]:
            if sha256_file(Path(resource["path"])) != resource["sha256"]:
                raise RuntimeError("Existing matched-processing output has changed")
        return existing
    expression_path, cohort_parts = extract_matched(config, manifest, root, private, bronze_dir, silver_dir)
    comparison = compare_matched(config, manifest, expression_path, root, private, silver_dir)
    report = {"status": "completed", "study_id": config.study_id,
              "generated_at": datetime.now(UTC).isoformat(), **audit,
              "private_manifest_resource": _resource(private / "matched_specimens.parquet"),
              "private_metrics_resource": _resource(private / "specimen_metrics.parquet"),
              "matched_specimens": manifest.height, "cohort_parts": cohort_parts,
              "public_derived_mode": config.allow_public_derived,
              "release_evidence": list(RECOUNT3_RELEASE_EVIDENCE),
              "individual_identifiers_exported": False,
              "claim_boundary": "Exact specimen processing sensitivity only; no independent cohort, biological validation or clinical claim.",
              "units": {"native": "TPM", "recount3": "AUC-scaled coverage count (40M target)"},
              "limitations": ["RNA-seq annotation and quantification workflows differ.",
                              "Specimen-matched results are descriptive and conditional on available samples.",
                              "Effect-rank overlaps are point estimates; cohort bootstrap intervals apply to specimen-level metrics only."],
              "expression_resource": _resource(expression_path), **comparison,
              "outputs": [_resource(expression_path), *comparison["public_outputs"]]}
    report_path.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/matched_processing_v1.yml")
    parser.add_argument("--bronze-dir", default="data/bronze/recount3")
    parser.add_argument("--silver-dir", default="data/silver")
    parser.add_argument("--output-root", default="outputs/research")
    parser.add_argument("--private-root", default="data/research")
    parser.add_argument("--prepare-only", action="store_true")
    args = parser.parse_args()
    result = run_study(args.config, args.bronze_dir, args.silver_dir,
                       args.output_root, args.private_root, args.prepare_only)
    print(f"Matched processing {result['status']}: {result['matched_specimens']} specimens")
