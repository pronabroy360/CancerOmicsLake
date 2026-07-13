from pathlib import Path

import polars as pl

from src.analytics.paired_expression import build_paired_expression_support, paired_expression_support


def _write_fixture(root: Path) -> tuple[Path, Path]:
    tcga_path = root / "tcga.parquet"
    external_path = root / "statistics.parquet"
    rows: list[dict[str, object]] = []
    for index in range(20):
        for gene, tumor, normal in [("MATCHED_UP", 30.0 + index, 1.0), ("OPPOSITE", 25.0 + index, 1.0)]:
            for sample_type, value in [("Primary Tumor", tumor), ("Solid Tissue Normal", normal)]:
                rows.append(
                    {
                        "project_id": "TCGA-BRCA",
                        "case_id": f"case-{index}",
                        "sample_type": sample_type,
                        "gene_symbol": gene,
                        "expression_value": value,
                    }
                )
    pl.DataFrame(rows).write_parquet(tcga_path)
    pl.DataFrame(
        [
            {
                "cancer_type": "TCGA-BRCA",
                "gene_symbol": "MATCHED_UP",
                "recount3_fdr_q_value": 0.001,
                "recount3_rank_biserial": 0.8,
            },
            {
                "cancer_type": "TCGA-BRCA",
                "gene_symbol": "OPPOSITE",
                "recount3_fdr_q_value": 0.001,
                "recount3_rank_biserial": -0.8,
            },
        ]
    ).write_parquet(external_path)
    return tcga_path, external_path


def test_paired_expression_scores_replication_and_discordance(tmp_path: Path) -> None:
    tcga, external = _write_fixture(tmp_path)
    output = tmp_path / "paired.parquet"
    summary = build_paired_expression_support(
        tcga_path=tcga,
        external_statistics_path=external,
        output_path=output,
        report_path=tmp_path / "report.json",
    )
    rows = {row["gene_symbol"]: row for row in pl.read_parquet(output).to_dicts()}

    assert summary["status"] == "completed"
    assert rows["MATCHED_UP"]["matched_case_count"] == 20
    assert rows["MATCHED_UP"]["paired_support_tier"] == "paired_replicated"
    assert rows["MATCHED_UP"]["paired_fdr_q_value"] <= 0.05
    assert rows["MATCHED_UP"]["paired_rank_biserial"] > 0
    assert rows["OPPOSITE"]["paired_support_tier"] == "paired_discordant"
    assert rows["OPPOSITE"]["paired_support_score"] == 0.0


def test_paired_expression_query_filters_rows(tmp_path: Path) -> None:
    tcga, external = _write_fixture(tmp_path)
    output = tmp_path / "paired.parquet"
    build_paired_expression_support(
        tcga_path=tcga,
        external_statistics_path=external,
        output_path=output,
        report_path=tmp_path / "report.json",
    )

    payload = paired_expression_support(
        cancer_type="TCGA-BRCA",
        gene_query="matched",
        support_tier="paired_replicated",
        max_fdr=0.05,
        gold_path=output,
    )

    assert payload["row_count"] == 1
    assert payload["rows"][0]["gene_symbol"] == "MATCHED_UP"


def test_paired_expression_requires_minimum_matched_cases(tmp_path: Path) -> None:
    tcga = tmp_path / "tcga.parquet"
    pl.DataFrame(
        [
            {
                "project_id": "TCGA-BRCA",
                "case_id": f"case-{index}",
                "sample_type": sample_type,
                "gene_symbol": "GENE",
                "expression_value": value,
            }
            for index in range(5)
            for sample_type, value in [("Primary Tumor", 10.0), ("Solid Tissue Normal", 1.0)]
        ]
    ).write_parquet(tcga)
    output = tmp_path / "paired.parquet"
    summary = build_paired_expression_support(
        tcga_path=tcga,
        external_statistics_path=tmp_path / "missing.parquet",
        output_path=output,
        report_path=tmp_path / "report.json",
    )

    assert summary["status"] == "skipped_insufficient_matched_cases"
    assert pl.read_parquet(output).is_empty()
