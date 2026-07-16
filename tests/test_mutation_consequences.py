from src.processing.mutation_consequences import classify_variant_consequence


def test_classify_variant_consequence_is_conservative() -> None:
    assert classify_variant_consequence("Missense_Mutation") == ("protein_altering", True)
    assert classify_variant_consequence("Frame_Shift_Del") == ("protein_altering", True)
    assert classify_variant_consequence("Silent") == ("synonymous", False)
    assert classify_variant_consequence("3'UTR") == ("non_coding_or_regulatory", False)
    assert classify_variant_consequence("Splice_Region") == ("non_coding_or_regulatory", False)
    assert classify_variant_consequence("Unexpected_Label") == ("unclassified", False)
