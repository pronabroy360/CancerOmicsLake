from pathlib import Path

import polars as pl

from src.analytics.mutation_frequency import mutation_frequency_by_cancer, mutation_frequency_by_gene


def test_mutation_frequency_by_gene_from_gold(tmp_path: Path) -> None:
    gold_file = tmp_path / "gold_mutation_frequency_by_gene.parquet"
    pl.DataFrame(
        {
            "gene_symbol": ["TP53", "TP53", "EGFR"],
            "cancer_type": ["TCGA-LUAD", "TCGA-BRCA", "TCGA-LUAD"],
            "mutated_sample_count": [20, 10, 8],
            "total_profiled_sample_count": [100, 80, 100],
            "mutation_frequency": [0.2, 0.125, 0.08],
            "top_variant_classification": ["Missense_Mutation", "Missense_Mutation", "Missense_Mutation"],
        }
    ).write_parquet(gold_file)

    payload = mutation_frequency_by_gene("tp53", gold_file)
    assert payload["gene_symbol"] == "TP53"
    assert len(payload["rows"]) == 2


def test_mutation_frequency_by_cancer_from_gold(tmp_path: Path) -> None:
    gold_file = tmp_path / "gold_mutation_frequency_by_gene.parquet"
    pl.DataFrame(
        {
            "gene_symbol": ["TP53", "EGFR", "KRAS"],
            "cancer_type": ["TCGA-LUAD", "TCGA-LUAD", "TCGA-BRCA"],
            "mutated_sample_count": [20, 8, 5],
            "total_profiled_sample_count": [100, 100, 80],
            "mutation_frequency": [0.2, 0.08, 0.0625],
            "top_variant_classification": ["Missense_Mutation", "Missense_Mutation", "Missense_Mutation"],
        }
    ).write_parquet(gold_file)

    payload = mutation_frequency_by_cancer("TCGA-LUAD", gold_file)
    assert payload["project_id"] == "TCGA-LUAD"
    assert len(payload["top_genes"]) == 2
