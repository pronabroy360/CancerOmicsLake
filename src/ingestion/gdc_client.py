from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import json
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

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


class GdcProjectQueryError(RuntimeError):
    def __init__(self, project_id: str, attempts: int, message: str) -> None:
        super().__init__(message)
        self.project_id = project_id
        self.attempts = attempts


class LiveGdcRequiredError(RuntimeError):
    def __init__(self, message: str, audit: dict[str, Any]) -> None:
        super().__init__(message)
        self.audit = audit


def query_tcga_metadata_stub(config: AppConfig) -> list[GdcFileRecord]:
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


def build_files_payload(config: AppConfig, project_id: str) -> dict[str, Any]:
    filters_content: list[dict[str, Any]] = [
        {
            "op": "in",
            "content": {"field": "cases.project.project_id", "value": [project_id]},
        },
        {
            "op": "in",
            "content": {"field": "files.access", "value": [config.tcga.access.type]},
        },
        {
            "op": "in",
            "content": {"field": "files.data_category", "value": config.tcga.data_categories},
        },
    ]

    if config.tcga.data_types:
        filters_content.append(
            {"op": "in", "content": {"field": "files.data_type", "value": config.tcga.data_types}}
        )
    if config.tcga.experimental_strategies:
        filters_content.append(
            {
                "op": "in",
                "content": {
                    "field": "files.experimental_strategy",
                    "value": config.tcga.experimental_strategies,
                },
            }
        )
    if config.tcga.workflow_types:
        filters_content.append(
            {
                "op": "in",
                "content": {"field": "files.analysis.workflow_type", "value": config.tcga.workflow_types},
            }
        )

    fields = ",".join(
        [
            "file_id",
            "file_name",
            "data_category",
            "data_type",
            "experimental_strategy",
            "analysis.workflow_type",
            "access",
            "file_size",
            "md5sum",
            "cases.case_id",
            "cases.submitter_id",
            "cases.project.project_id",
            "cases.project.primary_site",
            "cases.project.disease_type",
            "cases.samples.sample_id",
            "cases.samples.submitter_id",
            "cases.samples.sample_type",
        ]
    )
    return {
        "filters": {"op": "and", "content": filters_content},
        "format": "JSON",
        "fields": fields,
        "size": str(config.tcga.max_files_per_project),
    }


def _coerce_to_text(value: Any, default: str = "Unknown") -> str:
    if value is None:
        return default
    if isinstance(value, list):
        if not value:
            return default
        return str(value[0])
    return str(value)


def _extract_first_case(hit: dict[str, Any]) -> dict[str, Any]:
    cases = hit.get("cases")
    if isinstance(cases, list) and cases:
        first = cases[0]
        if isinstance(first, dict):
            return first
    return {}


def _extract_first_sample(case: dict[str, Any]) -> dict[str, Any]:
    samples = case.get("samples")
    if isinstance(samples, list) and samples:
        first = samples[0]
        if isinstance(first, dict):
            return first
    return {}


def map_hit_to_record(hit: dict[str, Any], default_project_id: str) -> GdcFileRecord:
    case = _extract_first_case(hit)
    sample = _extract_first_sample(case)
    project = case.get("project", {}) if isinstance(case.get("project"), dict) else {}
    analysis = hit.get("analysis", {}) if isinstance(hit.get("analysis"), dict) else {}

    file_id = _coerce_to_text(hit.get("file_id") or hit.get("id"), default="")
    return GdcFileRecord(
        project_id=_coerce_to_text(project.get("project_id"), default=default_project_id),
        case_id=_coerce_to_text(case.get("case_id")),
        submitter_id=_coerce_to_text(case.get("submitter_id")),
        sample_id=_coerce_to_text(sample.get("sample_id") or sample.get("submitter_id")),
        sample_type=_coerce_to_text(sample.get("sample_type")),
        primary_site=_coerce_to_text(project.get("primary_site")),
        disease_type=_coerce_to_text(project.get("disease_type")),
        file_id=file_id,
        file_name=_coerce_to_text(hit.get("file_name")),
        data_category=_coerce_to_text(hit.get("data_category")),
        data_type=_coerce_to_text(hit.get("data_type")),
        experimental_strategy=_coerce_to_text(hit.get("experimental_strategy")),
        workflow_type=_coerce_to_text(analysis.get("workflow_type")),
        access=_coerce_to_text(hit.get("access"), default="open"),
        file_size=int(hit.get("file_size") or 0),
        md5sum=_coerce_to_text(hit.get("md5sum"), default=""),
    )


def _post_json(url: str, payload: dict[str, Any], timeout_sec: int) -> dict[str, Any]:
    encoded = json.dumps(payload).encode("utf-8")
    request = Request(
        url=url,
        data=encoded,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=timeout_sec) as response:
        body = response.read().decode("utf-8")
    parsed = json.loads(body)
    if not isinstance(parsed, dict):
        raise ValueError("GDC response is not a JSON object.")
    return parsed


def _query_project_files(config: AppConfig, project_id: str) -> tuple[list[GdcFileRecord], int]:
    payload = build_files_payload(config, project_id)
    url = f"{config.gdc_api.base_url.rstrip('/')}{config.gdc_api.files_endpoint}"

    last_error: Exception | None = None
    for attempt in range(config.gdc_api.retry_count + 1):
        try:
            raw = _post_json(url, payload, timeout_sec=config.gdc_api.request_timeout_sec)
            hits = raw.get("data", {}).get("hits", [])
            if not isinstance(hits, list):
                raise ValueError("GDC response data.hits is not a list.")
            return [map_hit_to_record(hit, project_id) for hit in hits if isinstance(hit, dict)], attempt + 1
        except (HTTPError, URLError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
            last_error = exc
            if attempt >= config.gdc_api.retry_count:
                break
            time.sleep(config.gdc_api.retry_backoff_sec * (attempt + 1))
    attempts = config.gdc_api.retry_count + 1
    raise GdcProjectQueryError(
        project_id=project_id,
        attempts=attempts,
        message=f"GDC query failed for {project_id}: {last_error}",
    ) from last_error


def query_tcga_metadata_with_audit(
    config: AppConfig,
    force_stub: bool = False,
) -> tuple[list[GdcFileRecord], str, dict[str, Any]]:
    started_at = datetime.now(UTC).isoformat()
    project_audits: list[dict[str, Any]] = []

    if force_stub:
        records = query_tcga_metadata_stub(config)
        ended_at = datetime.now(UTC).isoformat()
        return records, "stub", {
            "started_at": started_at,
            "ended_at": ended_at,
            "source_mode": "stub",
            "requested_projects": config.tcga.projects,
            "total_records": len(records),
            "fallback_reason": "force_stub=true",
            "project_audits": [
                {
                    "project_id": project_id,
                    "status": "stub",
                    "attempts": 0,
                    "record_count": 0,
                    "error": "",
                }
                for project_id in config.tcga.projects
            ],
        }

    try:
        records: list[GdcFileRecord] = []
        for project_id in config.tcga.projects:
            project_records, attempts = _query_project_files(config, project_id)
            records.extend(project_records)
            project_audits.append(
                {
                    "project_id": project_id,
                    "status": "live",
                    "attempts": attempts,
                    "record_count": len(project_records),
                    "error": "",
                }
            )
        ended_at = datetime.now(UTC).isoformat()
        return records, "live", {
            "started_at": started_at,
            "ended_at": ended_at,
            "source_mode": "live",
            "requested_projects": config.tcga.projects,
            "total_records": len(records),
            "fallback_reason": "",
            "project_audits": project_audits,
        }
    except GdcProjectQueryError as exc:
        project_audits.append(
            {
                "project_id": exc.project_id,
                "status": "failed",
                "attempts": exc.attempts,
                "record_count": 0,
                "error": str(exc),
            }
        )
        if config.tcga.require_live_gdc:
            ended_at = datetime.now(UTC).isoformat()
            audit = {
                "started_at": started_at,
                "ended_at": ended_at,
                "source_mode": "failed_live_required",
                "requested_projects": config.tcga.projects,
                "total_records": 0,
                "fallback_reason": str(exc),
                "project_audits": project_audits,
            }
            raise LiveGdcRequiredError(
                "Live GDC metadata is required (require_live_gdc=true), but the live query failed.",
                audit=audit,
            ) from exc
        if config.tcga.use_stub_on_error:
            stub_records = query_tcga_metadata_stub(config)
            ended_at = datetime.now(UTC).isoformat()
            return stub_records, "stub", {
                "started_at": started_at,
                "ended_at": ended_at,
                "source_mode": "stub",
                "requested_projects": config.tcga.projects,
                "total_records": len(stub_records),
                "fallback_reason": str(exc),
                "project_audits": project_audits,
            }
        raise


def query_tcga_metadata(config: AppConfig, force_stub: bool = False) -> tuple[list[GdcFileRecord], str]:
    records, source_mode, _ = query_tcga_metadata_with_audit(config, force_stub=force_stub)
    return records, source_mode
