import polars as pl

from src.quality.checks import check_unique_measurement_keys


def test_measurement_uniqueness_counts_extra_rows_not_units_or_values():
    frame = pl.DataFrame({"sample_id": ["s", "s", "s"], "gene_id": ["ENSG1", "ENSG1", "ENSG1"],
                          "expression_unit": ["TPM", "TPM", "COUNT"], "expression_value": [1., 2., 1.]})
    result = check_unique_measurement_keys(frame, ["sample_id", "gene_id", "expression_unit"], "fixture")
    assert result.status == "failed" and result.failed_rows == 1
    assert check_unique_measurement_keys(frame[[0, 2]], ["sample_id", "gene_id", "expression_unit"], "fixture").status == "passed"


def test_measurement_uniqueness_fails_missing_schema_even_when_empty():
    result = check_unique_measurement_keys(pl.DataFrame(), ["gene_id"], "fixture")
    assert result.status == "failed" and result.metric_value == 1
