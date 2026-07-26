from __future__ import annotations

from datetime import UTC, datetime
import gzip
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import tarfile
from typing import Any, Sequence

import polars as pl

from src.graph.public_graph import filter_public_graph_tables


PUBLIC_AGGREGATE_FILES = (
    "gold_batch_effect_sensitivity.parquet",
    "gold_cancer_gene_evidence_confidence.parquet",
    "gold_candidate_bootstrap_stability.parquet",
    "gold_candidate_gene_priority.parquet",
    "gold_cohort_summary.parquet",
    "gold_consensus_candidate_genes.parquet",
    "gold_expression_statistical_support.parquet",
    "gold_external_expression_validation.parquet",
    "gold_mutation_frequency_by_cancer.parquet",
    "gold_mutation_frequency_by_gene.parquet",
    "gold_paired_tcga_expression_support.parquet",
    "gold_pathway_enrichment.parquet",
    "gold_reference_triangulation.parquet",
    "gold_reference_method_comparison.parquet",
    "gold_consensus_ablation_stability.parquet",
    "gold_tumor_vs_normal_expression.parquet",
)

FORBIDDEN_IDENTIFIER_COLUMNS = frozenset(
    {
        "aliquot_id",
        "case_id",
        "case_submitter_id",
        "donor_id",
        "donor_key",
        "gtex_sample_id",
        "individual_id",
        "participant_id",
        "patient_id",
        "patient_key",
        "portion_id",
        "sample_id",
        "sample_key",
        "submitter_id",
    }
)

SEMVER_PATTERN = re.compile(r"^\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?$")
INDIVIDUAL_VALUE_PATTERNS = (
    re.compile(r"^(?:PATIENT|SAMPLE|CASE|DONOR):", re.IGNORECASE),
    re.compile(r"^TCGA-[A-Z0-9]{2}-[A-Z0-9]{4}(?:-|$)", re.IGNORECASE),
    re.compile(r"^GTEX-[A-Z0-9]{4,}(?:-|$)", re.IGNORECASE),
)


def _git_commit() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=False
    )
    return result.stdout.strip() if result.returncode == 0 else "unknown"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_column(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


def _frictionless_type(dtype: pl.DataType) -> str:
    if dtype in (pl.String, pl.Categorical, pl.Enum):
        return "string"
    if dtype.is_integer():
        return "integer"
    if dtype.is_float() or dtype == pl.Decimal:
        return "number"
    if dtype == pl.Boolean:
        return "boolean"
    if dtype == pl.Date:
        return "date"
    if isinstance(dtype, pl.Datetime):
        return "datetime"
    return "any"


def _validate_public_table(frame: pl.DataFrame, resource_name: str) -> dict[str, Any]:
    if frame.is_empty():
        raise RuntimeError(f"Public release resource is empty: {resource_name}")

    unsafe_columns = sorted(
        column
        for column in frame.columns
        if _canonical_column(column) in FORBIDDEN_IDENTIFIER_COLUMNS
    )
    if unsafe_columns:
        raise RuntimeError(
            f"Public release resource {resource_name} contains forbidden identifier columns: "
            f"{', '.join(unsafe_columns)}"
        )

    unsafe_values: list[str] = []
    for column, dtype in frame.schema.items():
        if dtype not in (pl.String, pl.Categorical, pl.Enum):
            continue
        values = frame.get_column(column).drop_nulls().cast(pl.String).unique().to_list()
        if any(
            pattern.search(str(value).strip())
            for value in values
            for pattern in INDIVIDUAL_VALUE_PATTERNS
        ):
            unsafe_values.append(column)
    if unsafe_values:
        raise RuntimeError(
            f"Public release resource {resource_name} contains individual-like values in: "
            f"{', '.join(sorted(unsafe_values))}"
        )

    return {
        "row_count": frame.height,
        "column_count": frame.width,
        "columns": [
            {
                "name": column,
                "type": _frictionless_type(dtype),
                "physical_type": str(dtype),
            }
            for column, dtype in frame.schema.items()
        ],
    }


def _resource_metadata(path: Path, release_dir: Path, frame: pl.DataFrame) -> dict[str, Any]:
    audit = _validate_public_table(frame, path.name)
    return {
        "name": path.stem,
        "path": path.relative_to(release_dir).as_posix(),
        "format": "parquet",
        "media_type": "application/vnd.apache.parquet",
        "bytes": path.stat().st_size,
        "sha256": _sha256(path),
        **audit,
    }


def _write_release_readme(path: Path, version: str, resource_count: int) -> None:
    path.write_text(
        f"""# CancerOmicsLake Derived Research Data v{version}

This bundle contains {resource_count} aggregate, open-access-derived Parquet resources used by the
CancerOmicsLake reproducible research workflow. It excludes raw source data and individual-level
patient, case, donor, and sample identifiers.

## Scope

- TCGA-BRCA, TCGA-LUAD, and TCGA-COAD open-access data from NCI GDC
- GTEx V8 normal tissue expression references
- recount3 uniformly processed expression validation
- Reactome pathway annotations

## Interpretation

The outputs support engineering evaluation and biological hypothesis generation. Cross-source
expression remains susceptible to collection, tissue-composition, and batch confounding. Candidate
prioritization is not evidence of mechanism, causality, clinical validity, or actionability.

## Verification

Run `sha256sum -c checksums.sha256` from this directory. Resource schemas, row counts, provenance,
and hashes are recorded in `manifest.json` and `datapackage.json`.

## Terms

Project code is MIT licensed. No new license is asserted over source biomedical data; reuse remains
subject to the terms and citation requirements of GDC/TCGA, GTEx, recount3, and Reactome.
""",
        encoding="utf-8",
    )


def build_fair_release(
    version: str,
    gold_dir: str | Path = "data/gold",
    output_root: str | Path = "outputs/releases",
    creator: str = "Pronab Chandra Roy",
    required_files: Sequence[str] | None = None,
) -> dict[str, Any]:
    if not SEMVER_PATTERN.fullmatch(version):
        raise ValueError("Release version must be semantic versioning, for example 0.1.0")

    gold = Path(gold_dir)
    selected_files = tuple(required_files or PUBLIC_AGGREGATE_FILES)
    missing = sorted(name for name in selected_files if not (gold / name).exists())
    if missing:
        raise RuntimeError(f"FAIR release is missing required gold resources: {', '.join(missing)}")
    node_path = gold / "gold_graph_nodes.parquet"
    edge_path = gold / "gold_graph_edges.parquet"
    if required_files is None and (not node_path.exists() or not edge_path.exists()):
        raise RuntimeError("FAIR release requires both gold graph node and edge resources")

    release_dir = Path(output_root) / f"v{version}"
    build_dir = Path(output_root) / f".v{version}.building"
    if build_dir.exists():
        shutil.rmtree(build_dir)
    data_dir = build_dir / "data"
    data_dir.mkdir(parents=True)

    resources: list[dict[str, Any]] = []
    for name in selected_files:
        source = gold / name
        destination = data_dir / name
        shutil.copy2(source, destination)
        frame = pl.read_parquet(destination)
        resources.append(_resource_metadata(destination, build_dir, frame))

    graph_audit: dict[str, int] | None = None
    if node_path.exists() and edge_path.exists():
        public_nodes, public_edges, graph_audit = filter_public_graph_tables(
            pl.read_parquet(node_path), pl.read_parquet(edge_path)
        )
        for name, frame in (
            ("public_graph_nodes.parquet", public_nodes),
            ("public_graph_edges.parquet", public_edges),
        ):
            destination = data_dir / name
            frame.write_parquet(destination)
            resources.append(_resource_metadata(destination, build_dir, frame))

    generated_at = datetime.now(UTC).isoformat()
    payload: dict[str, Any] = {
        "schema_version": "1.0",
        "release_version": version,
        "generated_at": generated_at,
        "title": "CancerOmicsLake aggregate derived research data",
        "creator": creator,
        "repository": "https://github.com/pronabroy360/CancerOmicsLake",
        "git_commit": _git_commit(),
        "access_scope": "open-access-derived aggregate outputs only",
        "source_datasets": [
            {"name": "NCI GDC / TCGA", "projects": ["TCGA-BRCA", "TCGA-LUAD", "TCGA-COAD"]},
            {"name": "GTEx", "version": "V8"},
            {"name": "recount3", "processing": "Monorail uniformly processed expression"},
            {"name": "Reactome", "release": "97"},
        ],
        "resource_count": len(resources),
        "total_bytes": sum(int(resource["bytes"]) for resource in resources),
        "resources": resources,
        "graph_publication_audit": graph_audit,
        "identifier_safety": {
            "status": "passed",
            "forbidden_columns": sorted(FORBIDDEN_IDENTIFIER_COLUMNS),
            "individual_value_patterns_checked": len(INDIVIDUAL_VALUE_PATTERNS),
        },
        "limitations": [
            "Cross-source expression comparisons are not fully batch corrected.",
            "Mutation evidence is consequence-stratified but does not establish driver status.",
            "Candidate and pathway results are hypothesis-generating, not clinical claims.",
        ],
    }

    (build_dir / "manifest.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    datapackage = {
        "profile": "data-package",
        "name": "canceromicslake-derived-research-data",
        "title": payload["title"],
        "version": version,
        "created": generated_at,
        "homepage": payload["repository"],
        "contributors": [{"title": creator, "role": "author"}],
        "resources": [
            {
                "name": resource["name"],
                "path": resource["path"],
                "format": resource["format"],
                "mediatype": resource["media_type"],
                "bytes": resource["bytes"],
                "hash": f"sha256:{resource['sha256']}",
                "schema": {"fields": resource["columns"]},
            }
            for resource in resources
        ],
    }
    (build_dir / "datapackage.json").write_text(
        json.dumps(datapackage, indent=2), encoding="utf-8"
    )
    (build_dir / "checksums.sha256").write_text(
        "".join(f"{resource['sha256']}  {resource['path']}\n" for resource in resources),
        encoding="utf-8",
    )
    _write_release_readme(build_dir / "README.md", version, len(resources))
    if release_dir.exists():
        shutil.rmtree(release_dir)
    build_dir.replace(release_dir)
    return {**payload, "release_directory": str(release_dir)}


def package_fair_release(
    version: str,
    release_root: str | Path = "outputs/releases",
) -> dict[str, Any]:
    if not SEMVER_PATTERN.fullmatch(version):
        raise ValueError("Release version must be semantic versioning, for example 0.1.0")
    root = Path(release_root)
    release_dir = root / f"v{version}"
    manifest_path = release_dir / "manifest.json"
    if not manifest_path.is_file():
        raise RuntimeError(f"FAIR release manifest is missing: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict) or manifest.get("release_version") != version:
        raise RuntimeError("FAIR release manifest version does not match the requested archive")
    if manifest.get("identifier_safety", {}).get("status") != "passed":
        raise RuntimeError("FAIR release identifier-safety audit has not passed")
    resources = manifest.get("resources", [])
    if not isinstance(resources, list) or not resources:
        raise RuntimeError("FAIR release manifest contains no resources")
    for resource in resources:
        if not isinstance(resource, dict) or not resource.get("path") or not resource.get(
            "sha256"
        ):
            raise RuntimeError("FAIR release contains an invalid resource entry")
        path = (release_dir / str(resource["path"])).resolve()
        if not path.is_relative_to(release_dir.resolve()):
            raise RuntimeError(f"FAIR resource path escapes release root: {resource['path']}")
        if not path.is_file() or _sha256(path) != resource["sha256"]:
            raise RuntimeError(f"FAIR resource checksum mismatch: {resource['path']}")

    archive_name = f"canceromicslake-derived-data-v{version}.tar.gz"
    archive_path = root / archive_name
    temporary = archive_path.with_suffix(f"{archive_path.suffix}.tmp")
    archive_root = f"canceromicslake-derived-data-v{version}"
    files = sorted(path for path in release_dir.rglob("*") if path.is_file())
    root.mkdir(parents=True, exist_ok=True)
    with temporary.open("wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as compressed:
            with tarfile.open(
                fileobj=compressed,
                mode="w",
                format=tarfile.PAX_FORMAT,
            ) as archive:
                for path in files:
                    arcname = f"{archive_root}/{path.relative_to(release_dir).as_posix()}"
                    info = archive.gettarinfo(str(path), arcname=arcname)
                    info.uid = 0
                    info.gid = 0
                    info.uname = ""
                    info.gname = ""
                    info.mtime = 0
                    info.mode = 0o644
                    with path.open("rb") as handle:
                        archive.addfile(info, handle)
    temporary.replace(archive_path)

    deposit = {
        "schema_version": "1.0",
        "generated_at": datetime.now(UTC).isoformat(),
        "status": "ready_for_external_deposit",
        "release_version": version,
        "git_commit": manifest.get("git_commit"),
        "archive": archive_path.name,
        "archive_bytes": archive_path.stat().st_size,
        "archive_sha256": _sha256(archive_path),
        "archive_file_count": len(files),
        "source_manifest": str(manifest_path),
        "source_manifest_sha256": _sha256(manifest_path),
        "identifier_safety": manifest["identifier_safety"],
        "doi": None,
        "claim_boundary": (
            "Archive readiness does not indicate DOI registration, repository deposit, "
            "biological approval, or manuscript submission readiness."
        ),
    }
    deposit_path = root / f"canceromicslake-derived-data-v{version}.deposit.json"
    deposit_path.write_text(json.dumps(deposit, indent=2), encoding="utf-8")
    return {**deposit, "archive_path": str(archive_path), "deposit_path": str(deposit_path)}
