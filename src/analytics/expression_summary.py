from __future__ import annotations


def expression_by_gene_stub(gene_symbol: str) -> dict[str, object]:
    return {
        "gene_symbol": gene_symbol.upper(),
        "rows": [
            {"project_id": "TCGA-BRCA", "median_expression": 2.31},
            {"project_id": "TCGA-LUAD", "median_expression": 2.02},
            {"project_id": "TCGA-COAD", "median_expression": 1.89},
        ],
    }
