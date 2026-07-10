from __future__ import annotations

from datetime import UTC, datetime
import gzip
import hashlib
import json
from pathlib import Path
import re
import time
from typing import Any
from urllib.request import Request, urlopen

import polars as pl


RECOUNT3_BASE_URL = "https://recount-opendata.s3.amazonaws.com/recount3/release"
ANNOTATION = "G026"
TARGET_LIBRARY_SIZE = 40_000_000.0
EXTERNAL_ANNOTATION = "recount3_monorail_gencode_v26_auc_40m"

COHORTS = (
    {"source": "TCGA", "project": "BRCA", "project_id": "TCGA-BRCA", "tissues": ()},
    {"source": "TCGA", "project": "LUAD", "project_id": "TCGA-LUAD", "tissues": ()},
    {"source": "TCGA", "project": "COAD", "project_id": "TCGA-COAD", "tissues": ()},
    {
        "source": "GTEx",
        "project": "BREAST",
        "project_id": "",
        "tissues": ("Breast - Mammary Tissue",),
    },
    {"source": "GTEx", "project": "LUNG", "project_id": "", "tissues": ("Lung",)},
    {
        "source": "GTEx",
        "project": "COLON",
        "project_id": "",
        "tissues": ("Colon - Transverse", "Colon - Sigmoid"),
    },
)

OUTPUT_SCHEMA = {
    "source": pl.Utf8,
    "project_id": pl.Utf8,
    "sample_id": pl.Utf8,
    "sample_type": pl.Utf8,
    "tissue_site": pl.Utf8,
    "gene_id": pl.Utf8,
    "gene_symbol": pl.Utf8,
    "expression_value": pl.Float64,
    "expression_unit": pl.Utf8,
    "external_annotation": pl.Utf8,
}


def _cohort_urls(cohort: dict[str, object], base_url: str) -> dict[str, str]:
    source = str(cohort["source"])
    project = str(cohort["project"])
    prefix = "tcga" if source == "TCGA" else "gtex"
    suffix = project[-2:]
    root = f"{base_url.rstrip('/')}/human/data_sources/{prefix}"
    return {
        "counts": f"{root}/gene_sums/{suffix}/{project}/{prefix}.gene_sums.{project}.{ANNOTATION}.gz",
        "metadata": f"{root}/metadata/{suffix}/{project}/{prefix}.{prefix}.{project}.MD.gz",
        "qc": f"{root}/metadata/{suffix}/{project}/{prefix}.recount_qc.{project}.MD.gz",
    }


def _annotation_url(base_url: str) -> str:
    return (
        f"{base_url.rstrip('/')}/human/annotations/gene_sums/"
        f"human.gene_sums.{ANNOTATION}.gtf.gz"
    )


def _remote_size(url: str, timeout_sec: int) -> int:
    with urlopen(Request(url, method="HEAD"), timeout=timeout_sec) as response:
        return int(response.headers.get("content-length", "0") or 0)


def _download(url: str, destination: Path, timeout_sec: int) -> tuple[str, int]:
    destination.parent.mkdir(parents=True, exist_ok=True)
    expected_size = _remote_size(url, timeout_sec)
    if destination.exists() and (expected_size == 0 or destination.stat().st_size == expected_size):
        return "skipped_existing", destination.stat().st_size

    partial = destination.with_suffix(destination.suffix + ".part")
    existing = partial.stat().st_size if partial.exists() else 0
    headers = {"Range": f"bytes={existing}-"} if existing else {}
    with urlopen(Request(url, headers=headers), timeout=timeout_sec) as response:
        append = existing > 0 and getattr(response, "status", 200) == 206
        with partial.open("ab" if append else "wb") as stream:
            for chunk in iter(lambda: response.read(1024 * 1024), b""):
                stream.write(chunk)
    if expected_size and partial.stat().st_size != expected_size:
        raise ValueError(
            f"recount3 download size mismatch for {destination.name}: "
            f"expected {expected_size}, got {partial.stat().st_size}"
        )
    partial.replace(destination)
    return "downloaded", destination.stat().st_size


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _parse_gene_annotation(path: Path) -> pl.DataFrame:
    pattern = re.compile(r'(gene_id|gene_name) "([^"]+)"')
    rows: list[dict[str, str]] = []
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        for line in stream:
            if line.startswith("#"):
                continue
            fields = line.rstrip("\n").split("\t")
            if len(fields) < 9 or fields[2] != "gene":
                continue
            attributes = dict(pattern.findall(fields[8]))
            gene_id = attributes.get("gene_id", "")
            gene_symbol = attributes.get("gene_name", "")
            if gene_id and gene_symbol:
                rows.append({"raw_gene_id": gene_id, "gene_symbol": gene_symbol.upper()})
    if not rows:
        raise ValueError(f"No gene annotations parsed from {path}")
    return pl.DataFrame(rows).unique("raw_gene_id", keep="first")


def _read_selected_samples(
    cohort: dict[str, object],
    metadata_path: Path,
    qc_path: Path,
    sample_cap: int,
) -> pl.DataFrame:
    source = str(cohort["source"])
    if source == "TCGA":
        metadata = pl.read_csv(
            metadata_path,
            separator="\t",
            columns=["external_id", "cgc_sample_sample_type"],
            infer_schema_length=0,
        ).rename({"cgc_sample_sample_type": "sample_type"})
        metadata = metadata.filter(pl.col("sample_type") == "Primary Tumor").with_columns(
            [
                pl.lit("").alias("tissue_site"),
                pl.lit(str(cohort["project_id"])).alias("project_id"),
            ]
        )
    else:
        metadata = pl.read_csv(
            metadata_path,
            separator="\t",
            columns=["external_id", "SMTSD"],
            infer_schema_length=0,
        ).rename({"SMTSD": "tissue_site"})
        metadata = metadata.filter(pl.col("tissue_site").is_in(list(cohort["tissues"]))).with_columns(
            [pl.lit("Normal").alias("sample_type"), pl.lit("").alias("project_id")]
        )

    qc = pl.read_csv(
        qc_path,
        separator="\t",
        columns=["external_id", "bc_auc.all_reads_all_bases"],
        infer_schema_length=0,
    ).with_columns(
        pl.col("bc_auc.all_reads_all_bases")
        .cast(pl.Float64, strict=False)
        .alias("auc")
    )
    return (
        metadata.join(qc.select(["external_id", "auc"]), on="external_id", how="inner")
        .filter(pl.col("auc").is_not_null() & (pl.col("auc") > 0))
        .unique("external_id", keep="first")
        .sort("external_id")
        .head(sample_cap)
    )


def _harmonize_cohort(
    cohort: dict[str, object],
    counts_path: Path,
    selected: pl.DataFrame,
    annotation: pl.DataFrame,
) -> pl.DataFrame:
    sample_ids = selected.get_column("external_id").to_list()
    if not sample_ids:
        return pl.DataFrame(schema=OUTPUT_SCHEMA)
    counts = pl.read_csv(
        counts_path,
        separator="\t",
        skip_rows=2,
        columns=["gene_id", *sample_ids],
        infer_schema_length=100,
    ).rename({"gene_id": "raw_gene_id"})
    long = counts.unpivot(
        index="raw_gene_id",
        on=sample_ids,
        variable_name="sample_id",
        value_name="raw_coverage_count",
    )
    sample_context = selected.rename({"external_id": "sample_id"}).with_columns(
        (pl.lit(TARGET_LIBRARY_SIZE) / pl.col("auc")).alias("scale_factor")
    )
    return (
        long.join(sample_context, on="sample_id", how="inner")
        .join(annotation, on="raw_gene_id", how="inner")
        .with_columns(
            [
                pl.lit(str(cohort["source"])).alias("source"),
                pl.col("raw_gene_id").str.replace(r"\..*$", "").alias("gene_id"),
                (
                    pl.col("raw_coverage_count").cast(pl.Float64, strict=False)
                    * pl.col("scale_factor")
                ).alias("expression_value"),
                pl.lit("AUC-scaled coverage count (40M target)").alias("expression_unit"),
                pl.lit(EXTERNAL_ANNOTATION).alias("external_annotation"),
            ]
        )
        .select([pl.col(column).cast(dtype, strict=False) for column, dtype in OUTPUT_SCHEMA.items()])
        .filter(pl.col("expression_value").is_not_null() & (pl.col("expression_value") >= 0))
    )


def build_recount3_expression_extract(
    bronze_dir: str | Path = "data/bronze/recount3",
    output_path: str | Path = "data/silver/silver_expression_recount3.parquet",
    report_path: str | Path = "outputs/reports/recount3_expression_report.json",
    sample_cap_per_cohort: int = 30,
    base_url: str = RECOUNT3_BASE_URL,
    timeout_sec: int = 300,
    run_mode: str = "manual",
) -> dict[str, Any]:
    if sample_cap_per_cohort < 1:
        raise ValueError("sample_cap_per_cohort must be positive")
    started = time.monotonic()
    bronze = Path(bronze_dir)
    output = Path(output_path)
    report = Path(report_path)
    parts_dir = output.parent / "recount3_expression_parts"
    output.parent.mkdir(parents=True, exist_ok=True)
    report.parent.mkdir(parents=True, exist_ok=True)
    parts_dir.mkdir(parents=True, exist_ok=True)

    downloads: list[dict[str, object]] = []
    annotation_path = bronze / f"human.gene_sums.{ANNOTATION}.gtf.gz"
    status, size = _download(_annotation_url(base_url), annotation_path, timeout_sec)
    downloads.append(
        {
            "kind": "annotation",
            "url": _annotation_url(base_url),
            "path": str(annotation_path),
            "status": status,
            "bytes": size,
            "sha256": _sha256(annotation_path),
        }
    )
    annotation = _parse_gene_annotation(annotation_path)

    cohort_reports: list[dict[str, object]] = []
    part_paths: list[Path] = []
    for cohort in COHORTS:
        source = str(cohort["source"])
        project = str(cohort["project"])
        prefix = source.lower()
        urls = _cohort_urls(cohort, base_url)
        local_paths: dict[str, Path] = {}
        for kind, url in urls.items():
            destination = bronze / prefix / project / Path(url).name
            download_status, file_size = _download(url, destination, timeout_sec)
            downloads.append(
                {
                    "kind": kind,
                    "cohort": f"{source}:{project}",
                    "url": url,
                    "path": str(destination),
                    "status": download_status,
                    "bytes": file_size,
                    "sha256": _sha256(destination),
                }
            )
            local_paths[kind] = destination

        selected = _read_selected_samples(
            cohort,
            local_paths["metadata"],
            local_paths["qc"],
            sample_cap_per_cohort,
        )
        harmonized = _harmonize_cohort(cohort, local_paths["counts"], selected, annotation)
        part_path = parts_dir / f"{prefix}_{project.lower()}.parquet"
        harmonized.write_parquet(part_path, compression="zstd")
        part_paths.append(part_path)
        cohort_reports.append(
            {
                "source": source,
                "project": project,
                "project_id": str(cohort["project_id"]),
                "selected_samples": selected.height,
                "row_count": harmonized.height,
                "tissues": list(cohort["tissues"]),
                "part_path": str(part_path),
            }
        )

    pl.concat([pl.scan_parquet(path) for path in part_paths], how="vertical_relaxed").sink_parquet(
        output,
        compression="zstd",
    )
    row_count = int(pl.scan_parquet(output).select(pl.len()).collect().item())
    summary: dict[str, Any] = {
        "pipeline_run_id": datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ"),
        "run_mode": run_mode,
        "status": "completed",
        "source": "recount3 public S3 release",
        "base_url": base_url,
        "annotation": ANNOTATION,
        "normalization": "raw_coverage_count * (40000000 / bc_auc.all_reads_all_bases)",
        "sample_cap_per_cohort": sample_cap_per_cohort,
        "cohort_count": len(cohort_reports),
        "selected_sample_count": sum(int(row["selected_samples"]) for row in cohort_reports),
        "row_count": row_count,
        "output_path": str(output),
        "output_bytes": output.stat().st_size,
        "cohorts": cohort_reports,
        "downloads": downloads,
        "elapsed_seconds": round(time.monotonic() - started, 3),
    }
    report.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary
