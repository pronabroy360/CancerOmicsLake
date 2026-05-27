from __future__ import annotations

from dataclasses import dataclass

from src.common.config import AppConfig


@dataclass
class GdcFileRecord:
    project_id: str
    case_id: str
    submitter_id: str
    sample_id: str
    sample_type: str
    primary_site: str
    disease_type: str
    file_id: str
    file_name: str
    data_category: str
    data_type: str
    experimental_strategy: str
    workflow_type: str
    access: str
    file_size: int
    md5sum: str


def query_tcga_metadata_stub(config: AppConfig) -> list[GdcFileRecord]:
    """Metadata-only scaffold. Replace with real GDC API queries in M2."""
    records: list[GdcFileRecord] = []
    for project in config.tcga.projects:
        for idx, category in enumerate(config.tcga.data_categories, start=1):
            records.append(
                GdcFileRecord(
                    project_id=project,
                    case_id=f"{project}-CASE-{idx:04d}",
                    submitter_id=f"{project}-SUB-{idx:04d}",
                    sample_id=f"{project}-SAMPLE-{idx:04d}",
                    sample_type="Primary Tumor",
                    primary_site="Unknown",
                    disease_type="Unknown",
                    file_id=f"{project}-FILE-{idx:04d}",
                    file_name=f"{project.lower()}_{idx:04d}.tsv",
                    data_category=category,
                    data_type="Metadata",
                    experimental_strategy="RNA-Seq",
                    workflow_type="stub-workflow",
                    access="open",
                    file_size=0,
                    md5sum="stub-md5",
                )
            )
    return records
