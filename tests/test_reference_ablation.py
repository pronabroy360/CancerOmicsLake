from pathlib import Path

import polars as pl
import pytest

from src.analytics.consensus_candidates import CONSENSUS_COMPONENT_WEIGHTS
from src.analytics.reference_ablation import (
    build_consensus_component_ablation,
    build_reference_ablation_evaluation,
    build_reference_method_comparison,
)


def _reference_fixture() -> tuple[pl.DataFrame, pl.DataFrame]:
    reference = pl.DataFrame(
        {
            "cancer_type": ["TCGA-BRCA"] * 5,
            "gene_symbol": ["A", "B", "C", "D", "E"],
            "log2_fc_tumor_vs_gtex": [5.0, 4.0, 3.0, 2.0, 1.0],
            "log2_fc_tumor_vs_tcga_normal": [5.0, 4.0, -3.0, 1.0, 0.0],
        }
    )
    external = pl.DataFrame(
        {
            "cancer_type": ["TCGA-BRCA"] * 5,
            "gene_symbol": ["A", "B", "C", "D", "E"],
            "recount3_log2_fold_change": [5.0, 4.0, 2.0, -3.0, 1.0],
        }
    )
    return reference, external


def _consensus_fixture() -> pl.DataFrame:
    rows = []
    for index, gene in enumerate(["A", "B", "C", "D", "E"], start=1):
        row = {
            "cancer_type": "TCGA-BRCA",
            "gene_symbol": gene,
            "consensus_score": 1.0 - index * 0.1,
            "consensus_decision": "prioritized" if index <= 2 else "deprioritized",
        }
        for component in CONSENSUS_COMPONENT_WEIGHTS:
            row[component] = 1.0 - index * 0.08
        row["external_component"] = 0.0 if gene == "A" else row["external_component"]
        rows.append(row)
    return pl.DataFrame(rows)


def test_reference_comparison_uses_common_deterministic_top_k() -> None:
    reference, external = _reference_fixture()

    result = build_reference_method_comparison(reference, external, top_k=2)

    assert result.height == 3
    assert result.get_column("common_gene_count").unique().to_list() == [5]
    assert result.get_column("top_k").unique().to_list() == [2]
    gtex_adjacent = result.filter(
        (pl.col("method_a") == "gtex_native")
        & (pl.col("method_b") == "tcga_adjacent")
    ).row(0, named=True)
    assert gtex_adjacent["top_k_overlap_count"] == 2
    assert gtex_adjacent["top_k_jaccard"] == 1.0
    assert gtex_adjacent["universe_direction_concordance"] == pytest.approx(0.6)
    assert gtex_adjacent["regulated_direction_concordance"] == pytest.approx(0.6)


def test_consensus_ablation_renormalizes_and_reports_rank_sensitivity() -> None:
    result = build_consensus_component_ablation(_consensus_fixture(), top_k=2)

    assert result.height == 4
    external = result.filter(
        pl.col("ablation_scenario") == "without_external_validation"
    ).row(0, named=True)
    assert external["retained_weight"] == pytest.approx(0.85)
    assert 0.0 <= external["top_k_jaccard"] <= 1.0
    assert 0.0 <= external["fixed_threshold_retention_rate"] <= 1.0
    assert external["max_absolute_score_delta"] > 0.0


def test_reference_ablation_builder_writes_typed_outputs_and_report(
    tmp_path: Path,
) -> None:
    gold = tmp_path / "gold"
    gold.mkdir()
    reference, external = _reference_fixture()
    reference.write_parquet(gold / "gold_reference_triangulation.parquet")
    external.write_parquet(gold / "gold_external_expression_validation.parquet")
    _consensus_fixture().write_parquet(gold / "gold_consensus_candidate_genes.parquet")
    comparison_path = gold / "comparison.parquet"
    ablation_path = gold / "ablation.parquet"
    report_path = tmp_path / "report.json"

    summary = build_reference_ablation_evaluation(
        gold_dir=gold,
        comparison_output_path=comparison_path,
        ablation_output_path=ablation_path,
        report_path=report_path,
        top_k=2,
    )

    assert summary["status"] == "completed"
    assert summary["top_k_values"] == [2]
    assert summary["reference_comparison_rows"] == 3
    assert summary["consensus_ablation_rows"] == 4
    assert len(summary["input_resources"]) == 3
    assert all(
        len(resource["sha256"]) == 64 for resource in summary["input_resources"]
    )
    assert summary["evaluation_parameters"]["direction_threshold_absolute_log2_fc"] == 1.0
    assert comparison_path.exists()
    assert ablation_path.exists()
    assert report_path.exists()


def test_reference_ablation_builder_handles_missing_inputs(tmp_path: Path) -> None:
    summary = build_reference_ablation_evaluation(
        gold_dir=tmp_path / "gold",
        comparison_output_path=tmp_path / "comparison.parquet",
        ablation_output_path=tmp_path / "ablation.parquet",
        report_path=tmp_path / "report.json",
    )

    assert summary["status"] == "skipped_missing_inputs"
    assert summary["missing_inputs"] == ["reference", "external", "consensus"]


def test_reference_ablation_rejects_invalid_parameters() -> None:
    with pytest.raises(ValueError, match="top_k values must be positive"):
        build_reference_ablation_evaluation(top_k=0)
    with pytest.raises(ValueError, match="either top_k or top_k_values"):
        build_reference_ablation_evaluation(top_k=10, top_k_values=[10, 20])


def test_reference_ablation_evaluates_multiple_top_k_values(tmp_path: Path) -> None:
    gold = tmp_path / "gold"
    gold.mkdir()
    reference, external = _reference_fixture()
    reference.write_parquet(gold / "gold_reference_triangulation.parquet")
    external.write_parquet(gold / "gold_external_expression_validation.parquet")
    _consensus_fixture().write_parquet(gold / "gold_consensus_candidate_genes.parquet")

    summary = build_reference_ablation_evaluation(
        gold_dir=gold,
        comparison_output_path=tmp_path / "comparison.parquet",
        ablation_output_path=tmp_path / "ablation.parquet",
        report_path=tmp_path / "report.json",
        top_k_values=[1, 2],
    )

    assert summary["top_k_values"] == [1, 2]
    assert summary["reference_comparison_rows"] == 6
    assert summary["consensus_ablation_rows"] == 8
