import pytest

from src.common.config import load_config
from src.ingestion.gdc_client import (
    GdcQuerySlice,
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
    assert payload["sort"] == "file_id:asc"


def test_build_files_payload_supports_targeted_star_expression_slice() -> None:
    config = load_config("configs/project_config.yml")
    payload = build_files_payload(
        config,
        "TCGA-BRCA",
        query_slice=GdcQuerySlice(
            name="expression_star_counts",
            data_categories=["Transcriptome Profiling"],
            data_types=["Gene Expression Quantification"],
            experimental_strategies=["RNA-Seq"],
            workflow_types=["STAR - Counts"],
            size=500,
        ),
    )
    filters = payload["filters"]["content"]
    values_by_field = {item["content"]["field"]: item["content"]["value"] for item in filters}
    assert values_by_field["files.data_category"] == ["Transcriptome Profiling"]
    assert values_by_field["files.data_type"] == ["Gene Expression Quantification"]
    assert values_by_field["files.experimental_strategy"] == ["RNA-Seq"]
    assert values_by_field["files.analysis.workflow_type"] == ["STAR - Counts"]
    assert payload["size"] == "500"


def test_build_files_payload_supports_adjacent_normal_expression_slice() -> None:
    config = load_config("configs/project_config.yml")
    payload = build_files_payload(
        config,
        "TCGA-BRCA",
        query_slice=GdcQuerySlice(
            name="expression_star_counts_normal",
            data_categories=["Transcriptome Profiling"],
            data_types=["Gene Expression Quantification"],
            experimental_strategies=["RNA-Seq"],
            workflow_types=["STAR - Counts"],
            sample_types=["Solid Tissue Normal"],
            size=100,
        ),
    )
    filters = payload["filters"]["content"]
    values_by_field = {item["content"]["field"]: item["content"]["value"] for item in filters}
    assert values_by_field["cases.samples.sample_type"] == ["Solid Tissue Normal"]


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


def test_query_tcga_metadata_live_uses_targeted_slices_and_deduplicates(monkeypatch) -> None:
    config = load_config("configs/project_config.yml")
    config.tcga.projects = ["TCGA-BRCA"]
    config.tcga.use_stub_on_error = False

    def fake_post_json(url: str, payload: dict, timeout_sec: int) -> dict:  # noqa: ARG001
        filters = payload["filters"]["content"]
        fields = {item["content"]["field"]: item["content"]["value"] for item in filters}
        workflow_values = fields.get("files.analysis.workflow_type", [])
        data_type_values = fields.get("files.data_type", [])
        if workflow_values == ["STAR - Counts"]:
            hits = [
                {
                    "file_id": "expr-1",
                    "file_name": "expr.tsv",
                    "data_category": "Transcriptome Profiling",
                    "data_type": "Gene Expression Quantification",
                    "experimental_strategy": "RNA-Seq",
                    "analysis": {"workflow_type": "STAR - Counts"},
                    "access": "open",
                    "file_size": 10,
                    "md5sum": "abc",
                    "cases": [{"case_id": "case-1", "project": {"project_id": "TCGA-BRCA"}, "samples": [{"sample_id": "sample-1"}]}],
                }
            ]
        elif data_type_values == ["Masked Somatic Mutation"]:
            hits = [
                {
                    "file_id": "mut-1",
                    "file_name": "mut.maf.gz",
                    "data_category": "Simple Nucleotide Variation",
                    "data_type": "Masked Somatic Mutation",
                    "experimental_strategy": "WXS",
                    "analysis": {"workflow_type": "Aliquot Ensemble Somatic Variant Merging and Masking"},
                    "access": "open",
                    "file_size": 10,
                    "md5sum": "def",
                    "cases": [{"case_id": "case-1", "project": {"project_id": "TCGA-BRCA"}, "samples": [{"sample_id": "sample-1"}]}],
                }
            ]
        else:
            hits = [
                {
                    "file_id": "expr-1",
                    "file_name": "expr.tsv",
                    "data_category": "Transcriptome Profiling",
                    "data_type": "Gene Expression Quantification",
                    "experimental_strategy": "RNA-Seq",
                    "analysis": {"workflow_type": "STAR - Counts"},
                    "access": "open",
                    "file_size": 10,
                    "md5sum": "abc",
                    "cases": [{"case_id": "case-1", "project": {"project_id": "TCGA-BRCA"}, "samples": [{"sample_id": "sample-1"}]}],
                }
            ]
        return {"data": {"hits": hits}}

    monkeypatch.setattr("src.ingestion.gdc_client._post_json", fake_post_json)
    records, source_mode, audit = query_tcga_metadata_with_audit(config)
    assert source_mode == "live"
    assert {record.file_id for record in records} == {"expr-1", "mut-1"}
    assert audit["project_audits"][0]["attempts"] == 4
    assert [item["slice"] for item in audit["project_audits"][0]["query_slices"]] == [
        "broad",
        "expression_star_counts",
        "expression_star_counts_normal",
        "masked_somatic_mutation",
    ]


def test_require_live_gdc_blocks_stub_fallback_when_live_query_fails() -> None:
    config = load_config("configs/project_config.yml")
    config.tcga.require_live_gdc = True
    config.gdc_api.base_url = "http://127.0.0.1:9"
    config.gdc_api.retry_count = 0
    config.gdc_api.request_timeout_sec = 1
    with pytest.raises(LiveGdcRequiredError, match="require_live_gdc=true") as exc_info:
        query_tcga_metadata_with_audit(config)
    assert exc_info.value.audit["source_mode"] == "failed_live_required"
