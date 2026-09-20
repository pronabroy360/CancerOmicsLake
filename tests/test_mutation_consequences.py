from src.processing.mutation_consequences import classify_protein_impact, classify_variant_consequence


def test_classify_variant_consequence_is_conservative() -> None:
    assert classify_variant_consequence("Missense_Mutation") == ("protein_altering", True)
    assert classify_variant_consequence("Frame_Shift_Del") == ("protein_altering", True)
    assert classify_variant_consequence("Silent") == ("synonymous", False)
    assert classify_variant_consequence("3'UTR") == ("non_coding_or_regulatory", False)
    assert classify_variant_consequence("Splice_Region") == ("non_coding_or_regulatory", False)
    assert classify_variant_consequence("Unexpected_Label") == ("unclassified", False)


def test_classify_protein_impact_does_not_infer_driver_status() -> None:
    assert classify_protein_impact("Nonsense_Mutation") == "putative_loss_of_function"
    assert classify_protein_impact("Missense_Mutation") == "missense"
    assert classify_protein_impact("In_Frame_Del") == "inframe"
    assert classify_protein_impact("Start_Codon_SNP") == "other_protein_altering"
    assert classify_protein_impact("Silent") == "not_protein_altering"
