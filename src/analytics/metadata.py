from __future__ import annotations

from pathlib import Path

import polars as pl


def metadata_projects(
    silver_path: str | Path = "data/silver/silver_projects.parquet",
) -> dict[str, list[str]]:
    path = Path(silver_path)
    if not path.exists():
        return {"projects": ["TCGA-BRCA", "TCGA-LUAD", "TCGA-COAD"]}
    df = pl.read_parquet(path)
    if df.is_empty() or "project_id" not in df.columns:
        return {"projects": []}
    projects = (
        df.select(pl.col("project_id").cast(pl.Utf8).unique())
        .drop_nulls()
        .to_series(0)
        .to_list()
    )
    return {"projects": sorted(str(p) for p in projects)}


def metadata_samples(
    project_id: str,
    silver_path: str | Path = "data/silver/silver_samples.parquet",
) -> dict[str, object]:
    path = Path(silver_path)
    if not path.exists():
        return {"project_id": project_id, "sample_count": 0, "sample_types": []}
    df = pl.read_parquet(path)
    if df.is_empty() or not {"project_id", "sample_id"}.issubset(set(df.columns)):
        return {"project_id": project_id, "sample_count": 0, "sample_types": []}

    filtered = df.filter(pl.col("project_id").cast(pl.Utf8) == project_id)
    sample_count = (
        filtered.select(pl.col("sample_id").n_unique()).item(0, 0)
        if not filtered.is_empty()
        else 0
    )
    sample_types = (
        filtered.select(pl.col("sample_type").cast(pl.Utf8).unique())
        .drop_nulls()
        .to_series(0)
        .to_list()
        if not filtered.is_empty() and "sample_type" in filtered.columns
        else []
    )
    return {
        "project_id": project_id,
        "sample_count": int(sample_count),
        "sample_types": sorted(str(s) for s in sample_types),
    }
