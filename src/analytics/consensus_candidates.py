from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path
import time

import polars as pl


CONSENSUS_CANDIDATE_SCHEMA = {
    "cancer_type": pl.Utf8,
    "gene_symbol": pl.Utf8,
    "consensus_score": pl.Float64,
    "consensus_decision": pl.Utf8,
    "publication_tier": pl.Utf8,
    "rejection_reasons": pl.Utf8,
    "priority_score": pl.Float64,
    "priority_tier": pl.Utf8,
    "overall_confidence": pl.Float64,
    "confidence_tier": pl.Utf8,
    "mutation_frequency": pl.Float64,
    "mutated_sample_count": pl.Int64,
    "total_profiled_sample_count": pl.Int64,
    "log2_fold_change": pl.Float64,
    "abs_log2_fold_change": pl.Float64,
    "reference_stability_score": pl.Float64,
    "reference_concordance": pl.Utf8,
    "bootstrap_stability_score": pl.Float64,
    "bootstrap_stability_tier": pl.Utf8,
    "validation_score": pl.Float64,
    "validation_tier": pl.Utf8,
    "direction_agreement": pl.Utf8,
    "statistical_support_score": pl.Float64,
    "statistical_support_tier": pl.Utf8,
    "native_fdr_q_value": pl.Float64,
    "recount3_fdr_q_value": pl.Float64,
    "native_rank_biserial": pl.Float64,
    "recount3_rank_biserial": pl.Float64,
    "matched_case_count": pl.Int64,
    "paired_fdr_q_value": pl.Float64,
    "paired_rank_biserial": pl.Float64,
    "paired_support_score": pl.Float64,
    "paired_support_tier": pl.Utf8,
    "evidence_component_count": pl.Int64,
    "evidence_completeness": pl.Float64,
    "priority_component": pl.Float64,
    "confidence_component": pl.Float64,
    "reference_component": pl.Float64,
    "bootstrap_component": pl.Float64,
    "external_component": pl.Float64,
    "statistical_component": pl.Float64,
    "paired_component": pl.Float64,
    "mutation_component": pl.Float64,
    "consensus_caveat": pl.Utf8,
}


def _empty_consensus_candidates() -> pl.DataFrame:
    return pl.DataFrame(schema=CONSENSUS_CANDIDATE_SCHEMA)


def _read_or_empty(path: Path) -> pl.DataFrame:
    return pl.read_parquet(path) if path.exists() else pl.DataFrame()


def _select_existing(df: pl.DataFrame, expressions: list[pl.Expr], schema: dict[str, pl.DataType]) -> pl.DataFrame:
    if df.is_empty():
        return pl.DataFrame(schema=schema)
    return df.select(expressions)


def _reason_summary(row: dict[str, object]) -> str:
    reasons: list[str] = []
    if row.get("direction_agreement") == "discordant" or row.get("validation_tier") == "discordant":
        reasons.append("external_validation_discordant")
    if row.get("reference_concordance") in {"reference_sensitive", "discordant"}:
        reasons.append("reference_sensitive_or_discordant")
    if row.get("bootstrap_stability_tier") in {"limited", "unstable"}:
        reasons.append("bootstrap_support_weak")
    if row.get("confidence_tier") in {"limited", "low"}:
        reasons.append("evidence_confidence_weak")
    if row.get("statistical_support_tier") == "discordant":
        reasons.append("statistical_support_discordant")
    if row.get("paired_support_tier") == "paired_discordant":
        reasons.append("paired_support_discordant")
    if float(row.get("consensus_score") or 0.0) < 0.45:
        reasons.append("low_consensus_score")
    return ";".join(reasons) if reasons else "none"


def build_consensus_candidates(
    gold_dir: str | Path = "data/gold",
    output_path: str | Path = "data/gold/gold_consensus_candidate_genes.parquet",
    report_path: str | Path = "outputs/reports/consensus_candidate_report.json",
) -> dict[str, object]:
    started = time.monotonic()
    gold_root = Path(gold_dir)
    candidate = _read_or_empty(gold_root / "gold_candidate_gene_priority.parquet")
    output = Path(output_path)
    report = Path(report_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    report.parent.mkdir(parents=True, exist_ok=True)

    if candidate.is_empty():
        result = _empty_consensus_candidates()
        status = "empty"
    else:
        confidence = _read_or_empty(gold_root / "gold_cancer_gene_evidence_confidence.parquet")
        reference = _read_or_empty(gold_root / "gold_reference_triangulation.parquet")
        bootstrap = _read_or_empty(gold_root / "gold_candidate_bootstrap_stability.parquet")
        external = _read_or_empty(gold_root / "gold_external_expression_validation.parquet")
        statistics = _read_or_empty(gold_root / "gold_expression_statistical_support.parquet")
        paired = _read_or_empty(gold_root / "gold_paired_tcga_expression_support.parquet")

        base = candidate.select(
            [
                "cancer_type",
                "gene_symbol",
                pl.col("priority_score").cast(pl.Float64, strict=False),
                pl.col("priority_tier").cast(pl.Utf8, strict=False),
                pl.col("mutation_frequency").cast(pl.Float64, strict=False),
                pl.col("mutated_sample_count").cast(pl.Int64, strict=False),
                pl.col("total_profiled_sample_count").cast(pl.Int64, strict=False),
                pl.col("log2_fold_change").cast(pl.Float64, strict=False),
                pl.col("abs_log2_fold_change").cast(pl.Float64, strict=False),
            ]
        )
        confidence_part = _select_existing(
            confidence,
            [
                "cancer_type",
                "gene_symbol",
                pl.col("overall_confidence").cast(pl.Float64, strict=False),
                pl.col("confidence_tier").cast(pl.Utf8, strict=False),
            ],
            {
                "cancer_type": pl.Utf8,
                "gene_symbol": pl.Utf8,
                "overall_confidence": pl.Float64,
                "confidence_tier": pl.Utf8,
            },
        )
        reference_part = _select_existing(
            reference,
            [
                "cancer_type",
                "gene_symbol",
                pl.col("reference_stability_score").cast(pl.Float64, strict=False),
                pl.col("reference_concordance").cast(pl.Utf8, strict=False),
            ],
            {
                "cancer_type": pl.Utf8,
                "gene_symbol": pl.Utf8,
                "reference_stability_score": pl.Float64,
                "reference_concordance": pl.Utf8,
            },
        )
        bootstrap_part = _select_existing(
            bootstrap,
            [
                "cancer_type",
                "gene_symbol",
                pl.col("bootstrap_stability_score").cast(pl.Float64, strict=False),
                pl.col("bootstrap_stability_tier").cast(pl.Utf8, strict=False),
            ],
            {
                "cancer_type": pl.Utf8,
                "gene_symbol": pl.Utf8,
                "bootstrap_stability_score": pl.Float64,
                "bootstrap_stability_tier": pl.Utf8,
            },
        )
        external_part = _select_existing(
            external,
            [
                "cancer_type",
                "gene_symbol",
                pl.col("validation_score").cast(pl.Float64, strict=False),
                pl.col("validation_tier").cast(pl.Utf8, strict=False),
                pl.col("direction_agreement").cast(pl.Utf8, strict=False),
            ],
            {
                "cancer_type": pl.Utf8,
                "gene_symbol": pl.Utf8,
                "validation_score": pl.Float64,
                "validation_tier": pl.Utf8,
                "direction_agreement": pl.Utf8,
            },
        )
        statistics_part = _select_existing(
            statistics,
            [
                "cancer_type",
                "gene_symbol",
                pl.col("statistical_support_score").cast(pl.Float64, strict=False),
                pl.col("statistical_support_tier").cast(pl.Utf8, strict=False),
                pl.col("native_fdr_q_value").cast(pl.Float64, strict=False),
                pl.col("recount3_fdr_q_value").cast(pl.Float64, strict=False),
                pl.col("native_rank_biserial").cast(pl.Float64, strict=False),
                pl.col("recount3_rank_biserial").cast(pl.Float64, strict=False),
            ],
            {
                "cancer_type": pl.Utf8,
                "gene_symbol": pl.Utf8,
                "statistical_support_score": pl.Float64,
                "statistical_support_tier": pl.Utf8,
                "native_fdr_q_value": pl.Float64,
                "recount3_fdr_q_value": pl.Float64,
                "native_rank_biserial": pl.Float64,
                "recount3_rank_biserial": pl.Float64,
            },
        )
        paired_part = _select_existing(
            paired,
            [
                "cancer_type",
                "gene_symbol",
                pl.col("matched_case_count").cast(pl.Int64, strict=False),
                pl.col("paired_fdr_q_value").cast(pl.Float64, strict=False),
                pl.col("paired_rank_biserial").cast(pl.Float64, strict=False),
                pl.col("paired_support_score").cast(pl.Float64, strict=False),
                pl.col("paired_support_tier").cast(pl.Utf8, strict=False),
            ],
            {
                "cancer_type": pl.Utf8,
                "gene_symbol": pl.Utf8,
                "matched_case_count": pl.Int64,
                "paired_fdr_q_value": pl.Float64,
                "paired_rank_biserial": pl.Float64,
                "paired_support_score": pl.Float64,
                "paired_support_tier": pl.Utf8,
            },
        )

        joined = (
            base.join(confidence_part, on=["cancer_type", "gene_symbol"], how="left")
            .join(reference_part, on=["cancer_type", "gene_symbol"], how="left")
            .join(bootstrap_part, on=["cancer_type", "gene_symbol"], how="left")
            .join(external_part, on=["cancer_type", "gene_symbol"], how="left")
            .join(statistics_part, on=["cancer_type", "gene_symbol"], how="left")
            .join(paired_part, on=["cancer_type", "gene_symbol"], how="left")
            .with_columns(
                [
                    pl.col("priority_score").fill_null(0.0).clip(0.0, 1.0),
                    pl.col("overall_confidence").fill_null(0.0).clip(0.0, 1.0),
                    pl.col("reference_stability_score").fill_null(0.0).clip(0.0, 1.0),
                    pl.col("bootstrap_stability_score").fill_null(0.0).clip(0.0, 1.0),
                    pl.col("validation_score").fill_null(0.0).clip(0.0, 1.0),
                    pl.col("statistical_support_score").fill_null(0.0).clip(0.0, 1.0),
                    pl.col("native_fdr_q_value").fill_null(1.0).clip(0.0, 1.0),
                    pl.col("recount3_fdr_q_value").fill_null(1.0).clip(0.0, 1.0),
                    pl.col("native_rank_biserial").fill_null(0.0).clip(-1.0, 1.0),
                    pl.col("recount3_rank_biserial").fill_null(0.0).clip(-1.0, 1.0),
                    pl.col("matched_case_count").fill_null(0).cast(pl.Int64),
                    pl.col("paired_fdr_q_value").fill_null(1.0).clip(0.0, 1.0),
                    pl.col("paired_rank_biserial").fill_null(0.0).clip(-1.0, 1.0),
                    pl.col("paired_support_score").fill_null(0.0).clip(0.0, 1.0),
                    pl.col("mutation_frequency").fill_null(0.0).clip(0.0, 1.0),
                    pl.col("mutated_sample_count").fill_null(0).cast(pl.Int64),
                    pl.col("total_profiled_sample_count").fill_null(0).cast(pl.Int64),
                    pl.col("log2_fold_change").fill_null(0.0),
                    pl.col("abs_log2_fold_change").fill_null(0.0),
                    pl.col("priority_tier").fill_null("low"),
                    pl.col("confidence_tier").fill_null("missing"),
                    pl.col("reference_concordance").fill_null("missing"),
                    pl.col("bootstrap_stability_tier").fill_null("missing"),
                    pl.col("validation_tier").fill_null("missing"),
                    pl.col("direction_agreement").fill_null("missing"),
                    pl.col("statistical_support_tier").fill_null("missing"),
                    pl.col("paired_support_tier").fill_null("missing"),
                ]
            )
            .with_columns(
                [
                    pl.col("priority_score").alias("priority_component"),
                    pl.col("overall_confidence").alias("confidence_component"),
                    pl.when(pl.col("reference_concordance").is_in(["concordant_up", "concordant_down", "concordant_stable"]))
                    .then(pl.col("reference_stability_score"))
                    .when(pl.col("reference_concordance") == "reference_sensitive")
                    .then(pl.col("reference_stability_score") * 0.35)
                    .otherwise(0.0)
                    .alias("reference_component"),
                    pl.when(pl.col("bootstrap_stability_tier").is_in(["high", "moderate"]))
                    .then(pl.col("bootstrap_stability_score"))
                    .when(pl.col("bootstrap_stability_tier") == "limited")
                    .then(pl.col("bootstrap_stability_score") * 0.5)
                    .otherwise(0.0)
                    .alias("bootstrap_component"),
                    pl.when(pl.col("direction_agreement") == "concordant")
                    .then(pl.col("validation_score"))
                    .when(pl.col("direction_agreement") == "inconclusive")
                    .then(pl.col("validation_score") * 0.5)
                    .otherwise(0.0)
                    .alias("external_component"),
                    pl.when(pl.col("statistical_support_tier") == "replicated_fdr")
                    .then(pl.col("statistical_support_score"))
                    .when(pl.col("statistical_support_tier") == "recount3_fdr_supported")
                    .then(pl.col("statistical_support_score") * 0.65)
                    .when(pl.col("statistical_support_tier") == "native_only_fdr")
                    .then(pl.col("statistical_support_score") * 0.35)
                    .when(pl.col("statistical_support_tier") == "limited")
                    .then(pl.col("statistical_support_score") * 0.15)
                    .otherwise(0.0)
                    .alias("statistical_component"),
                    pl.when(pl.col("paired_support_tier") == "paired_replicated")
                    .then(pl.col("paired_support_score"))
                    .when(pl.col("paired_support_tier") == "paired_internal_fdr")
                    .then(pl.col("paired_support_score") * 0.65)
                    .when(pl.col("paired_support_tier") == "limited")
                    .then(pl.col("paired_support_score") * 0.15)
                    .otherwise(0.0)
                    .alias("paired_component"),
                    pl.col("mutation_frequency").alias("mutation_component"),
                ]
            )
            .with_columns(
                (
                    (pl.col("priority_component") > 0).cast(pl.Int64)
                    + (pl.col("confidence_component") > 0).cast(pl.Int64)
                    + (pl.col("reference_concordance") != "missing").cast(pl.Int64)
                    + (pl.col("bootstrap_stability_tier") != "missing").cast(pl.Int64)
                    + (pl.col("validation_tier") != "missing").cast(pl.Int64)
                    + (pl.col("statistical_support_tier") != "missing").cast(pl.Int64)
                    + (pl.col("paired_support_tier") != "missing").cast(pl.Int64)
                    + (pl.col("mutation_component") > 0).cast(pl.Int64)
                ).alias("evidence_component_count")
            )
            .with_columns((pl.col("evidence_component_count") / 8.0).round(6).alias("evidence_completeness"))
            .with_columns(
                (
                    pl.col("paired_component") * 0.20
                    + pl.col("statistical_component") * 0.20
                    + pl.col("external_component") * 0.15
                    + pl.col("reference_component") * 0.10
                    + pl.col("bootstrap_component") * 0.10
                    + pl.col("confidence_component") * 0.10
                    + pl.col("priority_component") * 0.10
                    + pl.col("mutation_component") * 0.05
                )
                .clip(0.0, 1.0)
                .round(6)
                .alias("consensus_score")
            )
            .with_columns(
                pl.struct(
                    [
                        "direction_agreement",
                        "validation_tier",
                        "reference_concordance",
                        "bootstrap_stability_tier",
                        "confidence_tier",
                        "statistical_support_tier",
                        "paired_support_tier",
                        "consensus_score",
                    ]
                )
                .map_elements(_reason_summary, return_dtype=pl.Utf8)
                .alias("rejection_reasons")
            )
            .with_columns(
                [
                    pl.when((pl.col("consensus_score") >= 0.75) & (pl.col("rejection_reasons") == "none"))
                    .then(pl.lit("prioritized"))
                    .when((pl.col("consensus_score") >= 0.55) & (pl.col("rejection_reasons") == "none"))
                    .then(pl.lit("watchlist"))
                    .otherwise(pl.lit("deprioritized"))
                    .alias("consensus_decision"),
                    pl.when((pl.col("consensus_score") >= 0.80) & (pl.col("rejection_reasons") == "none"))
                    .then(pl.lit("strong_candidate"))
                    .when((pl.col("consensus_score") >= 0.65) & (pl.col("rejection_reasons") == "none"))
                    .then(pl.lit("research_candidate"))
                    .when(pl.col("consensus_score") >= 0.45)
                    .then(pl.lit("exploratory"))
                    .otherwise(pl.lit("deprioritized"))
                    .alias("publication_tier"),
                    pl.lit(
                        "Consensus prioritization integrates paired and cross-source statistical associations with engineering evidence; adjacent-tissue field effects and residual confounding remain, so it is not a clinical biomarker or causal claim."
                    ).alias("consensus_caveat"),
                ]
            )
        )
        result = (
            joined.select(list(CONSENSUS_CANDIDATE_SCHEMA))
            .sort(["consensus_score", "evidence_completeness", "priority_score"], descending=[True, True, True])
        )
        status = "completed"

    result.write_parquet(output)
    decision_counts = (
        result.group_by("consensus_decision").len().sort("consensus_decision").to_dicts()
        if not result.is_empty()
        else []
    )
    publication_tier_counts = (
        result.group_by("publication_tier").len().sort("publication_tier").to_dicts()
        if not result.is_empty()
        else []
    )
    summary = {
        "status": status,
        "generated_at": datetime.now(UTC).isoformat(),
        "path": str(output),
        "row_count": int(result.height),
        "decision_counts": decision_counts,
        "publication_tier_counts": publication_tier_counts,
        "prioritized_count": int(result.filter(pl.col("consensus_decision") == "prioritized").height)
        if not result.is_empty()
        else 0,
        "watchlist_count": int(result.filter(pl.col("consensus_decision") == "watchlist").height)
        if not result.is_empty()
        else 0,
        "elapsed_seconds": round(time.monotonic() - started, 3),
    }
    report.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def consensus_candidates(
    cancer_type: str | None = None,
    gene_query: str | None = None,
    decision: str | None = None,
    publication_tier: str | None = None,
    min_consensus_score: float | None = None,
    limit: int = 50,
    gold_path: str | Path = "data/gold/gold_consensus_candidate_genes.parquet",
) -> dict[str, object]:
    path = Path(gold_path)
    df = pl.read_parquet(path) if path.exists() else _empty_consensus_candidates()
    if df.is_empty() or not set(CONSENSUS_CANDIDATE_SCHEMA).issubset(df.columns):
        filtered = _empty_consensus_candidates()
    else:
        filtered = df
        if cancer_type:
            filtered = filtered.filter(pl.col("cancer_type") == cancer_type)
        if gene_query:
            filtered = filtered.filter(
                pl.col("gene_symbol").str.to_uppercase().str.contains(gene_query.upper(), literal=True)
            )
        if decision:
            filtered = filtered.filter(pl.col("consensus_decision") == decision.lower())
        if publication_tier:
            filtered = filtered.filter(pl.col("publication_tier") == publication_tier.lower())
        if min_consensus_score is not None:
            filtered = filtered.filter(pl.col("consensus_score") >= float(min_consensus_score))
        filtered = filtered.sort(["consensus_score", "evidence_completeness"], descending=[True, True])

    capped = filtered.head(max(int(limit), 0))
    return {
        "filters": {
            "cancer_type": cancer_type,
            "gene_query": gene_query,
            "decision": decision,
            "publication_tier": publication_tier,
            "min_consensus_score": min_consensus_score,
            "limit": limit,
        },
        "rows": capped.to_dicts(),
        "row_count": capped.height,
        "total_matching_rows": filtered.height,
        "warning": (
            "Consensus candidate ranking is a publication-triage layer. It integrates multiple reproducibility signals, "
            "but it is not clinical validation or batch-corrected differential expression."
        ),
    }
