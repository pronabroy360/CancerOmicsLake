from pathlib import Path
import gzip

import polars as pl

from src.common.config import load_config
from src.processing.build_mutation_table import build_mutation_profile_table, load_tcga_mutation_table
from src.quality.checks import run_silver_quality_checks


def test_load_tcga_mutation_table_prefers_manifest_files(tmp_path: Path) -> None:
    config = load_config("configs/project_config.yml")
    ingest_time = "2026-05-28T00:00:00Z"

    tcga_root = tmp_path / "tcga"
    mut_dir = tcga_root / "TCGA-LUAD" / "mutations"
    mut_dir.mkdir(parents=True, exist_ok=True)

    maf_file = mut_dir / "luad.maf"
    maf_file.write_text(
        "Hugo_Symbol\tTumor_Sample_Barcode\tVariant_Classification\tVariant_Type\tNCBI_Build\tChromosome\tStart_Position\tEnd_Position\tReference_Allele\tTumor_Seq_Allele2\tTranscript_ID\tHGVSc\tHGVSp\tIMPACT\tConsequence\tall_effects\n"
        "TP53\tTCGA-LUAD-SAMPLE-0001\tMissense_Mutation\tSNP\tGRCh38\t17\t7673803\t7673803\tC\tT\tENST00000269305\tENST00000269305.9:c.818G>A\tp.Arg273His\tMODERATE\tmissense_variant\t[TP53,missense_variant,p.R273H,ENST00000269305]\n",
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
    assert row["consequence_group"] == "protein_altering"
    assert row["is_protein_altering"] is True
    assert row["start_position"] == 7673803
    assert row["reference_assembly"] == "GRCh38"
    assert row["transcript_id"] == "ENST00000269305"
    assert row["hgvsp"] == "p.Arg273His"
    assert row["vep_impact"] == "MODERATE"
    assert row["all_effects"].startswith("[TP53,")


def test_load_tcga_mutation_table_reads_gz_maf_with_comments(tmp_path: Path) -> None:
    config = load_config("configs/project_config.yml")
    ingest_time = "2026-05-28T00:00:00Z"

    tcga_root = tmp_path / "tcga"
    mut_dir = tcga_root / "TCGA-BRCA" / "mutations"
    mut_dir.mkdir(parents=True, exist_ok=True)

    maf_gz = mut_dir / "brca.maf.gz"
    with gzip.open(maf_gz, mode="wt", encoding="utf-8") as fh:
        fh.write("#version gdc-1.0.0\n")
        fh.write(
            "Hugo_Symbol\tTumor_Sample_Barcode\tVariant_Classification\tVariant_Type\tNCBI_Build\tChromosome\tStart_Position\tEnd_Position\tReference_Allele\tTumor_Seq_Allele2\n"
        )
        fh.write("PIK3CA\tTCGA-BRCA-SAMPLE-0001\tMissense_Mutation\tSNP\tGRCh38\t3\t179218294\t179218294\tA\tG\n")

    metadata_df = pl.DataFrame(
        {
            "project_id": ["TCGA-BRCA"],
            "case_id": ["BRCA-CASE-1"],
            "sample_id": ["TCGA-BRCA-SAMPLE-0001"],
            "file_name": ["brca.maf.gz"],
            "data_category": ["Simple Nucleotide Variation"],
            "data_type": ["Masked Somatic Mutation"],
            "access": ["open"],
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
    assert row["project_id"] == "TCGA-BRCA"
    assert row["gene_symbol"] == "PIK3CA"
    assert row["start_position"] == 179218294
    assert row["reference_assembly"] == "GRCh38"


def test_mutation_barcode_maps_to_unique_profile_uuid_and_retains_source(tmp_path: Path) -> None:
    root = tmp_path / "tcga"
    directory = root / "TCGA-LUAD" / "mutations"
    directory.mkdir(parents=True)
    (directory / "one.maf").write_text(
        "Hugo_Symbol\tTumor_Sample_Barcode\tCase_ID\tStart_Position\n"
        "TP53\tTCGA-CASE-01A\tcase-uuid\t100\n",
        encoding="utf-8",
    )
    metadata = pl.DataFrame(
        {
            "project_id": ["TCGA-LUAD"],
            "case_id": ["case-uuid"],
            "sample_id": ["sample-uuid"],
            "file_name": ["one.maf"],
            "data_category": ["Simple Nucleotide Variation"],
            "data_type": ["Masked Somatic Mutation"],
            "access": ["open"],
        }
    )

    row = load_tcga_mutation_table(load_config("configs/project_config.yml"), "now", metadata, root).row(0, named=True)

    assert row["sample_id"] == "sample-uuid"
    assert row["source_sample_id"] == "TCGA-CASE-01A"


def test_ambiguous_mutation_file_sample_mapping_remains_unresolved(tmp_path: Path) -> None:
    root = tmp_path / "tcga"
    directory = root / "TCGA-LUAD" / "mutations"
    directory.mkdir(parents=True)
    (directory / "one.maf").write_text(
        "Hugo_Symbol\tTumor_Sample_Barcode\tCase_ID\tStart_Position\n"
        "TP53\tTCGA-CASE-01A\tcase-uuid\t100\n",
        encoding="utf-8",
    )
    metadata = pl.DataFrame(
        {
            "project_id": ["TCGA-LUAD", "TCGA-LUAD"],
            "case_id": ["case-uuid", "case-uuid"],
            "sample_id": ["sample-uuid-1", "sample-uuid-2"],
            "file_name": ["one.maf", "one.maf"],
            "data_category": ["Simple Nucleotide Variation"] * 2,
            "data_type": ["Masked Somatic Mutation"] * 2,
            "access": ["open"] * 2,
        }
    )

    row = load_tcga_mutation_table(load_config("configs/project_config.yml"), "now", metadata, root).row(0, named=True)

    assert row["sample_id"] == "TCGA-CASE-01A"
    assert row["source_sample_id"] == "TCGA-CASE-01A"


def test_quality_rejects_mutation_samples_without_profile_link(tmp_path: Path) -> None:
    silver = tmp_path / "silver"
    silver.mkdir()
    pl.DataFrame({"project_id": ["TCGA-LUAD"], "case_id": ["case-1"], "sample_id": ["barcode"]}).write_parquet(
        silver / "silver_mutations.parquet"
    )
    pl.DataFrame({"project_id": ["TCGA-LUAD"], "case_id": ["case-1"], "sample_id": ["uuid"]}).write_parquet(
        silver / "silver_mutation_profile.parquet"
    )

    checks = {check.check_name: check for check in run_silver_quality_checks(silver, gold_dir=tmp_path / "gold")}

    assert checks["silver_mutation_samples_in_profile"].status == "failed"
    assert checks["silver_mutation_samples_in_profile"].failed_rows == 1


def test_build_mutation_profile_uses_only_downloaded_open_maf_files(tmp_path: Path) -> None:
    tcga_root = tmp_path / "tcga"
    mutation_dir = tcga_root / "TCGA-LUAD" / "mutations"
    mutation_dir.mkdir(parents=True)
    (mutation_dir / "downloaded.maf").write_text("header\n", encoding="utf-8")

    metadata = pl.DataFrame(
        {
            "project_id": ["TCGA-LUAD", "TCGA-LUAD"],
            "case_id": ["case-1", "case-2"],
            "sample_id": ["sample-1", "sample-2"],
            "file_id": ["file-1", "file-2"],
            "file_name": ["downloaded.maf", "not-downloaded.maf"],
            "data_category": ["Simple Nucleotide Variation", "Simple Nucleotide Variation"],
            "data_type": ["Masked Somatic Mutation", "Masked Somatic Mutation"],
            "access": ["open", "open"],
            "file_size": [7, 9],
            "md5sum": ["abc", "def"],
        }
    )

    profile = build_mutation_profile_table(metadata, "2026-07-16T00:00:00Z", tcga_root)

    assert profile.height == 1
    assert profile.row(0, named=True)["sample_id"] == "sample-1"
    assert profile.row(0, named=True)["profile_status"] == "downloaded"
