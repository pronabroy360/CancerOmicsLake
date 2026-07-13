from __future__ import annotations

import json
from pathlib import Path

import polars as pl

from src.analytics.dashboard_data import (
    batch_effect_sensitivity_data,
    candidate_priority_data,
    consensus_candidates_data,
    cohort_distribution_data,
    evidence_confidence_data,
    external_expression_validation_data,
    expression_statistical_support_data,
    paired_expression_support_data,
    graph_explorer_data,
    graph_node_metrics_data,
    overview_metrics,
    quality_report_data,
)


def test_overview_metrics_reads_gold_and_quality(tmp_path: Path) -> None:
    gold = tmp_path / "gold_cohort_summary.parquet"
    report = tmp_path / "silver_data_quality_report.json"

    pl.DataFrame(
        [
            {
                "tcga_project_count": 3,
                "tcga_sample_count": 120,
                "gtex_expression_sample_count": 40,
                "gene_count": 1000,
                "mutation_record_count": 5000,
                "gtex_expression_row_count": 4000,
                "tcga_expression_row_count": 10000,
            }
        ]
    ).write_parquet(gold)
    report.write_text(
        json.dumps(
            {
                "status": "passed_with_warnings",
                "generated_at": "2026-05-28T10:00:00Z",
                "pipeline_run_id": "20260528T100000Z",
                "checks": [],
            }
        ),
        encoding="utf-8",
    )

    payload = overview_metrics(gold_summary_path=gold, quality_report_path=report)
    assert payload["tcga_projects"] == 3
    assert payload["expression_records"] == 14000
    assert payload["quality_status"] == "passed_with_warnings"


def test_cohort_distribution_data_builds_counts(tmp_path: Path) -> None:
    silver = tmp_path / "silver_samples.parquet"
    pl.DataFrame(
        {
            "project_id": ["TCGA-BRCA", "TCGA-BRCA", "TCGA-LUAD"],
            "case_id": ["c1", "c2", "c3"],
            "sample_id": ["s1", "s2", "s3"],
            "sample_type": ["Primary Tumor", "Solid Tissue Normal", "Primary Tumor"],
        }
    ).write_parquet(silver)

    payload = cohort_distribution_data(silver)
    assert payload["total_samples"] == 3
    assert payload["total_cases"] == 3
    assert payload["project_options"] == ["TCGA-BRCA", "TCGA-LUAD"]
    assert payload["sample_by_cancer"].height == 2


def test_graph_explorer_data_filters_edges_and_nodes(tmp_path: Path) -> None:
    nodes_path = tmp_path / "nodes.parquet"
    edges_path = tmp_path / "edges.parquet"

    pl.DataFrame(
        [
            {"node_id": "GENE:TP53", "node_label": "Gene", "name": "TP53", "primary_site": "NA", "source": "TCGA"},
            {"node_id": "TCGA-BRCA", "node_label": "CancerType", "name": "TCGA-BRCA", "primary_site": "Breast", "source": "TCGA"},
            {"node_id": "TISSUE:Lung", "node_label": "Tissue", "name": "Lung", "primary_site": "Lung", "source": "GTEx"},
        ]
    ).write_parquet(nodes_path)
    pl.DataFrame(
        [
            {
                "edge_id": "e1",
                "source_node_id": "GENE:TP53",
                "target_node_id": "TCGA-BRCA",
                "edge_type": "MUTATED_IN_CANCER",
                "weight": 0.5,
                "evidence_source": "TCGA",
            },
            {
                "edge_id": "e2",
                "source_node_id": "GENE:TP53",
                "target_node_id": "TISSUE:Lung",
                "edge_type": "EXPRESSED_IN_TISSUE",
                "weight": 2.1,
                "evidence_source": "GTEx",
            },
        ]
    ).write_parquet(edges_path)

    payload = graph_explorer_data(
        edge_types=["MUTATED_IN_CANCER"],
        node_query="TP53",
        max_rows=100,
        graph_nodes_path=nodes_path,
        graph_edges_path=edges_path,
    )
    assert payload["edges"].height == 1
    assert payload["nodes"].height == 2
    assert payload["edge_type_counts"].height == 1


def test_candidate_priority_data_filters_rows(tmp_path: Path) -> None:
    gold = tmp_path / "gold_candidate_gene_priority.parquet"
    pl.DataFrame(
        [
            {
                "cancer_type": "TCGA-BRCA",
                "gene_symbol": "TP53",
                "mutation_frequency": 0.4,
                "mutated_sample_count": 4,
                "total_profiled_sample_count": 10,
                "abs_log2_fold_change": 1.2,
                "log2_fold_change": 1.2,
                "graph_degree": 2,
                "evidence_count": 2,
                "priority_score": 0.7,
                "priority_tier": "high",
                "evidence_summary": "x",
            },
            {
                "cancer_type": "TCGA-LUAD",
                "gene_symbol": "EGFR",
                "mutation_frequency": 0.2,
                "mutated_sample_count": 2,
                "total_profiled_sample_count": 10,
                "abs_log2_fold_change": 0.3,
                "log2_fold_change": 0.3,
                "graph_degree": 2,
                "evidence_count": 2,
                "priority_score": 0.25,
                "priority_tier": "medium",
                "evidence_summary": "y",
            },
        ]
    ).write_parquet(gold)

    df = candidate_priority_data(cancer_type="TCGA-BRCA", tier="high", gold_path=gold)

    assert df.height == 1
    assert df.row(0, named=True)["gene_symbol"] == "TP53"


def test_graph_node_metrics_data_returns_top_nodes(tmp_path: Path) -> None:
    metrics = tmp_path / "gold_graph_node_metrics.parquet"
    pl.DataFrame(
        [
            {
                "node_id": "GENE:TP53",
                "node_label": "Gene",
                "name": "TP53",
                "total_degree": 3,
                "in_degree": 1,
                "out_degree": 2,
                "weighted_degree": 2.5,
                "edge_type_count": 2,
                "degree_rank": 1,
            },
            {
                "node_id": "TCGA-BRCA",
                "node_label": "CancerType",
                "name": "TCGA-BRCA",
                "total_degree": 1,
                "in_degree": 1,
                "out_degree": 0,
                "weighted_degree": 1.0,
                "edge_type_count": 1,
                "degree_rank": 2,
            },
        ]
    ).write_parquet(metrics)

    df = graph_node_metrics_data(limit=1, graph_metrics_path=metrics)

    assert df.height == 1
    assert df.row(0, named=True)["node_id"] == "GENE:TP53"


def test_evidence_confidence_data_returns_filtered_rows(tmp_path: Path) -> None:
    from src.analytics.evidence_confidence import CONFIDENCE_SCHEMA

    path = tmp_path / "confidence.parquet"
    row = {column: None for column in CONFIDENCE_SCHEMA}
    row.update(
        {
            "cancer_type": "TCGA-BRCA",
            "gene_symbol": "TP53",
            "overall_confidence": 0.8,
            "priority_score": 0.7,
            "confidence_tier": "high",
        }
    )
    pl.DataFrame([row], schema=CONFIDENCE_SCHEMA).write_parquet(path)

    result = evidence_confidence_data(cancer_type="TCGA-BRCA", confidence_tier="high", gold_path=path)

    assert result.height == 1
    assert result.row(0, named=True)["gene_symbol"] == "TP53"


def test_batch_effect_sensitivity_data_returns_filtered_rows(tmp_path: Path) -> None:
    from src.analytics.batch_effect_sensitivity import BATCH_EFFECT_SENSITIVITY_SCHEMA

    path = tmp_path / "sensitivity.parquet"
    row = {column: None for column in BATCH_EFFECT_SENSITIVITY_SCHEMA}
    row.update(
        {
            "cancer_type": "TCGA-BRCA",
            "gene_symbol": "TP53",
            "percentile_delta": 0.8,
            "robust_z_delta": 1.2,
            "support_tier": "high",
            "sensitivity_direction": "rank_up",
        }
    )
    pl.DataFrame([row], schema=BATCH_EFFECT_SENSITIVITY_SCHEMA).write_parquet(path)

    result = batch_effect_sensitivity_data(
        cancer_type="TCGA-BRCA",
        support_tier="high",
        direction="rank_up",
        gold_path=path,
    )

    assert result.height == 1
    assert result.row(0, named=True)["gene_symbol"] == "TP53"


def test_reference_triangulation_data_returns_filtered_rows(tmp_path: Path) -> None:
    from src.analytics.dashboard_data import reference_triangulation_data
    from src.analytics.reference_triangulation import REFERENCE_TRIANGULATION_SCHEMA

    path = tmp_path / "triangulation.parquet"
    row = {column: None for column in REFERENCE_TRIANGULATION_SCHEMA}
    row.update(
        {
            "cancer_type": "TCGA-BRCA",
            "gene_symbol": "TP53",
            "reference_concordance": "concordant_up",
            "tcga_normal_support_tier": "high",
            "reference_stability_score": 0.9,
            "reference_effect_delta": 0.1,
        }
    )
    pl.DataFrame([row], schema=REFERENCE_TRIANGULATION_SCHEMA).write_parquet(path)

    result = reference_triangulation_data(
        cancer_type="TCGA-BRCA",
        concordance="concordant_up",
        support_tier="high",
        gold_path=path,
    )

    assert result.height == 1
    assert result.row(0, named=True)["gene_symbol"] == "TP53"


def test_bootstrap_stability_data_returns_filtered_rows(tmp_path: Path) -> None:
    from src.analytics.bootstrap_stability import BOOTSTRAP_STABILITY_SCHEMA
    from src.analytics.dashboard_data import bootstrap_stability_data

    path = tmp_path / "bootstrap.parquet"
    row = {column: None for column in BOOTSTRAP_STABILITY_SCHEMA}
    row.update(
        {
            "cancer_type": "TCGA-BRCA",
            "gene_symbol": "TP53",
            "priority_score": 0.9,
            "bootstrap_stability_score": 0.85,
            "bootstrap_stability_tier": "high",
        }
    )
    pl.DataFrame([row], schema=BOOTSTRAP_STABILITY_SCHEMA).write_parquet(path)

    result = bootstrap_stability_data(
        cancer_type="TCGA-BRCA",
        stability_tier="high",
        min_stability=0.8,
        gold_path=path,
    )

    assert result.height == 1
    assert result.row(0, named=True)["gene_symbol"] == "TP53"


def test_external_expression_validation_data_returns_filtered_rows(tmp_path: Path) -> None:
    from src.analytics.external_validation import EXTERNAL_VALIDATION_SCHEMA

    path = tmp_path / "external_validation.parquet"
    row = {column: None for column in EXTERNAL_VALIDATION_SCHEMA}
    row.update(
        {
            "cancer_type": "TCGA-BRCA",
            "gene_symbol": "TP53",
            "direction_agreement": "concordant",
            "validation_score": 0.9,
            "validation_tier": "high",
        }
    )
    pl.DataFrame([row], schema=EXTERNAL_VALIDATION_SCHEMA).write_parquet(path)

    result = external_expression_validation_data(
        cancer_type="TCGA-BRCA",
        validation_tier="high",
        direction_agreement="concordant",
        min_validation_score=0.8,
        gold_path=path,
    )

    assert result.height == 1
    assert result.row(0, named=True)["gene_symbol"] == "TP53"


def test_consensus_candidates_data_returns_filtered_rows(tmp_path: Path) -> None:
    from src.analytics.consensus_candidates import CONSENSUS_CANDIDATE_SCHEMA

    path = tmp_path / "consensus.parquet"
    row = {column: None for column in CONSENSUS_CANDIDATE_SCHEMA}
    row.update(
        {
            "cancer_type": "TCGA-BRCA",
            "gene_symbol": "TP53",
            "consensus_score": 0.9,
            "consensus_decision": "prioritized",
            "publication_tier": "strong_candidate",
        }
    )
    pl.DataFrame([row], schema=CONSENSUS_CANDIDATE_SCHEMA).write_parquet(path)

    result = consensus_candidates_data(
        cancer_type="TCGA-BRCA",
        decision="prioritized",
        publication_tier="strong_candidate",
        min_consensus_score=0.8,
        gold_path=path,
    )

    assert result.height == 1
    assert result.row(0, named=True)["gene_symbol"] == "TP53"


def test_expression_statistical_support_data_returns_filtered_rows(tmp_path: Path) -> None:
    from src.analytics.expression_statistics import EXPRESSION_STATISTICS_SCHEMA

    path = tmp_path / "statistics.parquet"
    row = {column: None for column in EXPRESSION_STATISTICS_SCHEMA}
    row.update(
        {
            "cancer_type": "TCGA-BRCA",
            "gene_symbol": "TP53",
            "statistical_support_score": 0.9,
            "statistical_support_tier": "replicated_fdr",
            "recount3_fdr_q_value": 0.01,
        }
    )
    pl.DataFrame([row], schema=EXPRESSION_STATISTICS_SCHEMA).write_parquet(path)

    result = expression_statistical_support_data(
        cancer_type="TCGA-BRCA",
        support_tier="replicated_fdr",
        max_fdr=0.05,
        min_support_score=0.8,
        gold_path=path,
    )

    assert result.height == 1
    assert result.row(0, named=True)["gene_symbol"] == "TP53"


def test_paired_expression_support_data_returns_filtered_rows(tmp_path: Path) -> None:
    from src.analytics.paired_expression import PAIRED_EXPRESSION_SCHEMA

    path = tmp_path / "paired.parquet"
    row = {column: None for column in PAIRED_EXPRESSION_SCHEMA}
    row.update(
        {
            "cancer_type": "TCGA-BRCA",
            "gene_symbol": "TP53",
            "matched_case_count": 40,
            "paired_fdr_q_value": 0.01,
            "paired_support_score": 0.9,
            "paired_support_tier": "paired_replicated",
        }
    )
    pl.DataFrame([row], schema=PAIRED_EXPRESSION_SCHEMA).write_parquet(path)

    result = paired_expression_support_data(
        cancer_type="TCGA-BRCA",
        support_tier="paired_replicated",
        max_fdr=0.05,
        min_support_score=0.8,
        gold_path=path,
    )

    assert result.height == 1
    assert result.row(0, named=True)["gene_symbol"] == "TP53"


def test_quality_report_data_builds_status_counts(tmp_path: Path) -> None:
    report = tmp_path / "silver_data_quality_report.json"
    report.write_text(
        json.dumps(
            {
                "status": "failed",
                "pipeline_run_id": "x",
                "generated_at": "y",
                "checks": [
                    {"check_name": "a", "status": "passed", "failed_rows": 0},
                    {"check_name": "b", "status": "warning", "failed_rows": 2},
                    {"check_name": "c", "status": "failed", "failed_rows": 1},
                ],
            }
        ),
        encoding="utf-8",
    )

    payload = quality_report_data(report)
    assert payload["status"] == "failed"
    assert payload["checks"].height == 3
    assert payload["status_counts"].height == 3
