from pathlib import Path

import polars as pl

from src.analytics.expression_statistics import (
    build_expression_statistical_support,
    expression_statistical_support,
)


def _write_expression_fixtures(root: Path) -> tuple[Path, Path, Path]:
    tcga_path = root / "tcga.parquet"
    gtex_path = root / "gtex.parquet"
    recount3_path = root / "recount3.parquet"
    tcga_rows: list[dict[str, object]] = []
    gtex_rows: list[dict[str, object]] = []
    recount3_rows: list[dict[str, object]] = []
    for index in range(10):
        for gene, tumor, normal in [("UP", 20.0 + index, 1.0), ("DISCORDANT", 18.0 + index, 1.0)]:
            tcga_rows.append(
                {
                    "project_id": "TCGA-BRCA",
                    "sample_type": "Primary Tumor",
                    "gene_symbol": gene,
                    "expression_value": tumor,
                }
            )
            gtex_rows.append(
                {
                    "tissue_site": "Breast - Mammary Tissue",
                    "gene_symbol": gene,
                    "expression_value": normal,
                }
            )
            recount3_rows.extend(
                [
                    {
                        "source": "TCGA",
                        "project_id": "TCGA-BRCA",
                        "sample_type": "Primary Tumor",
                        "tissue_site": "",
                        "gene_symbol": gene,
                        "expression_value": tumor if gene == "UP" else normal,
                    },
                    {
                        "source": "GTEX",
                        "project_id": "",
                        "sample_type": "Normal",
                        "tissue_site": "Breast - Mammary Tissue",
                        "gene_symbol": gene,
                        "expression_value": normal if gene == "UP" else tumor,
                    },
                ]
            )
    pl.DataFrame(tcga_rows).write_parquet(tcga_path)
    pl.DataFrame(gtex_rows).write_parquet(gtex_path)
    pl.DataFrame(recount3_rows).write_parquet(recount3_path)
    return tcga_path, gtex_path, recount3_path


def test_expression_statistics_fdr_and_direction_support(tmp_path: Path) -> None:
    tcga, gtex, recount3 = _write_expression_fixtures(tmp_path)
    output = tmp_path / "statistics.parquet"
    summary = build_expression_statistical_support(
        tcga_path=tcga,
        gtex_path=gtex,
        recount3_path=recount3,
        output_path=output,
        report_path=tmp_path / "report.json",
    )
    rows = {row["gene_symbol"]: row for row in pl.read_parquet(output).to_dicts()}

    assert summary["status"] == "completed"
    assert rows["UP"]["statistical_support_tier"] == "replicated_fdr"
    assert rows["UP"]["native_fdr_q_value"] <= 0.05
    assert rows["UP"]["recount3_fdr_q_value"] <= 0.05
    assert rows["UP"]["native_rank_biserial"] > 0
    assert rows["DISCORDANT"]["statistical_support_tier"] == "discordant"
    assert rows["DISCORDANT"]["statistical_support_score"] == 0.0


def test_expression_statistics_query_filters(tmp_path: Path) -> None:
    tcga, gtex, recount3 = _write_expression_fixtures(tmp_path)
    output = tmp_path / "statistics.parquet"
    build_expression_statistical_support(
        tcga_path=tcga,
        gtex_path=gtex,
        recount3_path=recount3,
        output_path=output,
        report_path=tmp_path / "report.json",
    )

    payload = expression_statistical_support(
        cancer_type="TCGA-BRCA",
        gene_query="up",
        support_tier="replicated_fdr",
        max_fdr=0.05,
        gold_path=output,
    )

    assert payload["row_count"] == 1
    assert payload["rows"][0]["gene_symbol"] == "UP"


def test_expression_statistics_missing_inputs_writes_empty_contract(tmp_path: Path) -> None:
    output = tmp_path / "statistics.parquet"
    summary = build_expression_statistical_support(
        tcga_path=tmp_path / "missing-tcga.parquet",
        gtex_path=tmp_path / "missing-gtex.parquet",
        recount3_path=tmp_path / "missing-recount3.parquet",
        output_path=output,
        report_path=tmp_path / "report.json",
    )

    assert summary["status"] == "skipped_missing_or_nonoverlapping_inputs"
    assert pl.read_parquet(output).is_empty()
