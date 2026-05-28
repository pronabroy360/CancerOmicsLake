from pathlib import Path

import polars as pl

from src.analytics.metadata import metadata_projects, metadata_samples


def test_metadata_projects_reads_silver_projects(tmp_path: Path) -> None:
    silver_projects = tmp_path / "silver_projects.parquet"
    pl.DataFrame(
        {"project_id": ["TCGA-BRCA", "TCGA-LUAD", "TCGA-BRCA"], "primary_site": ["Breast", "Lung", "Breast"]}
    ).write_parquet(silver_projects)

    payload = metadata_projects(silver_projects)
    assert payload["projects"] == ["TCGA-BRCA", "TCGA-LUAD"]


def test_metadata_samples_reads_silver_samples(tmp_path: Path) -> None:
    silver_samples = tmp_path / "silver_samples.parquet"
    pl.DataFrame(
        {
            "project_id": ["TCGA-BRCA", "TCGA-BRCA", "TCGA-LUAD"],
            "case_id": ["c1", "c2", "c3"],
            "sample_id": ["s1", "s2", "s3"],
            "sample_type": ["Primary Tumor", "Solid Tissue Normal", "Primary Tumor"],
        }
    ).write_parquet(silver_samples)

    payload = metadata_samples("TCGA-BRCA", silver_samples)
    assert payload["project_id"] == "TCGA-BRCA"
    assert payload["sample_count"] == 2
    assert payload["sample_types"] == ["Primary Tumor", "Solid Tissue Normal"]


def test_metadata_samples_missing_file_fallback(tmp_path: Path) -> None:
    payload = metadata_samples("TCGA-COAD", tmp_path / "missing.parquet")
    assert payload["project_id"] == "TCGA-COAD"
    assert payload["sample_count"] == 0
