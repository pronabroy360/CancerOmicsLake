from pathlib import Path

import polars as pl

from src.processing.build_silver_tables import build_silver_tables_from_bronze


def test_build_silver_tables_from_bronze(tmp_path: Path) -> None:
    bronze_dir = tmp_path / "bronze"
    silver_dir = tmp_path / "silver"
    bronze_dir.mkdir(parents=True, exist_ok=True)

    metadata_path = bronze_dir / "tcga_metadata_stub.csv"
    df = pl.DataFrame(
        {
            "project_id": ["TCGA-BRCA", "TCGA-BRCA"],
            "case_id": ["case-1", "case-1"],
            "submitter_id": ["sub-1", "sub-1"],
            "sample_id": ["sample-1", "sample-1"],
            "sample_type": ["Primary Tumor", "Primary Tumor"],
            "primary_site": ["Breast", "Breast"],
            "disease_type": ["Adenocarcinoma", "Adenocarcinoma"],
            "file_id": ["file-1", "file-2"],
            "file_name": ["f1.tsv", "f2.tsv"],
            "data_category": ["Transcriptome Profiling", "Clinical"],
            "data_type": ["Gene Expression Quantification", "Clinical Supplement"],
            "experimental_strategy": ["RNA-Seq", "RNA-Seq"],
            "workflow_type": ["STAR - Counts", "STAR - Counts"],
            "access": ["open", "open"],
            "file_size": ["100", "200"],
            "md5sum": ["abc", "def"],
        }
    )
    df.write_csv(metadata_path)

    summary = build_silver_tables_from_bronze(bronze_metadata_dir=bronze_dir, silver_dir=silver_dir)

    assert summary["projects_count"] == 1
    assert summary["patients_count"] == 1
    assert summary["samples_count"] == 1
    assert summary["file_manifest_count"] == 2

    assert (silver_dir / "silver_projects.parquet").exists()
    assert (silver_dir / "silver_patients.parquet").exists()
    assert (silver_dir / "silver_samples.parquet").exists()
    assert (silver_dir / "silver_file_manifest.parquet").exists()

