from pathlib import Path

import polars as pl
import pytest

from src.analytics.external_validation import (
    build_external_expression_validation,
    external_expression_validation,
)


def _write_fixture(root: Path) -> tuple[Path, Path]:
    gold = root / "gold"
    silver = root / "silver"
    gold.mkdir()
    silver.mkdir()
    pl.DataFrame(
        {
            "cancer_type": ["TCGA-BRCA", "TCGA-BRCA", "TCGA-BRCA"],
            "gene_symbol": ["STABLE_UP", "DISCORDANT", "WEAK"],
            "log2_fold_change": [3.0, 2.0, 0.2],
            "sample_count_tumor": [50, 50, 50],
            "sample_count_normal": [50, 50, 50],
        }
    ).write_parquet(gold / "gold_tumor_vs_normal_expression.parquet")

    rows: list[dict[str, object]] = []
    for index in range(12):
        for gene, tumor, normal in [
            ("STABLE_UP", 32.0, 1.0),
            ("DISCORDANT", 1.0, 32.0),
            ("WEAK", 4.0, 3.0),
        ]:
            rows.append(
                {
                    "source": "TCGA",
                    "project_id": "TCGA-BRCA",
                    "sample_id": f"TCGA-{index}",
                    "sample_type": "Primary Tumor",
                    "gene_symbol": gene,
                    "expression_value": tumor,
                    "external_annotation": "recount3_test",
                }
            )
            rows.append(
                {
                    "source": "GTEx",
                    "sample_id": f"GTEX-{index}",
                    "tissue_site": "Breast - Mammary Tissue",
                    "gene_symbol": gene,
                    "expression_value": normal,
                    "external_annotation": "recount3_test",
                }
            )
    path = silver / "silver_expression_recount3.parquet"
    pl.DataFrame(rows).write_parquet(path)
    return gold, path


def test_build_external_expression_validation_scores_concordance(tmp_path: Path) -> None:
    gold, recount3_path = _write_fixture(tmp_path)
    output = gold / "external.parquet"
    summary = build_external_expression_validation(
        gold_dir=gold,
        recount3_expression_path=recount3_path,
        output_path=output,
        report_path=tmp_path / "report.json",
        top_k=2,
    )
    result = pl.read_parquet(output)
    rows = {row["gene_symbol"]: row for row in result.to_dicts()}

    assert summary["status"] == "completed"
    assert summary["row_count"] == 3
    assert rows["STABLE_UP"]["direction_agreement"] == "concordant"
    assert rows["STABLE_UP"]["validation_tier"] == "high"
    assert rows["DISCORDANT"]["direction_agreement"] == "discordant"
    assert rows["DISCORDANT"]["validation_score"] < rows["STABLE_UP"]["validation_score"]
    assert rows["STABLE_UP"]["top_k_jaccard_by_cancer"] == pytest.approx(1.0)


def test_external_expression_validation_query_filters_rows(tmp_path: Path) -> None:
    gold, recount3_path = _write_fixture(tmp_path)
    output = gold / "external.parquet"
    build_external_expression_validation(
        gold_dir=gold,
        recount3_expression_path=recount3_path,
        output_path=output,
        report_path=tmp_path / "report.json",
        top_k=2,
    )

    payload = external_expression_validation(
        cancer_type="TCGA-BRCA",
        gene_query="stable",
        validation_tier="high",
        min_validation_score=0.8,
        gold_path=output,
    )

    assert payload["row_count"] == 1
    assert payload["rows"][0]["gene_symbol"] == "STABLE_UP"


def test_external_expression_validation_missing_extract_writes_empty_contract(tmp_path: Path) -> None:
    gold = tmp_path / "gold"
    gold.mkdir()
    pl.DataFrame(
        {
            "cancer_type": ["TCGA-BRCA"],
            "gene_symbol": ["TP53"],
            "log2_fold_change": [1.2],
            "sample_count_tumor": [10],
            "sample_count_normal": [10],
        }
    ).write_parquet(gold / "gold_tumor_vs_normal_expression.parquet")

    output = gold / "external.parquet"
    summary = build_external_expression_validation(
        gold_dir=gold,
        recount3_expression_path=tmp_path / "missing.parquet",
        output_path=output,
        report_path=tmp_path / "report.json",
    )

    assert summary["status"] == "skipped_missing_inputs"
    assert pl.read_parquet(output).is_empty()
