from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, ValidationError


class ProjectConfig(BaseModel):
    name: str
    version: str
    mode: str = "open_access"


class AccessConfig(BaseModel):
    type: str = "open"


class TcgaConfig(BaseModel):
    projects: list[str]
    data_categories: list[str]
    access: AccessConfig = Field(default_factory=AccessConfig)
    metadata_only: bool = True
    max_files_per_project: int = 200
    data_types: list[str] | None = None
    experimental_strategies: list[str] | None = None
    workflow_types: list[str] | None = None
    use_stub_on_error: bool = True
    require_live_gdc: bool = False
    download_caps_by_project: dict[str, dict[str, int]] = Field(default_factory=dict)


class GdcApiConfig(BaseModel):
    base_url: str = "https://api.gdc.cancer.gov"
    files_endpoint: str = "/files"
    request_timeout_sec: int = 60
    retry_count: int = 2
    retry_backoff_sec: float = 1.5
    audit_output_path: str = "outputs/reports/gdc_ingestion_audit.json"


class GtexConfig(BaseModel):
    version: str
    tissues: list[str]
    metadata_only: bool = True
    sample_cap_per_tissue: int = 50
    download_base_url: str = "https://storage.googleapis.com/adult-gtex/bulk-gex/v8/rna-seq/tpms-by-tissue"
    sample_attributes_url: str = (
        "https://storage.googleapis.com/adult-gtex/annotations/v8/metadata-files/"
        "GTEx_Analysis_v8_Annotations_SampleAttributesDS.txt"
    )
    tissue_files: dict[str, str] = Field(default_factory=dict)


class StorageConfig(BaseModel):
    format: str = "parquet"
    database: str = "duckdb"
    duckdb_path: str = "outputs/canceromicslake.duckdb"


class QualityConfig(BaseModel):
    gene_mapping_rate_threshold: float = 0.98
    fail_on_controlled_access: bool = True


class AppConfig(BaseModel):
    project: ProjectConfig
    tcga: TcgaConfig
    gtex: GtexConfig
    storage: StorageConfig
    quality: QualityConfig
    gdc_api: GdcApiConfig = Field(default_factory=GdcApiConfig)


def load_raw_yaml(path: str | Path) -> dict[str, Any]:
    path_obj = Path(path)
    with path_obj.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Config root must be a dictionary: {path_obj}")
    return data


def load_config(path: str | Path) -> AppConfig:
    raw = load_raw_yaml(path)
    try:
        config = AppConfig(**raw)
    except ValidationError as exc:
        raise ValueError(f"Invalid config file {path}: {exc}") from exc
    if config.project.mode != "open_access":
        raise ValueError("Only open_access mode is allowed in this public scaffold.")
    if config.tcga.access.type != "open":
        raise ValueError("tcga.access.type must be 'open' in this public scaffold.")
    return config
