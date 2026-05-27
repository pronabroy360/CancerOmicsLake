from src.quality.checks import check_gene_mapping_rate, check_non_negative_expression


def test_expression_non_negative_pass() -> None:
    rows = [{"expression_value": "0.0"}, {"expression_value": "1.2"}]
    result = check_non_negative_expression(rows)
    assert result.status == "passed"


def test_gene_mapping_rate_warning() -> None:
    rows = [{"gene_id_normalized": "ENSG1"}, {"gene_id_normalized": ""}]
    result = check_gene_mapping_rate(rows, threshold=0.8)
    assert result.status == "warning"
