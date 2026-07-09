from __future__ import annotations

from pathlib import Path

import polars as pl


DEFAULT_COLUMNS = {
    "cancer_type": pl.Utf8,
    "gene_symbol": pl.Utf8,
    "mutation_frequency": pl.Float64,
    "mutated_sample_count": pl.Int64,
    "total_profiled_sample_count": pl.Int64,
    "abs_log2_fold_change": pl.Float64,
    "log2_fold_change": pl.Float64,
    "graph_degree": pl.Int64,
    "evidence_count": pl.Int64,
    "priority_score": pl.Float64,
    "priority_tier": pl.Utf8,
    "evidence_summary": pl.Utf8,
}


def _empty_candidate_priority() -> pl.DataFrame:
    return pl.DataFrame(schema=DEFAULT_COLUMNS)


def _load_candidate_priority(gold_path: str | Path) -> pl.DataFrame:
    path = Path(gold_path)
    if not path.exists():
        return _empty_candidate_priority()
    df = pl.read_parquet(path)
    missing = [column for column in DEFAULT_COLUMNS if column not in df.columns]
    if missing:
        return _empty_candidate_priority()
    return df.select(list(DEFAULT_COLUMNS))


def candidate_gene_priority(
    cancer_type: str | None = None,
    gene_query: str | None = None,
    tier: str | None = None,
    min_priority_score: float | None = None,
    limit: int = 50,
    gold_path: str | Path = "data/gold/gold_candidate_gene_priority.parquet",
) -> dict[str, object]:
    df = _load_candidate_priority(gold_path)
    if df.is_empty():
        return {
            "filters": {
                "cancer_type": cancer_type,
                "gene_query": gene_query,
                "tier": tier,
                "min_priority_score": min_priority_score,
                "limit": limit,
            },
            "rows": [],
            "row_count": 0,
            "warning": "Candidate priority mart is unavailable. Run `make run-gold` first.",
        }

    filtered = df
    if cancer_type:
        filtered = filtered.filter(pl.col("cancer_type") == cancer_type)
    if gene_query:
        q = gene_query.upper()
        filtered = filtered.filter(pl.col("gene_symbol").cast(pl.Utf8).str.to_uppercase().str.contains(q))
    if tier:
        filtered = filtered.filter(pl.col("priority_tier").cast(pl.Utf8).str.to_lowercase() == tier.lower())
    if min_priority_score is not None:
        filtered = filtered.filter(pl.col("priority_score") >= float(min_priority_score))

    filtered = filtered.sort(
        ["priority_score", "evidence_count", "mutation_frequency", "abs_log2_fold_change"],
        descending=[True, True, True, True],
    )
    capped = filtered.head(max(int(limit), 0))
    return {
        "filters": {
            "cancer_type": cancer_type,
            "gene_query": gene_query,
            "tier": tier,
            "min_priority_score": min_priority_score,
            "limit": limit,
        },
        "rows": capped.to_dicts(),
        "row_count": capped.height,
        "total_matching_rows": filtered.height,
        "warning": "Exploratory prioritization only; scores are not clinically validated.",
    }


def candidate_priority_dataframe(
    cancer_type: str | None = None,
    gene_query: str | None = None,
    tier: str | None = None,
    min_priority_score: float | None = None,
    limit: int = 50,
    gold_path: str | Path = "data/gold/gold_candidate_gene_priority.parquet",
) -> pl.DataFrame:
    payload = candidate_gene_priority(
        cancer_type=cancer_type,
        gene_query=gene_query,
        tier=tier,
        min_priority_score=min_priority_score,
        limit=limit,
        gold_path=gold_path,
    )
    rows = payload.get("rows", [])
    return pl.DataFrame(rows) if rows else _empty_candidate_priority()
