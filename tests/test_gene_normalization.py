from src.processing.normalize_gene_ids import normalize_gene_id, strip_ensembl_version


def test_strip_ensembl_version() -> None:
    assert strip_ensembl_version("ENSG00000141510.17") == "ENSG00000141510"


def test_normalize_gene_id() -> None:
    mapped = normalize_gene_id("ENSG00000141510.17")
    assert mapped["gene_id_original"] == "ENSG00000141510.17"
    assert mapped["gene_id_normalized"] == "ENSG00000141510"
