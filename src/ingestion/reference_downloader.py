from __future__ import annotations

from dataclasses import dataclass


@dataclass
class GeneReference:
    gene_id: str
    gene_symbol: str
    gene_name: str
    chromosome: str
    gene_type: str
    source: str
    source_version: str


def reference_genes_stub() -> list[GeneReference]:
    return [
        GeneReference(
            gene_id="ENSG00000141510",
            gene_symbol="TP53",
            gene_name="tumor protein p53",
            chromosome="17",
            gene_type="protein_coding",
            source="stub",
            source_version="0.1",
        )
    ]
