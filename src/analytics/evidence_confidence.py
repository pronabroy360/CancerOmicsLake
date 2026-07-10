from __future__ import annotations

from pathlib import Path

import polars as pl


CONFIDENCE_SCHEMA = {
    "cancer_type": pl.Utf8,
    "gene_symbol": pl.Utf8,
    "priority_score": pl.Float64,
    "priority_tier": pl.Utf8,
    "mutation_frequency": pl.Float64,
    "mutated_sample_count": pl.Int64,
    "total_profiled_sample_count": pl.Int64,
    "log2_fold_change": pl.Float64,
    "abs_log2_fold_change": pl.Float64,
    "sample_count_tumor": pl.Int64,
    "sample_count_normal": pl.Int64,
    "gene_graph_degree": pl.Int64,
    "mutation_evidence": pl.Boolean,
    "expression_evidence": pl.Boolean,
    "mutation_confidence": pl.Float64,
    "expression_confidence": pl.Float64,
    "batch_sensitivity_confidence": pl.Float64,
    "graph_confidence": pl.Float64,
    "quality_confidence": pl.Float64,
    "traceability_confidence": pl.Float64,
    "biological_confidence": pl.Float64,
    "overall_confidence": pl.Float64,
    "confidence_tier": pl.Utf8,
    "raw_expression_direction": pl.Utf8,
    "sensitivity_direction": pl.Utf8,
    "sensitivity_support_tier": pl.Utf8,
    "batch_concordance": pl.Utf8,
    "percentile_delta": pl.Float64,
    "robust_z_delta": pl.Float64,
    "batch_effect_risk": pl.Utf8,
    "quality_status": pl.Utf8,
    "traceability_status": pl.Utf8,
    "caveat_summary": pl.Utf8,
}


def _empty_confidence() -> pl.DataFrame:
    return pl.DataFrame(schema=CONFIDENCE_SCHEMA)


def _read_or_empty(path: Path) -> pl.DataFrame:
    return pl.read_parquet(path) if path.exists() else pl.DataFrame()


def _is_public_provenance() -> pl.Expr:
    origin = pl.col("data_origin").cast(pl.Utf8, strict=False).fill_null("").str.to_lowercase()
    return (~origin.str.contains("stub|placeholder|demo")) & (origin.str.len_chars() > 0)


def _provenance_ratio(df: pl.DataFrame, keys: list[str]) -> pl.DataFrame:
    if df.is_empty() or not set(keys + ["data_origin"]).issubset(df.columns):
        return pl.DataFrame(schema={**{key: pl.Utf8 for key in keys}, "provenance_ratio": pl.Float64})
    return df.group_by(keys).agg(_is_public_provenance().cast(pl.Float64).mean().alias("provenance_ratio"))


def _expression_provenance(
    expression_tcga: pl.DataFrame,
    expression_gtex: pl.DataFrame,
) -> pl.DataFrame:
    tcga = _provenance_ratio(expression_tcga, ["project_id", "gene_symbol"]).rename(
        {"project_id": "cancer_type", "provenance_ratio": "tcga_expression_provenance"}
    )
    if expression_gtex.is_empty():
        return tcga.with_columns(pl.lit(None, dtype=pl.Float64).alias("gtex_expression_provenance"))

    mapping = pl.DataFrame(
        [
            {"cancer_type": "TCGA-BRCA", "tissue_site": "Breast - Mammary Tissue"},
            {"cancer_type": "TCGA-BRCA", "tissue_site": "Breast"},
            {"cancer_type": "TCGA-LUAD", "tissue_site": "Lung"},
            {"cancer_type": "TCGA-COAD", "tissue_site": "Colon - Transverse"},
            {"cancer_type": "TCGA-COAD", "tissue_site": "Colon - Sigmoid"},
            {"cancer_type": "TCGA-COAD", "tissue_site": "Colon"},
        ]
    )
    required = {"tissue_site", "gene_symbol", "data_origin"}
    if not required.issubset(expression_gtex.columns):
        return tcga.with_columns(pl.lit(None, dtype=pl.Float64).alias("gtex_expression_provenance"))
    gtex = (
        expression_gtex.join(mapping, on="tissue_site", how="inner")
        .group_by(["cancer_type", "gene_symbol"])
        .agg(_is_public_provenance().cast(pl.Float64).mean().alias("gtex_expression_provenance"))
    )
    return tcga.join(gtex, on=["cancer_type", "gene_symbol"], how="full", coalesce=True)


def _caveat_summary(row: dict[str, object]) -> str:
    caveats: list[str] = []
    if bool(row["expression_evidence"]):
        caveats.append("cross_study_batch_effect_unadjusted")
        concordance = str(row["batch_concordance"] or "unavailable")
        if concordance == "discordant":
            caveats.append("batch_sensitivity_direction_discordant")
        elif concordance == "inconclusive":
            caveats.append("batch_sensitivity_direction_inconclusive")
        elif concordance == "unavailable":
            caveats.append("batch_sensitivity_unavailable")
        if int(row["sample_count_normal"] or 0) < 30:
            caveats.append("gtex_normal_support_below_30")
        if int(row["sample_count_tumor"] or 0) < 30:
            caveats.append("tcga_tumor_support_below_30")
    if bool(row["mutation_evidence"]) and int(row["total_profiled_sample_count"] or 0) < 100:
        caveats.append("mutation_profiled_support_below_100")
    if int(bool(row["mutation_evidence"])) + int(bool(row["expression_evidence"])) < 2:
        caveats.append("single_biological_modality")
    if float(row["traceability_confidence"] or 0.0) < 1.0:
        caveats.append("source_provenance_incomplete")
    if float(row["graph_confidence"] or 0.0) == 0.0:
        caveats.append("graph_support_absent")
    return ";".join(caveats) if caveats else "none"


def build_evidence_confidence(
    gold_dir: str | Path = "data/gold",
    silver_dir: str | Path = "data/silver",
    output_path: str | Path = "data/gold/gold_cancer_gene_evidence_confidence.parquet",
) -> dict[str, object]:
    gold_root = Path(gold_dir)
    silver_root = Path(silver_dir)
    candidate = _read_or_empty(gold_root / "gold_candidate_gene_priority.parquet")
    if candidate.is_empty():
        result = _empty_confidence()
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        result.write_parquet(out)
        return {"path": str(out), "row_count": 0, "high_confidence_count": 0}

    comparison = _read_or_empty(gold_root / "gold_tumor_vs_normal_expression.parquet")
    batch_sensitivity = _read_or_empty(gold_root / "gold_batch_effect_sensitivity.parquet")
    graph_metrics = _read_or_empty(gold_root / "gold_graph_node_metrics.parquet")
    graph_edges = _read_or_empty(gold_root / "gold_graph_edges.parquet")
    mutations = _read_or_empty(silver_root / "silver_mutations.parquet")
    expression_tcga = _read_or_empty(silver_root / "silver_expression_tcga.parquet")
    expression_gtex = _read_or_empty(silver_root / "silver_expression_gtex.parquet")

    expression_counts = (
        comparison.select(["cancer_type", "gene_symbol", "sample_count_tumor", "sample_count_normal"])
        if not comparison.is_empty()
        else pl.DataFrame(
            schema={
                "cancer_type": pl.Utf8,
                "gene_symbol": pl.Utf8,
                "sample_count_tumor": pl.Int64,
                "sample_count_normal": pl.Int64,
            }
        )
    )
    sensitivity_evidence = (
        batch_sensitivity.select(
            [
                "cancer_type",
                "gene_symbol",
                "sensitivity_direction",
                pl.col("support_tier").alias("sensitivity_support_tier"),
                "percentile_delta",
                "robust_z_delta",
            ]
        )
        if not batch_sensitivity.is_empty()
        and {
            "cancer_type",
            "gene_symbol",
            "sensitivity_direction",
            "support_tier",
            "percentile_delta",
            "robust_z_delta",
        }.issubset(batch_sensitivity.columns)
        else pl.DataFrame(
            schema={
                "cancer_type": pl.Utf8,
                "gene_symbol": pl.Utf8,
                "sensitivity_direction": pl.Utf8,
                "sensitivity_support_tier": pl.Utf8,
                "percentile_delta": pl.Float64,
                "robust_z_delta": pl.Float64,
            }
        )
    )
    gene_metrics = (
        graph_metrics.filter(pl.col("node_label") == "Gene")
        .select(
            [
                pl.col("name").alias("gene_symbol"),
                pl.col("total_degree").cast(pl.Int64).alias("gene_graph_degree"),
            ]
        )
        if not graph_metrics.is_empty() and {"node_label", "name", "total_degree"}.issubset(graph_metrics.columns)
        else pl.DataFrame(schema={"gene_symbol": pl.Utf8, "gene_graph_degree": pl.Int64})
    )
    pair_edges = (
        graph_edges.filter(pl.col("edge_type").is_in(["MUTATED_IN_CANCER", "OVEREXPRESSED_IN"]))
        .select(
            [
                pl.col("source_node_id").str.strip_prefix("GENE:").alias("gene_symbol"),
                pl.col("target_node_id").alias("cancer_type"),
            ]
        )
        .unique()
        .with_columns(pl.lit(True).alias("graph_pair_edge"))
        if not graph_edges.is_empty()
        and {"edge_type", "source_node_id", "target_node_id"}.issubset(graph_edges.columns)
        else pl.DataFrame(schema={"gene_symbol": pl.Utf8, "cancer_type": pl.Utf8, "graph_pair_edge": pl.Boolean})
    )

    mutation_provenance = _provenance_ratio(mutations, ["project_id", "gene_symbol"]).rename(
        {
            "project_id": "cancer_type",
            "provenance_ratio": "mutation_provenance",
        }
    )
    expression_provenance = _expression_provenance(expression_tcga, expression_gtex)

    joined = (
        candidate.join(expression_counts, on=["cancer_type", "gene_symbol"], how="left")
        .join(sensitivity_evidence, on=["cancer_type", "gene_symbol"], how="left")
        .join(gene_metrics, on="gene_symbol", how="left")
        .join(pair_edges, on=["cancer_type", "gene_symbol"], how="left")
        .join(mutation_provenance, on=["cancer_type", "gene_symbol"], how="left")
        .join(expression_provenance, on=["cancer_type", "gene_symbol"], how="left")
        .with_columns(
            [
                pl.col("sample_count_tumor").fill_null(0).cast(pl.Int64),
                pl.col("sample_count_normal").fill_null(0).cast(pl.Int64),
                pl.col("gene_graph_degree").fill_null(0).cast(pl.Int64),
                pl.col("graph_pair_edge").fill_null(False),
                pl.col("sensitivity_direction").fill_null("unavailable"),
                pl.col("sensitivity_support_tier").fill_null("unavailable"),
            ]
        )
        .with_columns(
            [
                (pl.col("mutated_sample_count") > 0).alias("mutation_evidence"),
                ((pl.col("sample_count_tumor") > 0) & (pl.col("sample_count_normal") > 0)).alias(
                    "expression_evidence"
                ),
                pl.when(pl.col("log2_fold_change") >= 1.0)
                .then(pl.lit("raw_up"))
                .when(pl.col("log2_fold_change") <= -1.0)
                .then(pl.lit("raw_down"))
                .otherwise(pl.lit("raw_stable"))
                .alias("raw_expression_direction"),
            ]
        )
        .with_columns(
            pl.when(~pl.col("expression_evidence"))
            .then(pl.lit("not_applicable"))
            .when(pl.col("sensitivity_direction") == "unavailable")
            .then(pl.lit("unavailable"))
            .when(
                ((pl.col("raw_expression_direction") == "raw_up") & (pl.col("sensitivity_direction") == "rank_up"))
                | ((pl.col("raw_expression_direction") == "raw_down") & (pl.col("sensitivity_direction") == "rank_down"))
                | ((pl.col("raw_expression_direction") == "raw_stable") & (pl.col("sensitivity_direction") == "stable"))
            )
            .then(pl.lit("concordant"))
            .when(
                ((pl.col("raw_expression_direction") == "raw_up") & (pl.col("sensitivity_direction") == "rank_down"))
                | ((pl.col("raw_expression_direction") == "raw_down") & (pl.col("sensitivity_direction") == "rank_up"))
            )
            .then(pl.lit("discordant"))
            .otherwise(pl.lit("inconclusive"))
            .alias("batch_concordance")
        )
        .with_columns(
            pl.when(pl.col("batch_concordance") == "concordant")
            .then(
                pl.when(pl.col("sensitivity_support_tier") == "high")
                .then(1.0)
                .when(pl.col("sensitivity_support_tier") == "moderate")
                .then(0.8)
                .otherwise(0.6)
            )
            .when(pl.col("batch_concordance") == "inconclusive")
            .then(
                pl.when(pl.col("sensitivity_support_tier") == "high")
                .then(0.5)
                .when(pl.col("sensitivity_support_tier") == "moderate")
                .then(0.4)
                .otherwise(0.3)
            )
            .otherwise(0.0)
            .alias("batch_sensitivity_confidence")
        )
        .with_columns(
            [
                pl.when(pl.col("mutation_evidence"))
                .then(
                    0.55 * (pl.col("total_profiled_sample_count") / 100.0).clip(0.0, 1.0)
                    + 0.45 * (pl.col("mutated_sample_count") / 20.0).clip(0.0, 1.0)
                )
                .otherwise(0.0)
                .alias("mutation_confidence"),
                pl.when(pl.col("expression_evidence"))
                .then(
                    (
                        0.5 * (pl.col("sample_count_tumor") / 30.0).clip(0.0, 1.0)
                        + 0.5 * (pl.col("sample_count_normal") / 30.0).clip(0.0, 1.0)
                    )
                    * 0.5
                    * (0.5 + 0.5 * pl.col("batch_sensitivity_confidence"))
                )
                .otherwise(0.0)
                .alias("expression_confidence"),
                (
                    pl.col("graph_pair_edge").cast(pl.Float64) * 0.5
                    + (pl.col("gene_graph_degree") / 5.0).clip(0.0, 1.0) * 0.5
                ).alias("graph_confidence"),
                pl.when(
                    (pl.col("mutation_frequency").is_between(0.0, 1.0))
                    & (pl.col("mutated_sample_count") <= pl.col("total_profiled_sample_count"))
                    & (~pl.col("expression_evidence") | ((pl.col("sample_count_tumor") > 0) & (pl.col("sample_count_normal") > 0)))
                )
                .then(1.0)
                .otherwise(0.0)
                .alias("quality_confidence"),
            ]
        )
        .with_columns(
            [
                pl.when(pl.col("mutation_evidence") & pl.col("expression_evidence"))
                .then(
                    (
                        pl.col("mutation_provenance").fill_null(0.0)
                        + (
                            pl.col("tcga_expression_provenance").fill_null(0.0)
                            + pl.col("gtex_expression_provenance").fill_null(0.0)
                        )
                        / 2.0
                    )
                    / 2.0
                )
                .when(pl.col("mutation_evidence"))
                .then(pl.col("mutation_provenance").fill_null(0.0))
                .when(pl.col("expression_evidence"))
                .then(
                    (
                        pl.col("tcga_expression_provenance").fill_null(0.0)
                        + pl.col("gtex_expression_provenance").fill_null(0.0)
                    )
                    / 2.0
                )
                .otherwise(0.0)
                .alias("traceability_confidence"),
                pl.when(pl.col("mutation_evidence") & pl.col("expression_evidence"))
                .then(pl.col("mutation_confidence") * 0.6 + pl.col("expression_confidence") * 0.4)
                .when(pl.col("mutation_evidence"))
                .then(pl.col("mutation_confidence"))
                .when(pl.col("expression_evidence"))
                .then(pl.col("expression_confidence"))
                .otherwise(0.0)
                .alias("biological_confidence"),
            ]
        )
        .with_columns(
            (
                pl.col("biological_confidence") * 0.75
                + pl.col("graph_confidence") * 0.10
                + pl.col("quality_confidence") * 0.075
                + pl.col("traceability_confidence") * 0.075
            )
            .clip(0.0, 1.0)
            .round(6)
            .alias("overall_confidence")
        )
        .with_columns(
            [
                pl.when(pl.col("overall_confidence") >= 0.75)
                .then(pl.lit("high"))
                .when(pl.col("overall_confidence") >= 0.50)
                .then(pl.lit("moderate"))
                .when(pl.col("overall_confidence") >= 0.25)
                .then(pl.lit("limited"))
                .otherwise(pl.lit("low"))
                .alias("confidence_tier"),
                pl.when(pl.col("expression_evidence"))
                .then(
                    pl.when(pl.col("batch_concordance").is_in(["discordant", "unavailable"]))
                    .then(pl.lit("high"))
                    .otherwise(pl.lit("elevated"))
                )
                .otherwise(pl.lit("not_applicable"))
                .alias("batch_effect_risk"),
                pl.when(pl.col("quality_confidence") == 1.0)
                .then(pl.lit("passed"))
                .otherwise(pl.lit("failed"))
                .alias("quality_status"),
                pl.when(pl.col("traceability_confidence") >= 0.999)
                .then(pl.lit("passed"))
                .when(pl.col("traceability_confidence") > 0.0)
                .then(pl.lit("warning"))
                .otherwise(pl.lit("failed"))
                .alias("traceability_status"),
            ]
        )
        .with_columns(
            pl.struct(
                [
                    "expression_evidence",
                    "batch_concordance",
                    "mutation_evidence",
                    "sample_count_normal",
                    "sample_count_tumor",
                    "total_profiled_sample_count",
                    "traceability_confidence",
                    "graph_confidence",
                ]
            )
            .map_elements(_caveat_summary, return_dtype=pl.Utf8)
            .alias("caveat_summary")
        )
    )

    result = joined.select(list(CONFIDENCE_SCHEMA)).sort(
        ["overall_confidence", "priority_score"], descending=[True, True]
    )
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    result.write_parquet(out)
    return {
        "path": str(out),
        "row_count": int(result.height),
        "high_confidence_count": int(result.filter(pl.col("confidence_tier") == "high").height),
    }


def evidence_confidence(
    cancer_type: str | None = None,
    gene_query: str | None = None,
    confidence_tier: str | None = None,
    batch_concordance: str | None = None,
    min_confidence: float | None = None,
    limit: int = 50,
    gold_path: str | Path = "data/gold/gold_cancer_gene_evidence_confidence.parquet",
) -> dict[str, object]:
    path = Path(gold_path)
    df = pl.read_parquet(path) if path.exists() else _empty_confidence()
    if df.is_empty() or not set(CONFIDENCE_SCHEMA).issubset(df.columns):
        return {
            "filters": {
                "cancer_type": cancer_type,
                "gene_query": gene_query,
                "confidence_tier": confidence_tier,
                "batch_concordance": batch_concordance,
                "min_confidence": min_confidence,
                "limit": limit,
            },
            "rows": [],
            "row_count": 0,
            "warning": "Evidence confidence mart is unavailable. Run `make run-graph-export` first.",
        }

    filtered = df
    if cancer_type:
        filtered = filtered.filter(pl.col("cancer_type") == cancer_type)
    if gene_query:
        filtered = filtered.filter(
            pl.col("gene_symbol").str.to_uppercase().str.contains(gene_query.upper(), literal=True)
        )
    if confidence_tier:
        filtered = filtered.filter(pl.col("confidence_tier") == confidence_tier.lower())
    if batch_concordance:
        filtered = filtered.filter(pl.col("batch_concordance") == batch_concordance.lower())
    if min_confidence is not None:
        filtered = filtered.filter(pl.col("overall_confidence") >= float(min_confidence))

    filtered = filtered.sort(["overall_confidence", "priority_score"], descending=[True, True])
    capped = filtered.head(max(int(limit), 0))
    return {
        "filters": {
            "cancer_type": cancer_type,
            "gene_query": gene_query,
            "confidence_tier": confidence_tier,
            "batch_concordance": batch_concordance,
            "min_confidence": min_confidence,
            "limit": limit,
        },
        "rows": capped.to_dicts(),
        "row_count": capped.height,
        "total_matching_rows": filtered.height,
        "warning": (
            "Exploratory evidence calibration only; cross-study expression is batch-effect limited "
            "and is not clinically validated."
        ),
    }
