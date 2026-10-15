import polars as pl
import pytest

from src.analytics.recount3_crosswalk import _count_matches


def test_tcga_crosswalk_rejects_selected_controlled_access():
    selected = pl.DataFrame({"sample_id": ["recount-a"]})
    native = pl.DataFrame({"sample_id": ["gdc-sample-a"], "case_id": ["case-a"]})
    metadata = pl.DataFrame({"external_id": ["recount-a"],
                             "gdc_cases.samples.sample_id": ["gdc-sample-a"],
                             "gdc_cases.case_id": ["case-a"], "gdc_access": ["controlled"]})
    with pytest.raises(PermissionError, match="not GDC-open"):
        _count_matches(selected, native, metadata, "TCGA", "BRCA")
    assert _count_matches(selected, native, metadata, "TCGA", "BRCA", True)["exact_specimen_matches"] == 1


def test_tcga_crosswalk_requires_exact_sample_and_case_match():
    selected = pl.DataFrame({"sample_id": ["recount-a", "recount-b"]})
    native = pl.DataFrame({"sample_id": ["gdc-sample-a"], "case_id": ["case-a"]})
    metadata = pl.DataFrame({"external_id": ["recount-a", "recount-b"],
                             "gdc_cases.samples.sample_id": ["gdc-sample-a", "gdc-sample-b"],
                             "gdc_cases.case_id": ["case-a", "case-b"],
                             "gdc_access": ["open", "open"]})
    result = _count_matches(selected, native, metadata, "TCGA", "BRCA")
    assert result["exact_specimen_matches"] == 1
    assert result["unmatched_recount3_samples"] == 1
    wrong_case = native.with_columns(pl.lit("case-other").alias("case_id"))
    with pytest.raises(ValueError, match="different GDC case"):
        _count_matches(selected, wrong_case, metadata, "TCGA", "BRCA")


def test_gtex_crosswalk_checks_donor_and_excludes_ambiguous_specimen():
    selected = pl.DataFrame({"sample_id": ["recount-a"]})
    native = pl.DataFrame({"gtex_sample_id": ["gtex-a"], "donor_id": ["donor-a"]})
    metadata = pl.DataFrame({"external_id": ["recount-a"], "SAMPID": ["gtex-a"],
                             "SUBJID": ["donor-a"]})
    assert _count_matches(selected, native, metadata, "GTEx", "BREAST")["exact_specimen_matches"] == 1
    wrong_donor = native.with_columns(pl.lit("donor-other").alias("donor_id"))
    with pytest.raises(ValueError, match="different donor"):
        _count_matches(selected, wrong_donor, metadata, "GTEx", "BREAST")
    repeated = pl.DataFrame({"sample_id": ["recount-a", "recount-b"]})
    repeated_md = pl.concat([metadata, metadata.with_columns(pl.lit("recount-b").alias("external_id"))])
    result = _count_matches(repeated, native, repeated_md, "GTEx", "BREAST")
    assert result["excluded_duplicate_specimens"] == 1
    assert result["excluded_duplicate_specimen_files"] == 2
    assert result["exact_specimen_matches"] == 0
