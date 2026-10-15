from __future__ import annotations

import re


def strip_ensembl_version(gene_id: str) -> str:
    # PAR_Y denotes a distinct pseudoautosomal locus, not an annotation version.
    return re.sub(r"\.\d+(?=_PAR_Y$|$)", "", gene_id)


def normalize_gene_id(gene_id: str) -> dict[str, str]:
    normalized = strip_ensembl_version(gene_id)
    return {"gene_id_original": gene_id, "gene_id_normalized": normalized}
