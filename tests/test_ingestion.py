from src.common.config import load_config
from src.ingestion.gdc_client import build_files_payload, map_hit_to_record, query_tcga_metadata


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
