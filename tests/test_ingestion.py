import pytest

from src.common.config import load_config
from src.ingestion.gdc_client import (
    LiveGdcRequiredError,
    build_files_payload,
    map_hit_to_record,
    query_tcga_metadata,
    query_tcga_metadata_with_audit,
)


def test_tcga_stub_metadata_has_open_access() -> None:
    config = load_config("configs/project_config.yml")
    rows, source_mode = query_tcga_metadata(config, force_stub=True)
    assert rows
    assert source_mode == "stub"
    assert all(row.access == "open" for row in rows)


def test_build_files_payload_contains_required_filters() -> None:
    config = load_config("configs/project_config.yml")
    payload = build_files_payload(config, "TCGA-BRCA")
    filters = payload["filters"]["content"]
    assert any(item["content"]["field"] == "cases.project.project_id" for item in filters)
    assert any(item["content"]["field"] == "files.access" for item in filters)
    assert any(item["content"]["field"] == "files.data_category" for item in filters)


def test_map_hit_to_record_extracts_nested_fields() -> None:
    hit = {
        "id": "file-123",
        "file_name": "example.tsv",
        "data_category": "Transcriptome Profiling",
        "data_type": "Gene Expression Quantification",
        "experimental_strategy": "RNA-Seq",
        "analysis": {"workflow_type": "STAR - Counts"},
        "access": "open",
        "file_size": 42,
        "md5sum": "abc123",
        "cases": [
            {
                "case_id": "case-1",
                "submitter_id": "TCGA-XX-0001",
                "project": {
                    "project_id": "TCGA-BRCA",
                    "primary_site": "Breast",
                    "disease_type": "Adenomas and Adenocarcinomas",
                },
                "samples": [{"sample_id": "sample-1", "sample_type": "Primary Tumor"}],
            }
        ],
    }
    record = map_hit_to_record(hit, "TCGA-BRCA")
    assert record.file_id == "file-123"
    assert record.project_id == "TCGA-BRCA"
    assert record.sample_type == "Primary Tumor"
    assert record.workflow_type == "STAR - Counts"


def test_map_hit_to_record_uses_sample_submitter_id_fallback() -> None:
    hit = {
        "id": "file-123",
        "file_name": "example.tsv",
        "cases": [
            {
                "case_id": "case-1",
                "project": {"project_id": "TCGA-BRCA"},
                "samples": [{"submitter_id": "TCGA-XX-0001-01A", "sample_type": "Primary Tumor"}],
            }
        ],
    }
    record = map_hit_to_record(hit, "TCGA-BRCA")
    assert record.sample_id == "TCGA-XX-0001-01A"


def test_query_tcga_metadata_with_audit_force_stub() -> None:
    config = load_config("configs/project_config.yml")
    records, source_mode, audit = query_tcga_metadata_with_audit(config, force_stub=True)
    assert records
    assert source_mode == "stub"
    assert audit["source_mode"] == "stub"
    assert audit["total_records"] == len(records)
    assert audit["fallback_reason"] == "force_stub=true"


def test_require_live_gdc_blocks_stub_fallback_when_live_query_fails() -> None:
    config = load_config("configs/project_config.yml")
    config.tcga.require_live_gdc = True
    config.gdc_api.base_url = "http://127.0.0.1:9"
    config.gdc_api.retry_count = 0
    config.gdc_api.request_timeout_sec = 1
    with pytest.raises(LiveGdcRequiredError, match="require_live_gdc=true") as exc_info:
        query_tcga_metadata_with_audit(config)
    assert exc_info.value.audit["source_mode"] == "failed_live_required"
