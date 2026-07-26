import json
from pathlib import Path

import polars as pl
import pytest

from src.operations.manuscript_package import build_manuscript_package


def _write_fixture(root: Path, commit: str = "fixture") -> tuple[Path, Path, Path]:
    gold = root / "gold"
    reports = root / "reports"
    gold.mkdir()
    reports.mkdir()
    pl.DataFrame(
        {
            "tcga_project_count": [3],
            "tcga_patient_count": [100],
            "tcga_sample_count": [120],
            "tcga_file_count": [20],
            "gtex_expression_sample_count": [40],
            "tcga_expression_row_count": [1000],
            "gtex_expression_row_count": [900],
            "gene_count": [10],
            "mutation_record_count": [50],
            "protein_altering_mutation_record_count": [30],
            "mutation_profiled_sample_count": [12],
            "generated_at": ["fixture"],
        }
    ).write_parquet(gold / "gold_cohort_summary.parquet")
    pl.DataFrame(
        {
            "cancer_type": ["TCGA-BRCA"],
            "total_profiled_sample_count": [12],
            "mutated_sample_count": [10],
            "mutation_event_count": [30],
            "mutation_event_rate": [2.5],
            "all_somatic_event_count": [40],
            "synonymous_event_count": [10],
            "mutation_frequency": [0.8],
            "mutation_scope": ["protein_altering_only"],
        }
    ).write_parquet(gold / "gold_mutation_frequency_by_cancer.parquet")
    reference_rows = []
    for top_k in [25, 50, 100, 250]:
        reference_rows.append(
            {
                "cancer_type": "TCGA-BRCA",
                "method_a": "gtex_native",
                "method_b": "tcga_adjacent",
                "common_gene_count": 1000,
                "top_k": top_k,
                "top_k_a_count": min(top_k, 1000),
                "top_k_b_count": min(top_k, 1000),
                "top_k_overlap_count": min(top_k, 1000) // 2,
                "top_k_jaccard": 0.33,
                "top_k_direction_concordance": 0.5,
                "universe_direction_concordance": 0.6,
                "regulated_union_gene_count": 300,
                "regulated_direction_concordance": 0.4,
                "spearman_abs_effect": 0.7,
                "median_abs_effect_delta": 0.2,
                "agreement_tier": "limited",
                "evaluation_caveat": "fixture",
            }
        )
    pl.DataFrame(reference_rows).write_parquet(
        gold / "gold_reference_method_comparison.parquet"
    )
    ablation_rows = []
    scenarios = [
        "without_reference_triangulation",
        "without_external_validation",
        "without_paired_support",
        "without_explicit_reference_components",
    ]
    for top_k in [25, 50, 100, 250]:
        for scenario in scenarios:
            ablation_rows.append(
                {
                    "cancer_type": "TCGA-BRCA",
                    "ablation_scenario": scenario,
                    "omitted_components": "fixture",
                    "retained_weight": 0.8,
                    "common_gene_count": 1000,
                    "top_k": top_k,
                    "top_k_overlap_count": min(top_k, 1000) // 2,
                    "top_k_jaccard": 0.33,
                    "spearman_consensus_score": 0.8,
                    "median_baseline_top_k_rank_shift": 2.0,
                    "median_absolute_score_delta": 0.1,
                    "max_absolute_score_delta": 0.2,
                    "baseline_prioritized_count": 10,
                    "fixed_threshold_retained_count": 5,
                    "fixed_threshold_retention_rate": 0.5,
                    "sensitivity_tier": "moderate",
                    "evaluation_caveat": "fixture",
                }
            )
    pl.DataFrame(ablation_rows).write_parquet(
        gold / "gold_consensus_ablation_stability.parquet"
    )

    payloads = {
        "silver_data_quality_report.json": {
            "status": "passed",
            "checks": [{"check_name": "fixture", "status": "passed"}],
        },
        "dbt_execution_report.json": {
            "status": "passed",
            "action": "test",
        },
        "demo_check_report.json": {
            "status": "passed",
            "check_count": 2,
            "checks": [
                {"check_name": "fixture_one", "status": "passed"},
                {"check_name": "fixture_two", "status": "passed"},
            ],
        },
        "project_completion_report.json": {
            "status": "complete",
            "completed_milestones": 9,
            "total_milestones": 9,
        },
        "research_benchmark_report.json": {
            "status": "passed",
            "git_commit": commit,
            "workloads": [
                {"status": "passed", "latency_ms": {"median": 1.0}},
                {"status": "passed", "latency_ms": {"median": 2.0}},
            ],
        },
        "reference_ablation_report.json": {
            "status": "completed",
            "git_commit": commit,
        },
        "graph_metrics_report.json": {
            "status": "passed",
            "public_safe": True,
            "node_count": 20,
            "edge_count": 30,
        },
        "consensus_candidate_report.json": {
            "status": "completed",
            "row_count": 1000,
            "prioritized_count": 10,
            "watchlist_count": 20,
        },
        "external_expression_validation_report.json": {
            "status": "completed",
            "row_count": 1000,
            "tier_counts": [
                {"validation_tier": "discordant", "len": 5},
                {"validation_tier": "high", "len": 995},
            ],
        },
        "paired_expression_support_report.json": {
            "status": "completed",
            "row_count": 1000,
            "tier_counts": [
                {"paired_support_tier": "paired_replicated", "len": 100}
            ],
        },
        "pathway_enrichment_report.json": {
            "status": "completed",
            "row_count": 50,
        },
    }
    for name, payload in payloads.items():
        (reports / name).write_text(json.dumps(payload), encoding="utf-8")
    fair = root / "manifest.json"
    fair.write_text(
        json.dumps(
            {
                "git_commit": commit,
                "resource_count": 18,
                "identifier_safety": {"status": "passed"},
            }
        ),
        encoding="utf-8",
    )
    return gold, reports, fair


def test_build_manuscript_package_writes_evidence_linked_outputs(
    tmp_path: Path,
) -> None:
    gold, reports, fair = _write_fixture(tmp_path)
    output = tmp_path / "manuscript"

    summary = build_manuscript_package(
        gold_dir=gold,
        reports_dir=reports,
        fair_manifest_path=fair,
        output_dir=output,
        strict_provenance=False,
    )

    assert summary["status"] == "passed"
    assert summary["claim_count"] == 10
    assert (output / "manuscript.md").exists()
    assert (output / "figures/figure_2_reference_jaccard.svg").exists()
    assert (output / "tables/table_2_reference_comparison_k100.csv").exists()
    assert "100 TCGA" in (output / "manuscript.md").read_text(encoding="utf-8")
    ledger = json.loads((output / "evidence_ledger.json").read_text(encoding="utf-8"))
    assert ledger["status"] == "passed"
    assert all(len(resource["sha256"]) == 64 for resource in ledger["resources"])
    manifest = json.loads((output / "package_manifest.json").read_text(encoding="utf-8"))
    assert manifest["file_count"] == 14
    assert manifest["hashed_file_count"] == len(manifest["files"]) == 13


def test_build_manuscript_package_fails_on_missing_evidence(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="missing required evidence"):
        build_manuscript_package(
            gold_dir=tmp_path,
            reports_dir=tmp_path,
            fair_manifest_path=tmp_path / "missing.json",
            output_dir=tmp_path / "manuscript",
        )


def test_build_manuscript_package_fails_on_stale_provenance(
    tmp_path: Path,
) -> None:
    gold, reports, fair = _write_fixture(tmp_path, commit="stale")
    with pytest.raises(RuntimeError, match="does not match Git commit"):
        build_manuscript_package(
            gold_dir=gold,
            reports_dir=reports,
            fair_manifest_path=fair,
            output_dir=tmp_path / "manuscript",
            strict_provenance=True,
        )


def test_build_manuscript_package_rejects_zero_gene_inventory(tmp_path: Path) -> None:
    gold, reports, fair = _write_fixture(tmp_path)
    cohort_path = gold / "gold_cohort_summary.parquet"
    pl.read_parquet(cohort_path).with_columns(pl.lit(0).alias("gene_count")).write_parquet(
        cohort_path
    )

    with pytest.raises(RuntimeError, match="non-zero cohort gene count"):
        build_manuscript_package(
            gold_dir=gold,
            reports_dir=reports,
            fair_manifest_path=fair,
            output_dir=tmp_path / "manuscript",
            strict_provenance=False,
        )
