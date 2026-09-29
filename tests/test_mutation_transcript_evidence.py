import polars as pl

from src.analytics.mutation_transcript_evidence import build_mutation_transcript_evidence


def test_transcript_evidence_counts_unique_samples_and_nonblank_annotations() -> None:
    mutations = pl.DataFrame(
        {
            "project_id": ["TCGA-LUAD"] * 3,
            "sample_id": ["S1", "S1", "S2"],
            "gene_symbol": ["TP53"] * 3,
            "transcript_id": ["ENST1"] * 3,
            "vep_consequence": ["missense_variant"] * 3,
            "vep_impact": ["moderate", "MODERATE", "MODERATE"],
            "variant_classification": ["Missense_Mutation"] * 3,
            "hgvsc": ["c.1A>G", "", None],
            "hgvsp": ["p.K1R", "  ", "p.K1R"],
            "all_effects": ["effect", "", None],
        }
    )
    profile = pl.DataFrame(
        {"project_id": ["TCGA-LUAD"] * 3, "sample_id": ["S1", "S2", "S3"]}
    )

    row = build_mutation_transcript_evidence(mutations, profile).row(0, named=True)

    assert row["vep_impact"] == "MODERATE"
    assert row["event_count"] == 3
    assert row["distinct_sample_count"] == 2
    assert row["profiled_sample_count"] == 3
    assert row["sample_fraction"] == 2 / 3
    assert row["hgvsc_annotation_event_count"] == 1
    assert row["hgvsp_annotation_event_count"] == 2
    assert row["all_effects_annotation_event_count"] == 1
    assert row["impact_interpretation"] == "source_vep_category_not_driver_classification"


def test_transcript_evidence_skips_blank_gene_symbols() -> None:
    mutations = pl.DataFrame(
        {
            "project_id": ["TCGA-LUAD", "TCGA-LUAD"],
            "sample_id": ["S1", "S2"],
            "gene_symbol": ["TP53", "  "],
        }
    )

    result = build_mutation_transcript_evidence(mutations, pl.DataFrame())

    assert result.height == 1
    assert result["gene_symbol"].to_list() == ["TP53"]
