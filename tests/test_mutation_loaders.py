from pathlib import Path

import polars as pl

from src.common.config import load_config
from src.processing.build_mutation_table import load_tcga_mutation_table


def test_load_tcga_mutation_table_prefers_manifest_files(tmp_path: Path) -> None:
    config = load_config("configs/project_config.yml")
    ingest_time = "2026-05-28T00:00:00Z"

    tcga_root = tmp_path / "tcga"
    mut_dir = tcga_root / "TCGA-LUAD" / "mutations"
    mut_dir.mkdir(parents=True, exist_ok=True)

    maf_file = mut_dir / "luad.maf"
    maf_file.write_text(
        "Hugo_Symbol\tTumor_Sample_Barcode\tVariant_Classification\tVariant_Type\tChromosome\tStart_Position\tEnd_Position\tReference_Allele\tTumor_Seq_Allele2\n"
        "TP53\tTCGA-LUAD-SAMPLE-0001\tMissense_Mutation\tSNP\t17\t7673803\t7673803\tC\tT\n",
        encoding="utf-8",
    )
    non_mut_file = mut_dir / "not_mut.tsv"
    non_mut_file.write_text(
        "Hugo_Symbol\tTumor_Sample_Barcode\tVariant_Classification\tVariant_Type\tChromosome\tStart_Position\tEnd_Position\tReference_Allele\tTumor_Seq_Allele2\n"
        "EGFR\tTCGA-LUAD-SAMPLE-0002\tMissense_Mutation\tSNP\t7\t55242465\t55242465\tG\tA\n",
        encoding="utf-8",
    )

    metadata_df = pl.DataFrame(
        {
            "project_id": ["TCGA-LUAD", "TCGA-LUAD"],
            "case_id": ["LUAD-CASE-1", "LUAD-CASE-2"],
            "sample_id": ["TCGA-LUAD-SAMPLE-0001", "TCGA-LUAD-SAMPLE-0002"],
            "file_name": ["luad.maf", "not_mut.tsv"],
            "data_category": ["Simple Nucleotide Variation", "Clinical"],
            "data_type": ["Masked Somatic Mutation", "Clinical Supplement"],
            "access": ["open", "open"],
        }
    )

    df = load_tcga_mutation_table(
        config=config,
        ingest_time=ingest_time,
        metadata_df=metadata_df,
        tcga_root_dir=tcga_root,
    )
    assert df.height == 1
    row = df.row(0, named=True)
    assert row["project_id"] == "TCGA-LUAD"
    assert row["gene_symbol"] == "TP53"
    assert row["variant_classification"] == "Missense_Mutation"
    assert row["start_position"] == 7673803
