"""Audit exact native/recount3 specimen matches without exporting identifiers."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path

import polars as pl


COHORTS = {
    "TCGA": {"BRCA": "TCGA-BRCA", "COAD": "TCGA-COAD", "LUAD": "TCGA-LUAD"},
    "GTEx": {"BREAST": "Breast - Mammary Tissue", "LUNG": "Lung",
             "COLON": ("Colon - Transverse", "Colon - Sigmoid")},
}
RECOUNT3_RELEASE_EVIDENCE = (
    "https://rna.recount.bio/docs/index.html",
    "https://github.com/awslabs/open-data-registry/blob/main/datasets/recount.yaml",
)


def _hash(path: Path) -> dict:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return {"path": str(path), "bytes": path.stat().st_size, "sha256": digest.hexdigest()}


def _metadata(path: Path, source: str) -> pl.DataFrame:
    columns = (["external_id", "gdc_cases.samples.sample_id", "gdc_cases.case_id", "gdc_access"]
               if source == "TCGA" else ["external_id", "SAMPID", "SUBJID"])
    with gzip.open(path, "rb") as stream:
        frame = pl.read_csv(stream, separator="\t", columns=columns, infer_schema_length=0)
    if frame.select(pl.any_horizontal(pl.all().is_null()).sum()).item() > 0:
        raise ValueError(f"Null crosswalk identifier or access field: {path}")
    if frame.select(pl.col("external_id").n_unique()).item() != frame.height:
        raise ValueError(f"Ambiguous recount3 external IDs: {path}")
    return frame


def _count_matches(selected: pl.DataFrame, native: pl.DataFrame, metadata: pl.DataFrame,
                   source: str, cohort: str, allow_public_derived: bool = False) -> dict:
    specimen = "gdc_cases.samples.sample_id" if source == "TCGA" else "SAMPID"
    native_key = "sample_id" if source == "TCGA" else "gtex_sample_id"
    selected = selected.join(metadata, left_on="sample_id", right_on="external_id", how="left")
    if selected[specimen].null_count():
        raise ValueError(f"Selected recount3 sample has no metadata: {source}/{cohort}")
    if source == "TCGA" and selected.filter(pl.col("gdc_access") != "open").height and not allow_public_derived:
        raise PermissionError(f"Selected TCGA recount3 upstream files are not GDC-open: {cohort}; "
                              "use explicit public-derived mode only for the published recount3 release")
    duplicated = selected.group_by(specimen).len().filter(pl.col("len") > 1)
    eligible = selected.filter(~pl.col(specimen).is_in(duplicated[specimen].to_list()))
    matched = eligible.join(native, left_on=specimen, right_on=native_key, how="inner")
    if matched.height != matched.select("sample_id").n_unique():
        raise ValueError(f"Ambiguous native specimen match: {source}/{cohort}")
    if source == "TCGA" and matched.filter(pl.col("gdc_cases.case_id") != pl.col("case_id")).height:
        raise ValueError(f"Matched TCGA sample belongs to different GDC case: {cohort}")
    if source == "GTEx" and matched.filter(pl.col("SUBJID") != pl.col("donor_id")).height:
        raise ValueError(f"Matched GTEx sample belongs to different donor: {cohort}")
    return {"source": source, "cohort": cohort, "recount3_samples": selected.height,
            "exact_specimen_matches": matched.height,
            "excluded_duplicate_specimen_files": selected.height - eligible.height,
            "excluded_duplicate_specimens": duplicated.height,
            "unmatched_recount3_samples": eligible.height - matched.height,
            "match_fraction_of_all_selected": round(matched.height / selected.height, 6) if selected.height else 0.0}


def build_crosswalk_audit(bronze_dir: str | Path = "data/bronze/recount3",
                          silver_dir: str | Path = "data/silver",
                          output_path: str | Path = "outputs/research/recount3_specimen_crosswalk_audit.json",
                          allow_public_derived: bool = False) -> dict:
    bronze, silver = Path(bronze_dir), Path(silver_dir)
    files = {source: silver / f"silver_expression_{source.lower()}.parquet" for source in ("TCGA", "GTEx")}
    recount_path = silver / "silver_expression_recount3.parquet"
    selected_all = pl.scan_parquet(recount_path).select("source", "project_id", "tissue_site", "sample_id").unique().collect()
    native = {
        "TCGA": pl.scan_parquet(files["TCGA"]).select("project_id", "sample_id", "case_id").unique().collect(),
        "GTEx": pl.scan_parquet(files["GTEx"]).select("tissue_site", "gtex_sample_id", "donor_id").unique().collect(),
    }
    resources = [_hash(p) for p in (*files.values(), recount_path)]
    cohorts = []
    for source, mapping in COHORTS.items():
        folder = "tcga" if source == "TCGA" else "gtex"
        for code, label in mapping.items():
            prefix = "tcga.tcga" if source == "TCGA" else "gtex.gtex"
            path = bronze / folder / code / f"{prefix}.{code}.MD.gz"
            resources.append(_hash(path))
            md = _metadata(path, source)
            if source == "TCGA":
                selected = selected_all.filter((pl.col("source") == source) & (pl.col("project_id") == label))
                natives = native[source].filter(pl.col("project_id") == label)
            else:
                tissues = (label,) if isinstance(label, str) else label
                selected = selected_all.filter((pl.col("source") == source) & pl.col("tissue_site").is_in(tissues))
                natives = native[source].filter(pl.col("tissue_site").is_in(tissues)).drop("tissue_site")
            cohorts.append(_count_matches(selected, natives, md, source, code, allow_public_derived))
    result = {"status": "completed", "join_rule": "exact GDC sample UUID or exact GTEx SAMPID; case/donor checked",
              "claim_boundary": "Specimen identity only. Expression scales, annotation versions and processing equivalence are not established.",
              "cohorts": cohorts, "input_resources": resources, "individual_identifiers_exported": False,
              "public_derived_mode": allow_public_derived,
              "upstream_gdc_access_not_derived_release_access": True,
              "recount3_release_evidence": list(RECOUNT3_RELEASE_EVIDENCE) if allow_public_derived else []}
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--bronze-dir", default="data/bronze/recount3")
    parser.add_argument("--silver-dir", default="data/silver")
    parser.add_argument("--output", default="outputs/research/recount3_specimen_crosswalk_audit.json")
    parser.add_argument("--allow-public-derived", action="store_true",
                        help="Analyze recount3's publicly released processed expression; never fetch controlled GDC files")
    args = parser.parse_args()
    build_crosswalk_audit(args.bronze_dir, args.silver_dir, args.output, args.allow_public_derived)
