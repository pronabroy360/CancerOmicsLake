from __future__ import annotations


def tumor_vs_normal_stub(gene_symbol: str) -> dict[str, object]:
    return {
        "gene_symbol": gene_symbol.upper(),
        "warning": "Exploratory cross-dataset comparison; batch effects may be present.",
        "rows": [
            {
                "cancer_type": "TCGA-BRCA",
                "median_tcga_tumor_expression": 2.3,
                "median_gtex_normal_expression": 1.9,
                "log2_fold_change": 0.4,
            }
        ],
    }
