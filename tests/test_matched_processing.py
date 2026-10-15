from dataclasses import asdict
import gzip
import json
from pathlib import Path

import numpy as np
import polars as pl
import pytest
import yaml

from src.analytics.matched_processing import MatchedConfig, match_cohort, run_study
from src.analytics.matched_processing_metrics import paired_expression, specimen_metrics
from src.ingestion.recount3_expression import COHORTS


def _gzip(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt", encoding="utf-8") as handle:
        handle.write(value)


def test_matched_specimen_metrics_use_ranks_not_expression_units():
    frame = pl.DataFrame({"gene_id": ["A", "B", "C", "D"], "native_value": [1., 2., 3., 4.],
                          "recount_value": [10., 100., 1000., 10000.]})
    result = specimen_metrics(frame, 4, 4, 2)
    assert result["spearman_all_common"] == pytest.approx(1)
    assert result["spearman_jointly_detected"] == pytest.approx(1)
    assert result["top100_jaccard"] == 1
    with pytest.raises(ValueError, match="Duplicate gene"):
        specimen_metrics(pl.concat([frame, frame.head(1)]), 5, 5, 2)
    with pytest.raises(ValueError, match="Negative"):
        specimen_metrics(frame.with_columns(pl.lit(-1.).alias("native_value")), 4, 4, 2)


def test_exact_matching_rejects_access_case_and_missing_count_columns(tmp_path: Path):
    paths = {name: tmp_path / f"{name}.gz" for name in ("metadata", "qc", "counts")}
    metadata = ("external_id\tgdc_cases.samples.sample_id\tgdc_cases.case_id\t"
                "cgc_sample_sample_type\tgdc_access\n"
                "recount-a\tGDC-A\tCASE-A\tPrimary Tumor\tcontrolled\n")
    _gzip(paths["metadata"], metadata)
    _gzip(paths["qc"], "external_id\tbc_auc.all_reads_all_bases\nrecount-a\t40000000\n")
    _gzip(paths["counts"], "##annotation=G026\n##date=x\ngene_id\trecount-a\nENSG1.2\t1\n")
    native = {"GDC-A": {"project_id": "TCGA-BRCA", "sample_type": "Primary Tumor", "case_id": "CASE-A"}}
    with pytest.raises(PermissionError, match="controlled"):
        match_cohort(COHORTS[0], paths, native, False)
    matches, summary = match_cohort(COHORTS[0], paths, native, True)
    assert matches.height == summary["matched_samples"] == 1
    with pytest.raises(ValueError, match="case mismatch"):
        match_cohort(COHORTS[0], paths, {"GDC-A": {**native["GDC-A"], "case_id": "OTHER"}}, True)
    _gzip(paths["counts"], "##annotation=G026\n##date=x\ngene_id\tother\nENSG1.2\t1\n")
    with pytest.raises(ValueError, match="absent from counts header"):
        match_cohort(COHORTS[0], paths, native, True)


def test_ambiguous_specimens_are_excluded_and_gtex_donor_is_verified(tmp_path: Path):
    paths = {name: tmp_path / f"{name}.gz" for name in ("metadata", "qc", "counts")}
    cohort = next(row for row in COHORTS if row["project"] == "BREAST")
    _gzip(paths["metadata"], "external_id\tSAMPID\tSUBJID\tSMTSD\n"
          "r1\ts1\td1\tBreast - Mammary Tissue\n"
          "r2\ts1\td1\tBreast - Mammary Tissue\n"
          "r3\ts2\td2\tBreast - Mammary Tissue\n")
    _gzip(paths["qc"], "external_id\tbc_auc.all_reads_all_bases\n"
          "r1\t40000000\nr2\t40000000\nr3\t40000000\n")
    _gzip(paths["counts"], "##annotation=G026\n##date=x\ngene_id\tr1\tr2\tr3\nENSG1.2\t1\t1\t1\n")
    native = {"s1": {"donor_id": "d1", "tissue_site": "Breast - Mammary Tissue"},
              "s2": {"donor_id": "d2", "tissue_site": "Breast - Mammary Tissue"}}
    matches, audit = match_cohort(cohort, paths, native, True)
    assert matches["recount_sample_id"].to_list() == ["r3"]
    assert audit["excluded_duplicate_specimens"] == 1
    assert audit["excluded_duplicate_specimen_files"] == 2
    with pytest.raises(ValueError, match="donor/tissue mismatch"):
        match_cohort(cohort, paths, {**native, "s2": {**native["s2"], "donor_id": "wrong"}}, True)


def test_duplicate_native_measurement_is_rejected(tmp_path: Path):
    native_path, recount_path = tmp_path / "native.parquet", tmp_path / "recount.parquet"
    pl.DataFrame({"sample_id": ["n1", "n1"], "gene_id": ["ENSG1", "ENSG1"],
                  "expression_value": [1., 2.]}).write_parquet(native_path)
    pl.DataFrame({"source": ["TCGA"], "sample_id": ["r1"], "gene_id": ["ENSG1"],
                  "expression_value": [10.]}).write_parquet(recount_path)
    manifest = pl.DataFrame({"native_sample_id": ["n1"], "recount_sample_id": ["r1"]})
    with pytest.raises(ValueError, match="Duplicate native"):
        paired_expression(manifest, native_path, recount_path, "TCGA")


def _fixture(tmp_path: Path) -> tuple[Path, Path, Path, Path, Path]:
    bronze, silver, output, private = (tmp_path / name for name in ("bronze", "silver", "output", "private"))
    silver.mkdir()
    _gzip(bronze / "human.gene_sums.G026.gtf.gz",
          'chr1\tHAVANA\tgene\t1\t10\t.\t+\t.\tgene_id "ENSG1.2"; gene_name "A";\n'
          'chr1\tHAVANA\tgene\t1\t10\t.\t+\t.\tgene_id "ENSG2.1"; gene_name "B";\n'
          'chrY\tHAVANA\tgene\t1\t10\t.\t+\t.\tgene_id "ENSG2.1_PAR_Y"; gene_name "C";\n')
    native_tcga, native_gtex = [], []
    for cohort in COHORTS:
        source, code = cohort["source"], cohort["project"]
        root = bronze / source.lower() / code
        rows, qc, count_rows = [], [], []
        labels = [""] if source == "TCGA" else list(cohort["tissues"])
        for tissue_index, tissue in enumerate(labels):
            for i in range(2):
                suffix = f"{code}-{tissue_index}-{i}"
                external, specimen, unit = f"recount-{suffix}", f"native-{suffix}", f"unit-{suffix}"
                values = [10. + i, 3. + i, 1. + i] if source == "TCGA" else [1. + i, 2. + i, 3. + i]
                if source == "TCGA":
                    rows.append(f"{external}\t{specimen}\t{unit}\tPrimary Tumor\tcontrolled")
                else:
                    rows.append(f"{external}\t{specimen}\t{unit}\t{tissue}")
                qc.append(f"{external}\t40000000")
                count_rows.append((external, values))
                for gene, value in zip(("ENSG1", "ENSG2", "ENSG2_PAR_Y"), values, strict=True):
                    if source == "TCGA":
                        native_tcga.append({"project_id": cohort["project_id"], "sample_id": specimen,
                                            "case_id": unit, "sample_type": "Primary Tumor",
                                            "gene_id": gene, "expression_value": value})
                    else:
                        native_gtex.append({"gtex_sample_id": specimen, "donor_id": unit,
                                            "tissue_site": tissue, "gene_id": gene,
                                            "expression_value": value})
        header = ("external_id\tgdc_cases.samples.sample_id\tgdc_cases.case_id\t"
                  "cgc_sample_sample_type\tgdc_access" if source == "TCGA" else
                  "external_id\tSAMPID\tSUBJID\tSMTSD")
        _gzip(root / f"{source.lower()}.{source.lower()}.{code}.MD.gz", header + "\n" + "\n".join(rows) + "\n")
        _gzip(root / f"{source.lower()}.recount_qc.{code}.MD.gz",
              "external_id\tbc_auc.all_reads_all_bases\n" + "\n".join(qc) + "\n")
        count_text = "##annotation=G026\n##date=x\ngene_id\t" + "\t".join(row[0] for row in count_rows) + "\n"
        for gene_index, gene in enumerate(("ENSG1.2", "ENSG2.1", "ENSG2.1_PAR_Y")):
            count_text += gene + "\t" + "\t".join(str(row[1][gene_index] * 10) for row in count_rows) + "\n"
        _gzip(root / f"{source.lower()}.gene_sums.{code}.G026.gz", count_text)
    pl.DataFrame(native_tcga).write_parquet(silver / "silver_expression_tcga.parquet")
    pl.DataFrame(native_gtex).write_parquet(silver / "silver_expression_gtex.parquet")
    cfg = tmp_path / "config.yml"
    settings = asdict(MatchedConfig(study_id="fixture_matched", allow_public_derived=True,
                                    minimum_common_genes=2, bootstrap_repeats=20, top_k=(1, 2)))
    settings["top_k"] = list(settings["top_k"])
    cfg.write_text(yaml.safe_dump(settings))
    return cfg, bronze, silver, output, private


def test_end_to_end_study_keeps_ids_private_and_freezes_snapshot(tmp_path: Path):
    config, bronze, silver, output, private = _fixture(tmp_path)
    report = run_study(config, bronze, silver, output, private)
    assert report["status"] == "completed" and report["matched_specimens"] == 14
    assert set(pl.read_parquet_schema(silver / "silver_expression_recount3_fixture_matched.parquet")) == {
        "source", "project_id", "sample_id", "sample_type", "tissue_site", "gene_id",
        "gene_symbol", "expression_value", "expression_unit", "external_annotation"}
    assert pl.scan_parquet(silver / "silver_expression_recount3_fixture_matched.parquet").select(
        "source", "sample_id", "gene_id").unique().select(pl.len()).collect().item() == 42
    public = (output / "fixture_matched" / "report.json").read_text()
    assert "native-BRCA" not in public and "recount-BRCA" not in public
    assert len(report["effect_summary"]) == 6
    assert run_study(config, bronze, silver, output, private)["outputs"] == report["outputs"]
    payload = yaml.safe_load(config.read_text())
    payload["seed"] += 1
    config.write_text(yaml.safe_dump(payload))
    with pytest.raises(RuntimeError, match="Frozen study plan differs"):
        run_study(config, bronze, silver, output, private)
