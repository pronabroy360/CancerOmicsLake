from pathlib import Path

import polars as pl
import pytest

from src.analytics.bootstrap_stability import build_bootstrap_stability, bootstrap_stability


def _write_fixture(root: Path) -> tuple[Path, Path]:
    silver = root / "silver"
    gold = root / "gold"
    silver.mkdir()
    gold.mkdir()
    pl.DataFrame(
        {
            "cancer_type": ["TCGA-BRCA", "TCGA-BRCA"],
            "gene_symbol": ["STABLE_UP", "VARIABLE"],
            "priority_score": [0.9, 0.8],
        }
    ).write_parquet(gold / "gold_candidate_gene_priority.parquet")
    pl.DataFrame(
        {
            "cancer_type": ["TCGA-BRCA"],
            "gene_symbol": ["VARIABLE"],
            "confidence_tier": ["high"],
        }
    ).write_parquet(gold / "gold_cancer_gene_evidence_confidence.parquet")

    tcga_rows: list[dict[str, object]] = []
    gtex_rows: list[dict[str, object]] = []
    for index in range(20):
        for gene, tumor, normal, healthy in [
            ("STABLE_UP", 20.0, 1.0, 1.0),
            ("VARIABLE", 2.0 if index % 2 else 10.0, 3.0, 3.0),
        ]:
            tcga_rows.extend(
                [
                    {
                        "project_id": "TCGA-BRCA",
                        "sample_id": f"tumor-{index}",
                        "sample_type": "Primary Tumor",
                        "gene_symbol": gene,
                        "expression_value": tumor,
                        "expression_unit": "TPM",
                    },
                    {
                        "project_id": "TCGA-BRCA",
                        "sample_id": f"normal-{index}",
                        "sample_type": "Solid Tissue Normal",
                        "gene_symbol": gene,
                        "expression_value": normal,
                        "expression_unit": "TPM",
                    },
                ]
            )
            gtex_rows.append(
                {
                    "gtex_sample_id": f"GTEX-{index}",
                    "tissue_site": "Breast - Mammary Tissue",
                    "gene_symbol": gene,
                    "expression_value": healthy,
                }
            )
    pl.DataFrame(tcga_rows).write_parquet(silver / "silver_expression_tcga.parquet")
    pl.DataFrame(gtex_rows).write_parquet(silver / "silver_expression_gtex.parquet")
    return silver, gold


def test_build_bootstrap_stability_is_deterministic(tmp_path: Path) -> None:
    silver, gold = _write_fixture(tmp_path)
    first = gold / "first.parquet"
    second = gold / "second.parquet"
    summary = build_bootstrap_stability(
        silver_dir=silver,
        gold_dir=gold,
        output_path=first,
        report_path=tmp_path / "first.json",
        candidates_per_cancer=2,
        iterations=40,
        top_k=1,
        random_seed=10,
    )
    build_bootstrap_stability(
        silver_dir=silver,
        gold_dir=gold,
        output_path=second,
        report_path=tmp_path / "second.json",
        candidates_per_cancer=2,
        iterations=40,
        top_k=1,
        random_seed=10,
    )

    assert summary["row_count"] == 2
    assert pl.read_parquet(first).equals(pl.read_parquet(second))
    stable = pl.read_parquet(first).filter(pl.col("gene_symbol") == "STABLE_UP").row(0, named=True)
    assert stable["tcga_direction_stability"] == 1.0
    assert stable["gtex_direction_stability"] == 1.0
    assert stable["reference_concordance_rate"] == 1.0


def test_bootstrap_stability_query_filters_results(tmp_path: Path) -> None:
    silver, gold = _write_fixture(tmp_path)
    output = gold / "bootstrap.parquet"
    build_bootstrap_stability(
        silver_dir=silver,
        gold_dir=gold,
        output_path=output,
        report_path=tmp_path / "report.json",
        candidates_per_cancer=2,
        iterations=20,
        top_k=1,
    )

    payload = bootstrap_stability(
        cancer_type="TCGA-BRCA",
        gene_query="stable",
        min_stability=0.5,
        gold_path=output,
    )
    assert payload["row_count"] == 1
    assert payload["rows"][0]["gene_symbol"] == "STABLE_UP"


def test_bootstrap_stability_forces_high_confidence_candidates_into_cohort(tmp_path: Path) -> None:
    silver, gold = _write_fixture(tmp_path)
    output = gold / "bootstrap.parquet"
    summary = build_bootstrap_stability(
        silver_dir=silver,
        gold_dir=gold,
        output_path=output,
        report_path=tmp_path / "report.json",
        candidates_per_cancer=1,
        iterations=20,
        top_k=1,
    )
    result = pl.read_parquet(output)

    assert summary["forced_high_confidence_count"] == 1
    assert result.height == 2
    forced = result.filter(pl.col("gene_symbol") == "VARIABLE").row(0, named=True)
    assert forced["candidate_selection_reason"] == "high_confidence"
    assert forced["evidence_confidence_tier"] == "high"


def test_bootstrap_stability_rejects_too_few_iterations(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="at least 20"):
        build_bootstrap_stability(
            silver_dir=tmp_path,
            gold_dir=tmp_path,
            iterations=5,
        )
