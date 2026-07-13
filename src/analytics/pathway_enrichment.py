from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path
import re
import time

import numpy as np
import polars as pl
from scipy.stats import hypergeom

from src.analytics.expression_statistics import _benjamini_hochberg


PATHWAY_ENRICHMENT_SCHEMA = {
    "cancer_type": pl.Utf8,
    "candidate_set": pl.Utf8,
    "pathway_id": pl.Utf8,
    "pathway_name": pl.Utf8,
    "pathway_source": pl.Utf8,
    "background_gene_count": pl.Int64,
    "candidate_gene_count": pl.Int64,
    "pathway_gene_count": pl.Int64,
    "overlap_gene_count": pl.Int64,
    "overlap_genes": pl.Utf8,
    "enrichment_ratio": pl.Float64,
    "odds_ratio": pl.Float64,
    "p_value": pl.Float64,
    "fdr_q_value": pl.Float64,
    "enrichment_score": pl.Float64,
    "enrichment_tier": pl.Utf8,
    "pathway_caveat": pl.Utf8,
}

DEFAULT_CANDIDATE_SETS = {
    "prioritized": {"consensus_decision": {"prioritized"}},
    "watchlist_plus_prioritized": {"consensus_decision": {"prioritized", "watchlist"}},
    "research_candidate_plus": {"publication_tier": {"strong_candidate", "research_candidate"}},
}

MIN_PATHWAY_SIZE = 5
MAX_PATHWAY_SIZE = 500
MIN_OVERLAP = 2
FDR_THRESHOLD = 0.05


def _empty_pathway_enrichment() -> pl.DataFrame:
    return pl.DataFrame(schema=PATHWAY_ENRICHMENT_SCHEMA)


def _pathway_id(name: str, description: str) -> str:
    for value in (name, description):
        match = re.search(r"R-HSA-\d+", value)
        if match:
            return match.group(0)
    return re.sub(r"[^A-Za-z0-9_]+", "_", name).strip("_").upper()[:96] or "UNKNOWN_PATHWAY"


def load_gmt_pathways(path: str | Path, source: str = "Reactome") -> list[dict[str, object]]:
    gmt = Path(path)
    if not gmt.exists():
        return []
    pathways: list[dict[str, object]] = []
    for line in gmt.read_text(encoding="utf-8").splitlines():
        parts = [part.strip() for part in line.split("\t")]
        if len(parts) < 3 or not parts[0]:
            continue
        name, description, *genes = parts
        normalized = sorted({gene.upper() for gene in genes if gene.strip()})
        if normalized:
            pathways.append(
                {
                    "pathway_id": _pathway_id(name, description),
                    "pathway_name": name,
                    "pathway_source": source,
                    "genes": normalized,
                }
            )
    return pathways


def _candidate_genes(consensus: pl.DataFrame, cancer_type: str, candidate_set: str) -> set[str]:
    subset = consensus.filter(pl.col("cancer_type") == cancer_type)
    rules = DEFAULT_CANDIDATE_SETS[candidate_set]
    if "consensus_decision" in rules:
        subset = subset.filter(pl.col("consensus_decision").is_in(sorted(rules["consensus_decision"])))
    if "publication_tier" in rules:
        subset = subset.filter(pl.col("publication_tier").is_in(sorted(rules["publication_tier"])))
    return {str(value).upper() for value in subset.get_column("gene_symbol").drop_nulls().unique().to_list()}


def _odds_ratio(k: int, n: int, pathway_size: int, background_size: int) -> float:
    a = float(k)
    b = float(pathway_size - k)
    c = float(n - k)
    d = float(background_size - pathway_size - n + k)
    if b <= 0 or c <= 0:
        return float("inf") if a > 0 and d >= 0 else 0.0
    return (a * d) / (b * c)


def _enrichment_rows(
    consensus: pl.DataFrame,
    pathways: list[dict[str, object]],
    *,
    min_pathway_size: int,
    max_pathway_size: int,
    min_overlap: int,
) -> pl.DataFrame:
    rows: list[dict[str, object]] = []
    cancer_types = sorted({str(v) for v in consensus.get_column("cancer_type").drop_nulls().unique().to_list()})
    for cancer_type in cancer_types:
        background = {
            str(value).upper()
            for value in consensus.filter(pl.col("cancer_type") == cancer_type)
            .get_column("gene_symbol")
            .drop_nulls()
            .unique()
            .to_list()
        }
        background_size = len(background)
        if background_size == 0:
            continue
        for candidate_set in DEFAULT_CANDIDATE_SETS:
            candidates = _candidate_genes(consensus, cancer_type, candidate_set)
            candidate_size = len(candidates)
            if candidate_size == 0:
                continue
            for pathway in pathways:
                pathway_genes = set(pathway["genes"]) & background
                pathway_size = len(pathway_genes)
                if pathway_size < min_pathway_size or pathway_size > max_pathway_size:
                    continue
                overlap = sorted(candidates & pathway_genes)
                overlap_count = len(overlap)
                if overlap_count < min_overlap:
                    continue
                expected = (candidate_size * pathway_size) / background_size
                p_value = max(float(hypergeom.sf(overlap_count - 1, background_size, pathway_size, candidate_size)), 1e-300)
                rows.append(
                    {
                        "cancer_type": cancer_type,
                        "candidate_set": candidate_set,
                        "pathway_id": str(pathway["pathway_id"]),
                        "pathway_name": str(pathway["pathway_name"]),
                        "pathway_source": str(pathway["pathway_source"]),
                        "background_gene_count": background_size,
                        "candidate_gene_count": candidate_size,
                        "pathway_gene_count": pathway_size,
                        "overlap_gene_count": overlap_count,
                        "overlap_genes": ",".join(overlap),
                        "enrichment_ratio": float(overlap_count / expected) if expected > 0 else 0.0,
                        "odds_ratio": _odds_ratio(overlap_count, candidate_size, pathway_size, background_size),
                        "p_value": p_value,
                    }
                )
    if not rows:
        return _empty_pathway_enrichment()
    result = pl.DataFrame(rows)
    adjusted_parts = []
    for _, group in result.group_by(["cancer_type", "candidate_set"], maintain_order=True):
        q_values = _benjamini_hochberg(group.get_column("p_value").to_numpy())
        adjusted_parts.append(group.with_columns(pl.Series("fdr_q_value", q_values)))
    adjusted = pl.concat(adjusted_parts, how="vertical")
    q_score = (-pl.col("fdr_q_value").clip(1e-300, 1.0).log10() / 10.0).clip(0.0, 1.0)
    overlap_score = (pl.col("overlap_gene_count") / 10.0).clip(0.0, 1.0)
    ratio_score = (pl.col("enrichment_ratio") / 5.0).clip(0.0, 1.0)
    return (
        adjusted.with_columns(
            [
                ((q_score * 0.55) + (overlap_score * 0.25) + (ratio_score * 0.20))
                .clip(0.0, 1.0)
                .round(6)
                .alias("enrichment_score"),
                pl.when((pl.col("fdr_q_value") <= FDR_THRESHOLD) & (pl.col("overlap_gene_count") >= 3))
                .then(pl.lit("fdr_enriched"))
                .when(pl.col("p_value") <= 0.05)
                .then(pl.lit("nominal"))
                .otherwise(pl.lit("limited"))
                .alias("enrichment_tier"),
                pl.lit(
                    "Pathway enrichment is hypothesis generation over selected candidate genes; it depends on the tested background and does not establish mechanism or clinical actionability."
                ).alias("pathway_caveat"),
            ]
        )
        .select(list(PATHWAY_ENRICHMENT_SCHEMA))
        .sort(["enrichment_score", "fdr_q_value", "overlap_gene_count"], descending=[True, False, True])
    )


def build_pathway_enrichment(
    consensus_path: str | Path = "data/gold/gold_consensus_candidate_genes.parquet",
    pathway_gmt_path: str | Path = "data/bronze/reference/pathways/reactome_pathways.gmt",
    output_path: str | Path = "data/gold/gold_pathway_enrichment.parquet",
    report_path: str | Path = "outputs/reports/pathway_enrichment_report.json",
    pathway_source: str = "Reactome",
    min_pathway_size: int = MIN_PATHWAY_SIZE,
    max_pathway_size: int = MAX_PATHWAY_SIZE,
    min_overlap: int = MIN_OVERLAP,
) -> dict[str, object]:
    started = time.monotonic()
    output = Path(output_path)
    report = Path(report_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    report.parent.mkdir(parents=True, exist_ok=True)
    consensus_file = Path(consensus_path)
    pathways = load_gmt_pathways(pathway_gmt_path, source=pathway_source)
    consensus = pl.read_parquet(consensus_file) if consensus_file.exists() else pl.DataFrame()
    if consensus.is_empty() or not pathways:
        result = _empty_pathway_enrichment()
        status = "skipped_missing_inputs"
    else:
        result = _enrichment_rows(
            consensus,
            pathways,
            min_pathway_size=min_pathway_size,
            max_pathway_size=max_pathway_size,
            min_overlap=min_overlap,
        )
        status = "completed" if not result.is_empty() else "completed_no_enrichment"
    result.write_parquet(output)
    tier_counts = (
        result.group_by("enrichment_tier").len().sort("enrichment_tier").to_dicts() if not result.is_empty() else []
    )
    summary = {
        "status": status,
        "generated_at": datetime.now(UTC).isoformat(),
        "path": str(output),
        "consensus_path": str(consensus_file),
        "pathway_gmt_path": str(pathway_gmt_path),
        "pathway_source": pathway_source,
        "pathway_count": len(pathways),
        "row_count": int(result.height),
        "candidate_sets": sorted(DEFAULT_CANDIDATE_SETS),
        "min_pathway_size": int(min_pathway_size),
        "max_pathway_size": int(max_pathway_size),
        "min_overlap": int(min_overlap),
        "fdr_method": "Benjamini-Hochberg within cancer type and candidate set",
        "tier_counts": tier_counts,
        "elapsed_seconds": round(time.monotonic() - started, 3),
    }
    report.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def pathway_enrichment(
    cancer_type: str | None = None,
    candidate_set: str | None = None,
    pathway_query: str | None = None,
    enrichment_tier: str | None = None,
    max_fdr: float | None = None,
    min_overlap: int | None = None,
    limit: int = 50,
    gold_path: str | Path = "data/gold/gold_pathway_enrichment.parquet",
) -> dict[str, object]:
    path = Path(gold_path)
    df = pl.read_parquet(path) if path.exists() else _empty_pathway_enrichment()
    filtered = df if set(PATHWAY_ENRICHMENT_SCHEMA).issubset(df.columns) else _empty_pathway_enrichment()
    if cancer_type:
        filtered = filtered.filter(pl.col("cancer_type") == cancer_type)
    if candidate_set:
        filtered = filtered.filter(pl.col("candidate_set") == candidate_set)
    if pathway_query:
        query = pathway_query.upper()
        filtered = filtered.filter(
            pl.col("pathway_name").str.to_uppercase().str.contains(query, literal=True)
            | pl.col("pathway_id").str.to_uppercase().str.contains(query, literal=True)
        )
    if enrichment_tier:
        filtered = filtered.filter(pl.col("enrichment_tier") == enrichment_tier.lower())
    if max_fdr is not None:
        filtered = filtered.filter(pl.col("fdr_q_value") <= float(max_fdr))
    if min_overlap is not None:
        filtered = filtered.filter(pl.col("overlap_gene_count") >= int(min_overlap))
    filtered = filtered.sort(["enrichment_score", "fdr_q_value"], descending=[True, False])
    capped = filtered.head(max(int(limit), 0))
    return {
        "filters": {
            "cancer_type": cancer_type,
            "candidate_set": candidate_set,
            "pathway_query": pathway_query,
            "enrichment_tier": enrichment_tier,
            "max_fdr": max_fdr,
            "min_overlap": min_overlap,
            "limit": limit,
        },
        "row_count": capped.height,
        "total_matching_rows": filtered.height,
        "warning": (
            "Pathway enrichment is for hypothesis generation over candidate sets; it is not mechanistic proof, "
            "clinical validation, or causal inference."
        ),
        "rows": capped.to_dicts(),
    }
