from __future__ import annotations

from pathlib import Path

import polars as pl

from src.analytics.pathway_enrichment import PATHWAY_ENRICHMENT_SCHEMA, load_gmt_pathways


DEFAULT_MAX_PATHWAYS_PER_CANCER = 50
DEFAULT_MAX_FDR = 0.05

PATHWAY_MEMBERSHIP_SCHEMA = {
    "pathway_id": pl.Utf8,
    "pathway_name": pl.Utf8,
    "pathway_source": pl.Utf8,
    "gene_symbol": pl.Utf8,
}


def _empty_enrichment() -> pl.DataFrame:
    return pl.DataFrame(schema=PATHWAY_ENRICHMENT_SCHEMA)


def select_enriched_pathways(
    enrichment_path: str | Path = "data/gold/gold_pathway_enrichment.parquet",
    *,
    max_pathways_per_cancer: int = DEFAULT_MAX_PATHWAYS_PER_CANCER,
    max_fdr: float = DEFAULT_MAX_FDR,
) -> pl.DataFrame:
    if max_pathways_per_cancer < 1:
        raise ValueError("max_pathways_per_cancer must be at least 1")
    if not 0.0 <= max_fdr <= 1.0:
        raise ValueError("max_fdr must be between 0 and 1")

    path = Path(enrichment_path)
    enrichment = pl.read_parquet(path) if path.exists() else _empty_enrichment()
    required = set(PATHWAY_ENRICHMENT_SCHEMA)
    if enrichment.is_empty() or not required.issubset(enrichment.columns):
        return _empty_enrichment()

    selected = (
        enrichment.filter(
            (pl.col("enrichment_tier") == "fdr_enriched")
            & pl.col("fdr_q_value").is_not_null()
            & (pl.col("fdr_q_value") <= max_fdr)
        )
        .sort(
            [
                "cancer_type",
                "fdr_q_value",
                "enrichment_score",
                "overlap_gene_count",
                "pathway_id",
                "candidate_set",
            ],
            descending=[False, False, True, True, False, False],
        )
        .unique(subset=["cancer_type", "pathway_id"], keep="first", maintain_order=True)
        .group_by("cancer_type", maintain_order=True)
        .head(max_pathways_per_cancer)
        .sort(["cancer_type", "fdr_q_value", "pathway_id"])
    )
    return selected.select(list(PATHWAY_ENRICHMENT_SCHEMA))


def selected_pathway_memberships(
    selected_pathways: pl.DataFrame,
    pathway_gmt_path: str | Path = "data/bronze/reference/pathways/reactome_pathways.gmt",
) -> pl.DataFrame:
    if selected_pathways.is_empty() or "pathway_id" not in selected_pathways.columns:
        return pl.DataFrame(schema=PATHWAY_MEMBERSHIP_SCHEMA)

    selected_ids = {
        str(value)
        for value in selected_pathways.get_column("pathway_id").drop_nulls().unique().to_list()
    }
    if not selected_ids:
        return pl.DataFrame(schema=PATHWAY_MEMBERSHIP_SCHEMA)

    rows: list[dict[str, str]] = []
    for pathway in load_gmt_pathways(pathway_gmt_path, source="Reactome"):
        pathway_id = str(pathway["pathway_id"])
        if pathway_id not in selected_ids:
            continue
        for gene_symbol in pathway["genes"]:
            rows.append(
                {
                    "pathway_id": pathway_id,
                    "pathway_name": str(pathway["pathway_name"]),
                    "pathway_source": str(pathway["pathway_source"]),
                    "gene_symbol": str(gene_symbol),
                }
            )

    if not rows:
        return pl.DataFrame(schema=PATHWAY_MEMBERSHIP_SCHEMA)
    return pl.DataFrame(rows, schema=PATHWAY_MEMBERSHIP_SCHEMA).unique(
        subset=["pathway_id", "gene_symbol"], maintain_order=True
    )
