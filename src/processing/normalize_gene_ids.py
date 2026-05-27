from __future__ import annotations


def strip_ensembl_version(gene_id: str) -> str:
    return gene_id.split(".", maxsplit=1)[0]


def normalize_gene_id(gene_id: str) -> dict[str, str]:
    normalized = strip_ensembl_version(gene_id)
    return {"gene_id_original": gene_id, "gene_id_normalized": normalized}
