from __future__ import annotations


def mutation_frequency_by_gene_stub(gene_symbol: str) -> dict[str, object]:
    return {
        "gene_symbol": gene_symbol.upper(),
        "rows": [
            {"cancer_type": "TCGA-LUAD", "mutation_frequency": 0.25},
            {"cancer_type": "TCGA-COAD", "mutation_frequency": 0.18},
        ],
    }
