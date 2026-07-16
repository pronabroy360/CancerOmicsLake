from pathlib import Path

import polars as pl

from src.analytics.build_gold_tables import build_gold_cohort_summary
from src.quality.checks import run_silver_quality_checks


def test_gold_mutation_frequency_uses_profile_denominator_and_protein_altering_events(tmp_path: Path) -> None:
    silver_dir = tmp_path / "silver"
    gold_dir = tmp_path / "gold"
    silver_dir.mkdir()

    pl.DataFrame(
        {
            "project_id": ["TCGA-LUAD", "TCGA-LUAD", "TCGA-LUAD"],
            "case_id": ["case-1", "case-2", "case-2"],
            "sample_id": ["sample-1", "sample-2", "sample-2"],
            "gene_id": ["ENSG1", "ENSG1", "ENSG2"],
            "gene_symbol": ["TP53", "TP53", "EGFR"],
            "variant_classification": ["Missense_Mutation", "Silent", "Silent"],
            "consequence_group": ["protein_altering", "synonymous", "synonymous"],
            "is_protein_altering": [True, False, False],
            "variant_type": ["SNP", "SNP", "SNP"],
            "chromosome": ["17", "17", "7"],
            "start_position": [1, 2, 3],
            "end_position": [1, 2, 3],
            "reference_allele": ["C", "A", "G"],
            "tumor_seq_allele": ["T", "G", "A"],
            "data_origin": ["file-1", "file-2", "file-2"],
            "ingested_at": ["now", "now", "now"],
        }
    ).write_parquet(silver_dir / "silver_mutations.parquet")
    pl.DataFrame(
        {
            "project_id": ["TCGA-LUAD", "TCGA-LUAD", "TCGA-LUAD", "TCGA-BRCA"],
            "case_id": ["case-1", "case-2", "case-3", "case-4"],
            "sample_id": ["sample-1", "sample-2", "sample-3", "sample-4"],
            "file_id": ["file-1", "file-2", "file-3", "file-4"],
            "file_name": ["1.maf", "2.maf", "3.maf", "4.maf"],
            "file_size": [10, 10, 10, 10],
            "md5sum": ["a", "b", "c", "d"],
            "data_origin": ["1.maf", "2.maf", "3.maf", "4.maf"],
            "profile_status": ["downloaded", "downloaded", "downloaded", "downloaded"],
            "ingested_at": ["now", "now", "now", "now"],
        }
    ).write_parquet(silver_dir / "silver_mutation_profile.parquet")

    build_gold_cohort_summary(silver_dir=silver_dir, gold_dir=gold_dir)

    by_gene = pl.read_parquet(gold_dir / "gold_mutation_frequency_by_gene.parquet")
    assert by_gene.get_column("gene_symbol").to_list() == ["TP53"]
    row = by_gene.row(0, named=True)
    assert row["mutated_sample_count"] == 1
    assert row["total_profiled_sample_count"] == 3
    assert row["mutation_frequency"] == 1 / 3
    assert row["protein_altering_event_count"] == 1
    assert row["all_somatic_event_count"] == 2
    assert row["synonymous_event_count"] == 1
    assert row["mutation_scope"] == "protein_altering_only"

    by_cancer = pl.read_parquet(gold_dir / "gold_mutation_frequency_by_cancer.parquet")
    cancer = by_cancer.filter(pl.col("cancer_type") == "TCGA-LUAD").row(0, named=True)
    assert cancer["mutation_event_count"] == 1
    assert cancer["all_somatic_event_count"] == 3
    assert cancer["synonymous_event_count"] == 2
    assert cancer["mutation_frequency"] == 1 / 3
    zero_event_cancer = by_cancer.filter(pl.col("cancer_type") == "TCGA-BRCA").row(0, named=True)
    assert zero_event_cancer["total_profiled_sample_count"] == 1
    assert zero_event_cancer["mutation_event_count"] == 0
    assert zero_event_cancer["mutation_frequency"] == 0.0

    quality = {result.check_name: result for result in run_silver_quality_checks(silver_dir, gold_dir=gold_dir)}
    assert quality["silver_mutation_consequence_semantics_valid"].status == "passed"
    assert quality["silver_mutation_profile_rows_valid"].status == "passed"
    assert quality["gold_mutation_frequency_semantics_valid"].status == "passed"
