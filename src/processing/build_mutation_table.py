from __future__ import annotations


def mutation_stub_rows() -> list[dict[str, str]]:
    return [
        {
            "mutation_key": "stub-mutation-1",
            "sample_key": "stub-sample-1",
            "gene_key": "stub-gene-1",
            "variant_classification": "Missense_Mutation",
            "variant_type": "SNP",
            "chromosome": "17",
            "start_position": "7673803",
            "end_position": "7673803",
            "reference_allele": "C",
            "tumor_seq_allele": "T",
            "source": "TCGA/GDC",
        }
    ]
