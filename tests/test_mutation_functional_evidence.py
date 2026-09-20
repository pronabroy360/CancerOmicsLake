import polars as pl

from src.analytics.mutation_functional_evidence import build_mutation_functional_evidence


def test_functional_evidence_counts_classes_and_recurrent_loci() -> None:
    mutations = pl.DataFrame(
        {
            "project_id": ["TCGA-LUAD"] * 6,
            "sample_id": ["S1", "S2", "S3", "S4", "S1", "S5"],
            "gene_symbol": ["TP53", "TP53", "TP53", "TP53", "EGFR", "EGFR"],
            "variant_classification": [
                "Missense_Mutation",
                "Missense_Mutation",
                "Nonsense_Mutation",
                "In_Frame_Del",
                "Missense_Mutation",
                "Silent",
            ],
            "is_protein_altering": [True, True, True, True, True, False],
            "chromosome": ["17", "17", "17", "17", "7", "7"],
            "start_position": [100, 100, 200, 300, 400, 500],
            "reference_allele": ["C", "C", "G", "AT", "A", "T"],
            "tumor_seq_allele": ["T", "T", "A", "A", "G", "C"],
        }
    )
    profile = pl.DataFrame(
        {"project_id": ["TCGA-LUAD"] * 6, "sample_id": ["S1", "S2", "S3", "S4", "S5", "S6"]}
    )

    result = build_mutation_functional_evidence(mutations, profile)

    tp53 = result.filter(pl.col("gene_symbol") == "TP53").row(0, named=True)
    assert tp53["total_profiled_sample_count"] == 6
    assert tp53["protein_altering_mutated_sample_count"] == 4
    assert tp53["putative_loss_of_function_sample_count"] == 1
    assert tp53["missense_sample_count"] == 2
    assert tp53["inframe_sample_count"] == 1
    assert tp53["recurrent_locus_count"] == 1
    assert tp53["max_locus_sample_count"] == 2
    assert tp53["samples_with_recurrent_locus_count"] == 2
    assert tp53["recurrent_locus_sample_fraction"] == 2 / 6
    assert tp53["driver_classification"] == "not_assessed"

    egfr = result.filter(pl.col("gene_symbol") == "EGFR").row(0, named=True)
    assert egfr["protein_altering_mutated_sample_count"] == 1
    assert egfr["recurrent_locus_count"] == 0


def test_functional_evidence_rejects_single_sample_recurrence_threshold() -> None:
    try:
        build_mutation_functional_evidence(pl.DataFrame(), pl.DataFrame(), recurrence_threshold_samples=1)
    except ValueError as exc:
        assert "at least 2" in str(exc)
    else:
        raise AssertionError("Expected ValueError")
