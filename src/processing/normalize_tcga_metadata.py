from __future__ import annotations

from src.ingestion.gdc_client import GdcFileRecord


def normalize_tcga_records(records: list[GdcFileRecord]) -> list[dict[str, str]]:
    return [
        {
            "project_id": r.project_id,
            "case_id": r.case_id,
            "sample_id": r.sample_id,
            "sample_type": r.sample_type,
            "file_id": r.file_id,
            "file_name": r.file_name,
            "data_category": r.data_category,
            "workflow_type": r.workflow_type,
            "access": r.access,
        }
        for r in records
    ]
