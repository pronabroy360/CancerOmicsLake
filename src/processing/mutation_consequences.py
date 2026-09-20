from __future__ import annotations


PROTEIN_ALTERING_CLASSIFICATIONS = frozenset(
    {
        "DE_NOVO_START_INFRAME",
        "DE_NOVO_START_OUTOFFRAME",
        "FRAME_SHIFT_DEL",
        "FRAME_SHIFT_INS",
        "IN_FRAME_DEL",
        "IN_FRAME_INS",
        "MISSENSE_MUTATION",
        "NONSENSE_MUTATION",
        "NONSTOP_MUTATION",
        "SPLICE_SITE",
        "START_CODON_DEL",
        "START_CODON_INS",
        "START_CODON_SNP",
        "STOP_CODON_DEL",
        "STOP_CODON_INS",
        "TRANSLATION_START_SITE",
    }
)

SYNONYMOUS_CLASSIFICATIONS = frozenset({"SILENT"})

NON_CODING_OR_REGULATORY_CLASSIFICATIONS = frozenset(
    {
        "3'FLANK",
        "3'UTR",
        "5'FLANK",
        "5'UTR",
        "IGR",
        "INTRON",
        "LINCRNA",
        "RNA",
        "SPLICE_REGION",
        "TARGETED_REGION",
    }
)

PUTATIVE_LOSS_OF_FUNCTION_CLASSIFICATIONS = frozenset(
    {
        "FRAME_SHIFT_DEL",
        "FRAME_SHIFT_INS",
        "NONSENSE_MUTATION",
        "NONSTOP_MUTATION",
        "SPLICE_SITE",
        "TRANSLATION_START_SITE",
    }
)

MISSENSE_CLASSIFICATIONS = frozenset({"MISSENSE_MUTATION"})

INFRAME_CLASSIFICATIONS = frozenset(
    {
        "DE_NOVO_START_INFRAME",
        "IN_FRAME_DEL",
        "IN_FRAME_INS",
        "START_CODON_DEL",
        "START_CODON_INS",
        "STOP_CODON_DEL",
        "STOP_CODON_INS",
    }
)


def normalize_variant_classification(value: object) -> str:
    return str(value or "").strip().upper().replace(" ", "_")


def classify_variant_consequence(value: object) -> tuple[str, bool]:
    normalized = normalize_variant_classification(value)
    if normalized in PROTEIN_ALTERING_CLASSIFICATIONS:
        return "protein_altering", True
    if normalized in SYNONYMOUS_CLASSIFICATIONS:
        return "synonymous", False
    if normalized in NON_CODING_OR_REGULATORY_CLASSIFICATIONS:
        return "non_coding_or_regulatory", False
    return "unclassified", False


def classify_protein_impact(value: object) -> str:
    """Provide auditable MAF-class groupings without inferring pathogenicity."""
    normalized = normalize_variant_classification(value)
    if normalized in PUTATIVE_LOSS_OF_FUNCTION_CLASSIFICATIONS:
        return "putative_loss_of_function"
    if normalized in MISSENSE_CLASSIFICATIONS:
        return "missense"
    if normalized in INFRAME_CLASSIFICATIONS:
        return "inframe"
    if normalized in PROTEIN_ALTERING_CLASSIFICATIONS:
        return "other_protein_altering"
    return "not_protein_altering"
