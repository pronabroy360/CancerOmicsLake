from __future__ import annotations

import gzip
from pathlib import Path

import polars as pl

from src.common.config import AppConfig
from src.processing.expression_loaders import _resolve_column
from src.processing.mutation_consequences import classify_variant_consequence
from src.processing.normalize_gene_ids import normalize_gene_id


def _safe_read_table(path: Path) -> pl.DataFrame:
    suffixes = {s.lower() for s in path.suffixes}
    is_tabular = bool({".maf", ".tsv", ".txt"} & suffixes)
    separator = "\t" if is_tabular else ","

    read_kwargs = {
        "separator": separator,
        "infer_schema_length": 10000,
        "comment_prefix": "#",
        "truncate_ragged_lines": True,
        "ignore_errors": True,
    }
    if ".gz" in suffixes:
        with gzip.open(path, mode="rt", encoding="utf-8", errors="ignore") as fh:
            return pl.read_csv(fh, **read_kwargs)
    return pl.read_csv(path, **read_kwargs)


def _empty_mutation_df() -> pl.DataFrame:
    return pl.DataFrame(
        schema={
            "project_id": pl.Utf8,
            "case_id": pl.Utf8,
            "sample_id": pl.Utf8,
            "gene_id": pl.Utf8,
            "gene_symbol": pl.Utf8,
            "variant_classification": pl.Utf8,
            "consequence_group": pl.Utf8,
            "is_protein_altering": pl.Boolean,
            "variant_type": pl.Utf8,
            "chromosome": pl.Utf8,
            "start_position": pl.Int64,
            "end_position": pl.Int64,
            "reference_allele": pl.Utf8,
            "tumor_seq_allele": pl.Utf8,
            "data_origin": pl.Utf8,
            "ingested_at": pl.Utf8,
        }
    )


def _resolve_mutation_files_from_manifest(root: Path, metadata_df: pl.DataFrame) -> list[Path]:
    required = {"file_name", "data_category", "data_type"}
    if not required.issubset(set(metadata_df.columns)):
        return []

    manifest = metadata_df.select(
        [
            pl.col("project_id") if "project_id" in metadata_df.columns else pl.lit(None).alias("project_id"),
            pl.col("file_name").cast(pl.Utf8),
            pl.col("data_category").cast(pl.Utf8),
            pl.col("data_type").cast(pl.Utf8),
            pl.col("access").cast(pl.Utf8) if "access" in metadata_df.columns else pl.lit("open").alias("access"),
        ]
    ).unique(subset=["project_id", "file_name", "data_category", "data_type", "access"])

    mutation_manifest = manifest.filter(
        pl.col("data_category").str.to_lowercase().str.contains("simple nucleotide variation")
        & (
            pl.col("data_type").str.to_lowercase().str.contains("somatic mutation")
            | pl.col("data_type").str.to_lowercase().str.contains("masked somatic mutation")
        )
        & (pl.col("access").str.to_lowercase() == "open")
    )
    if mutation_manifest.is_empty():
        return []

    files: list[Path] = []
    for row in mutation_manifest.iter_rows(named=True):
        file_name = str(row["file_name"])
        project_id = row.get("project_id")
        candidate_paths: list[Path] = []
        if project_id:
            candidate_paths.append(root / str(project_id) / "mutations" / file_name)
            candidate_paths.append(root / str(project_id) / file_name)
        candidate_paths.append(root / "mutations" / file_name)

        resolved = next((p for p in candidate_paths if p.exists()), None)
        if resolved is not None:
            files.append(resolved)

    return sorted(set(files))


def _parse_mutation_file(path: Path, metadata_df: pl.DataFrame) -> pl.DataFrame:
    raw = _safe_read_table(path)
    if raw.is_empty():
        return _empty_mutation_df().head(0)

    sample_col = _resolve_column(raw, ["sample_id", "tumor_sample_barcode", "tumor_sample"])
    gene_id_col = _resolve_column(raw, ["gene_id", "ensembl_gene_id"])
    gene_symbol_col = _resolve_column(raw, ["hugo_symbol", "gene_symbol", "symbol"])
    variant_class_col = _resolve_column(raw, ["variant_classification"])
    variant_type_col = _resolve_column(raw, ["variant_type"])
    chr_col = _resolve_column(raw, ["chromosome", "chr"])
    start_col = _resolve_column(raw, ["start_position", "start_pos", "position"])
    end_col = _resolve_column(raw, ["end_position", "end_pos", "position"])
    ref_col = _resolve_column(raw, ["reference_allele", "ref_allele"])
    alt_col = _resolve_column(raw, ["tumor_seq_allele2", "tumor_seq_allele", "tumor_allele"])
    case_col = _resolve_column(raw, ["case_id"])

    if sample_col is None or gene_symbol_col is None or start_col is None:
        return _empty_mutation_df().head(0)

    base = raw.select(
        [
            pl.col(sample_col).cast(pl.Utf8).alias("sample_id"),
            (
                pl.col(gene_id_col).cast(pl.Utf8)
                if gene_id_col is not None
                else pl.lit("", dtype=pl.Utf8)
            ).alias("gene_id_raw"),
            pl.col(gene_symbol_col).cast(pl.Utf8).fill_null("Unknown").alias("gene_symbol"),
            (
                pl.col(variant_class_col).cast(pl.Utf8)
                if variant_class_col is not None
                else pl.lit("Unknown", dtype=pl.Utf8)
            ).alias("variant_classification"),
            (
                pl.col(variant_type_col).cast(pl.Utf8)
                if variant_type_col is not None
                else pl.lit("Unknown", dtype=pl.Utf8)
            ).alias("variant_type"),
            (
                pl.col(chr_col).cast(pl.Utf8)
                if chr_col is not None
                else pl.lit("Unknown", dtype=pl.Utf8)
            ).alias("chromosome"),
            pl.col(start_col).cast(pl.Int64, strict=False).alias("start_position"),
            (
                pl.col(end_col).cast(pl.Int64, strict=False)
                if end_col is not None
                else pl.col(start_col).cast(pl.Int64, strict=False)
            ).alias("end_position"),
            (
                pl.col(ref_col).cast(pl.Utf8)
                if ref_col is not None
                else pl.lit("Unknown", dtype=pl.Utf8)
            ).alias("reference_allele"),
            (
                pl.col(alt_col).cast(pl.Utf8)
                if alt_col is not None
                else pl.lit("Unknown", dtype=pl.Utf8)
            ).alias("tumor_seq_allele"),
            (
                pl.col(case_col).cast(pl.Utf8)
                if case_col is not None
                else pl.lit(None, dtype=pl.Utf8)
            ).alias("case_id_file"),
        ]
    )

    meta_columns = {"sample_id", "project_id", "case_id"}
    project_id_from_path = "Unknown"
    if len(path.parents) >= 2 and path.parents[1].name.startswith("TCGA-"):
        project_id_from_path = path.parents[1].name
    if meta_columns.issubset(set(metadata_df.columns)):
        sample_map = metadata_df.select(
            [
                pl.col("sample_id"),
                pl.col("project_id").alias("project_id_meta"),
                pl.col("case_id").alias("case_id_meta"),
            ]
        ).unique(subset=["sample_id"])
        case_map = metadata_df.select(
            [
                pl.col("case_id").alias("case_id_file"),
                pl.col("project_id").alias("project_id_case"),
            ]
        ).unique(subset=["case_id_file"])
        base = (
            base.join(sample_map, on="sample_id", how="left")
            .join(case_map, on="case_id_file", how="left")
            .with_columns(
                [
                    pl.coalesce(
                        [
                            pl.col("project_id_meta"),
                            pl.col("project_id_case"),
                            pl.lit(project_id_from_path),
                        ]
                    ).alias("project_id"),
                    pl.coalesce([pl.col("case_id_meta"), pl.col("case_id_file")]).alias("case_id"),
                ]
            )
        )
    else:
        base = base.with_columns(
            [
                pl.lit(project_id_from_path).alias("project_id"),
                pl.col("case_id_file").fill_null("Unknown").alias("case_id"),
            ]
        )

    normalized_gene = [
        normalize_gene_id(str(v))["gene_id_normalized"] if v is not None else ""
        for v in base.get_column("gene_id_raw").to_list()
    ]
    consequence_labels: list[str] = []
    protein_altering_flags: list[bool] = []
    for value in base.get_column("variant_classification").to_list():
        consequence_group, is_protein_altering = classify_variant_consequence(value)
        consequence_labels.append(consequence_group)
        protein_altering_flags.append(is_protein_altering)

    base = base.with_columns(
        [
            pl.Series(name="gene_id", values=normalized_gene),
            pl.Series(name="consequence_group", values=consequence_labels, dtype=pl.Utf8),
            pl.Series(name="is_protein_altering", values=protein_altering_flags, dtype=pl.Boolean),
        ]
    )

    return base.select(
        [
            pl.col("project_id").fill_null("Unknown"),
            pl.col("case_id").fill_null("Unknown"),
            pl.col("sample_id").fill_null("Unknown"),
            pl.col("gene_id").fill_null(""),
            pl.col("gene_symbol").fill_null("Unknown"),
            pl.col("variant_classification").fill_null("Unknown"),
            pl.col("consequence_group"),
            pl.col("is_protein_altering"),
            pl.col("variant_type").fill_null("Unknown"),
            pl.col("chromosome").fill_null("Unknown"),
            pl.col("start_position").cast(pl.Int64, strict=False),
            pl.col("end_position").cast(pl.Int64, strict=False),
            pl.col("reference_allele").fill_null("Unknown"),
            pl.col("tumor_seq_allele").fill_null("Unknown"),
            pl.lit(str(path)).alias("data_origin"),
        ]
    )


def load_tcga_mutation_table(
    config: AppConfig | None,
    ingest_time: str,
    metadata_df: pl.DataFrame,
    tcga_root_dir: str | Path = "data/bronze/tcga",
) -> pl.DataFrame:
    empty = _empty_mutation_df().with_columns(pl.lit(ingest_time).alias("ingested_at")).head(0)
    if config is None:
        return empty

    root = Path(tcga_root_dir)
    if not root.exists():
        return empty

    files = _resolve_mutation_files_from_manifest(root=root, metadata_df=metadata_df)
    if not files:
        files = sorted(root.glob("**/mutations/*.*"))

    frames: list[pl.DataFrame] = []
    for file_path in files:
        suffixes = {s.lower() for s in file_path.suffixes}
        if not suffixes.intersection({".maf", ".tsv", ".txt", ".csv"}):
            continue
        parsed = _parse_mutation_file(file_path, metadata_df)
        if not parsed.is_empty():
            frames.append(parsed)

    if not frames:
        return empty

    return pl.concat(frames, how="vertical").with_columns(pl.lit(ingest_time).alias("ingested_at"))


def build_mutation_profile_table(
    metadata_df: pl.DataFrame,
    ingest_time: str,
    tcga_root_dir: str | Path = "data/bronze/tcga",
) -> pl.DataFrame:
    schema = {
        "project_id": pl.Utf8,
        "case_id": pl.Utf8,
        "sample_id": pl.Utf8,
        "file_id": pl.Utf8,
        "file_name": pl.Utf8,
        "file_size": pl.Int64,
        "md5sum": pl.Utf8,
        "data_origin": pl.Utf8,
        "profile_status": pl.Utf8,
        "ingested_at": pl.Utf8,
    }
    root = Path(tcga_root_dir)
    required = {
        "project_id",
        "case_id",
        "sample_id",
        "file_id",
        "file_name",
        "data_category",
        "data_type",
    }
    if not root.exists() or not required.issubset(metadata_df.columns):
        return pl.DataFrame(schema=schema)

    mutation_manifest = metadata_df.filter(
        pl.col("data_category").cast(pl.Utf8).str.to_lowercase().str.contains("simple nucleotide variation")
        & pl.col("data_type").cast(pl.Utf8).str.to_lowercase().str.contains("somatic mutation")
        & (
            (pl.col("access").cast(pl.Utf8).str.to_lowercase() == "open")
            if "access" in metadata_df.columns
            else pl.lit(True)
        )
    )

    rows: list[dict[str, object]] = []
    for row in mutation_manifest.iter_rows(named=True):
        project_id = str(row.get("project_id") or "")
        file_name = str(row.get("file_name") or "")
        candidates = [
            root / project_id / "mutations" / file_name,
            root / project_id / file_name,
            root / "mutations" / file_name,
        ]
        source_path = next((path for path in candidates if path.is_file()), None)
        if source_path is None:
            continue
        rows.append(
            {
                "project_id": project_id,
                "case_id": str(row.get("case_id") or "Unknown"),
                "sample_id": str(row.get("sample_id") or "Unknown"),
                "file_id": str(row.get("file_id") or ""),
                "file_name": file_name,
                "file_size": row.get("file_size"),
                "md5sum": str(row.get("md5sum") or ""),
                "data_origin": str(source_path),
                "profile_status": "downloaded",
                "ingested_at": ingest_time,
            }
        )

    if not rows:
        return pl.DataFrame(schema=schema)
    return (
        pl.DataFrame(rows)
        .cast(schema, strict=False)
        .unique(subset=["project_id", "file_id", "sample_id"], keep="first")
        .sort(["project_id", "sample_id", "file_id"])
    )
