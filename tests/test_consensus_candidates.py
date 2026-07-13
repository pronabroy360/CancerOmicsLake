from pathlib import Path

import polars as pl

from src.analytics.consensus_candidates import (
    CONSENSUS_CANDIDATE_SCHEMA,
    build_consensus_candidates,
    consensus_candidates,
)


def _write_fixture(gold: Path) -> None:
    gold.mkdir()
    pl.DataFrame(
        [
            {
                "cancer_type": "TCGA-BRCA",
                "gene_symbol": "STRONG",
                "mutation_frequency": 0.40,
                "mutated_sample_count": 40,
                "total_profiled_sample_count": 100,
                "abs_log2_fold_change": 2.0,
                "log2_fold_change": 2.0,
                "graph_degree": 3,
                "evidence_count": 2,
                "priority_score": 0.90,
                "priority_tier": "high",
                "evidence_summary": "fixture",
            },
            {
                "cancer_type": "TCGA-BRCA",
                "gene_symbol": "BADREF",
                "mutation_frequency": 0.10,
                "mutated_sample_count": 10,
                "total_profiled_sample_count": 100,
                "abs_log2_fold_change": 2.5,
                "log2_fold_change": 2.5,
                "graph_degree": 2,
                "evidence_count": 2,
                "priority_score": 0.80,
                "priority_tier": "high",
                "evidence_summary": "fixture",
            },
        ]
    ).write_parquet(gold / "gold_candidate_gene_priority.parquet")
    pl.DataFrame(
        [
            {
                "cancer_type": "TCGA-BRCA",
                "gene_symbol": "STRONG",
                "overall_confidence": 0.90,
                "confidence_tier": "high",
            },
            {
                "cancer_type": "TCGA-BRCA",
                "gene_symbol": "BADREF",
                "overall_confidence": 0.85,
                "confidence_tier": "high",
            },
        ]
    ).write_parquet(gold / "gold_cancer_gene_evidence_confidence.parquet")
    pl.DataFrame(
        [
            {
                "cancer_type": "TCGA-BRCA",
                "gene_symbol": "STRONG",
                "reference_stability_score": 0.95,
                "reference_concordance": "concordant_up",
            },
            {
                "cancer_type": "TCGA-BRCA",
                "gene_symbol": "BADREF",
                "reference_stability_score": 0.90,
                "reference_concordance": "reference_sensitive",
            },
        ]
    ).write_parquet(gold / "gold_reference_triangulation.parquet")
    pl.DataFrame(
        [
            {
                "cancer_type": "TCGA-BRCA",
                "gene_symbol": "STRONG",
                "bootstrap_stability_score": 0.88,
                "bootstrap_stability_tier": "high",
            },
            {
                "cancer_type": "TCGA-BRCA",
                "gene_symbol": "BADREF",
                "bootstrap_stability_score": 0.82,
                "bootstrap_stability_tier": "high",
            },
        ]
    ).write_parquet(gold / "gold_candidate_bootstrap_stability.parquet")
    pl.DataFrame(
        [
            {
                "cancer_type": "TCGA-BRCA",
                "gene_symbol": "STRONG",
                "validation_score": 0.92,
                "validation_tier": "high",
                "direction_agreement": "concordant",
            },
            {
                "cancer_type": "TCGA-BRCA",
                "gene_symbol": "BADREF",
                "validation_score": 0.30,
                "validation_tier": "discordant",
                "direction_agreement": "discordant",
            },
        ]
    ).write_parquet(gold / "gold_external_expression_validation.parquet")
    pl.DataFrame(
        [
            {
                "cancer_type": "TCGA-BRCA",
                "gene_symbol": "STRONG",
                "statistical_support_score": 0.95,
                "statistical_support_tier": "replicated_fdr",
                "native_fdr_q_value": 0.001,
                "recount3_fdr_q_value": 0.002,
                "native_rank_biserial": 0.80,
                "recount3_rank_biserial": 0.75,
            },
            {
                "cancer_type": "TCGA-BRCA",
                "gene_symbol": "BADREF",
                "statistical_support_score": 0.0,
                "statistical_support_tier": "discordant",
                "native_fdr_q_value": 0.001,
                "recount3_fdr_q_value": 0.001,
                "native_rank_biserial": 0.70,
                "recount3_rank_biserial": -0.70,
            },
        ]
    ).write_parquet(gold / "gold_expression_statistical_support.parquet")
    pl.DataFrame(
        [
            {
                "cancer_type": "TCGA-BRCA",
                "gene_symbol": "STRONG",
                "matched_case_count": 40,
                "paired_fdr_q_value": 0.001,
                "paired_rank_biserial": 0.85,
                "paired_support_score": 0.95,
                "paired_support_tier": "paired_replicated",
            },
            {
                "cancer_type": "TCGA-BRCA",
                "gene_symbol": "BADREF",
                "matched_case_count": 40,
                "paired_fdr_q_value": 0.001,
                "paired_rank_biserial": -0.80,
                "paired_support_score": 0.0,
                "paired_support_tier": "paired_discordant",
            },
        ]
    ).write_parquet(gold / "gold_paired_tcga_expression_support.parquet")


def test_build_consensus_candidates_prioritizes_only_concordant_evidence(tmp_path: Path) -> None:
    gold = tmp_path / "gold"
    _write_fixture(gold)
    output = gold / "consensus.parquet"

    summary = build_consensus_candidates(
        gold_dir=gold,
        output_path=output,
        report_path=tmp_path / "report.json",
    )
    result = pl.read_parquet(output)
    rows = {row["gene_symbol"]: row for row in result.to_dicts()}

    assert summary["status"] == "completed"
    assert summary["row_count"] == 2
    assert rows["STRONG"]["consensus_decision"] == "prioritized"
    assert rows["STRONG"]["publication_tier"] == "strong_candidate"
    assert rows["STRONG"]["rejection_reasons"] == "none"
    assert rows["STRONG"]["statistical_component"] == 0.95
    assert rows["BADREF"]["consensus_decision"] == "deprioritized"
    assert "external_validation_discordant" in rows["BADREF"]["rejection_reasons"]
    assert "reference_sensitive_or_discordant" in rows["BADREF"]["rejection_reasons"]
    assert "statistical_support_discordant" in rows["BADREF"]["rejection_reasons"]
    assert "paired_support_discordant" in rows["BADREF"]["rejection_reasons"]
    assert rows["BADREF"]["statistical_component"] == 0.0
    assert rows["BADREF"]["paired_component"] == 0.0


def test_consensus_candidates_query_filters_rows(tmp_path: Path) -> None:
    gold = tmp_path / "gold"
    _write_fixture(gold)
    output = gold / "consensus.parquet"
    build_consensus_candidates(gold_dir=gold, output_path=output, report_path=tmp_path / "report.json")

    payload = consensus_candidates(
        cancer_type="TCGA-BRCA",
        gene_query="strong",
        decision="prioritized",
        publication_tier="strong_candidate",
        min_consensus_score=0.75,
        gold_path=output,
    )

    assert payload["row_count"] == 1
    assert payload["rows"][0]["gene_symbol"] == "STRONG"
    assert "clinical validation" in payload["warning"]


def test_consensus_candidates_missing_inputs_writes_empty_contract(tmp_path: Path) -> None:
    output = tmp_path / "gold" / "consensus.parquet"
    summary = build_consensus_candidates(
        gold_dir=tmp_path / "gold",
        output_path=output,
        report_path=tmp_path / "report.json",
    )

    assert summary["status"] == "empty"
    assert pl.read_parquet(output).schema == CONSENSUS_CANDIDATE_SCHEMA
