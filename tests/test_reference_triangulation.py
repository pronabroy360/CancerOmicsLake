from pathlib import Path

import polars as pl

from src.analytics.reference_triangulation import (
    build_reference_triangulation_table,
    reference_triangulation,
)


def _expression_fixtures() -> tuple[pl.DataFrame, pl.DataFrame]:
    genes = {
        "UP": (15.0, 1.0, 1.0),
        "SENSITIVE": (15.0, 15.0, 1.0),
        "DISCORDANT": (1.0, 15.0, 0.0),
    }
    tcga_rows: list[dict[str, object]] = []
    gtex_rows: list[dict[str, object]] = []
    for gene, (tumor_value, tcga_normal_value, gtex_value) in genes.items():
        for index in range(30):
            tcga_rows.extend(
                [
                    {
                        "project_id": "TCGA-BRCA",
                        "sample_id": f"tumor-{index}",
                        "sample_type": "Primary Tumor",
                        "gene_id": f"ENSG-{gene}",
                        "gene_symbol": gene,
                        "expression_value": tumor_value,
                        "expression_unit": "TPM",
                        "pipeline_workflow": "STAR - Counts",
                        "data_origin": "gdc_download",
                    },
                    {
                        "project_id": "TCGA-BRCA",
                        "sample_id": f"normal-{index}",
                        "sample_type": "Solid Tissue Normal",
                        "gene_id": f"ENSG-{gene}",
                        "gene_symbol": gene,
                        "expression_value": tcga_normal_value,
                        "expression_unit": "TPM",
                        "pipeline_workflow": "STAR - Counts",
                        "data_origin": "gdc_download",
                    },
                ]
            )
            gtex_rows.append(
                {
                    "gtex_sample_id": f"GTEX-{index}",
                    "tissue_site": "Breast - Mammary Tissue",
                    "gene_symbol": gene,
                    "expression_value": gtex_value,
                }
            )
    return pl.DataFrame(tcga_rows), pl.DataFrame(gtex_rows)


def test_reference_triangulation_classifies_reference_agreement() -> None:
    tcga, gtex = _expression_fixtures()
    result = build_reference_triangulation_table(tcga, gtex)

    assert result.height == 3
    rows = {row["gene_symbol"]: row for row in result.to_dicts()}
    assert rows["UP"]["reference_concordance"] == "concordant_up"
    assert rows["UP"]["tcga_normal_support_tier"] == "high"
    assert rows["UP"]["reference_stability_score"] == 1.0
    assert rows["SENSITIVE"]["reference_concordance"] == "reference_sensitive"
    assert rows["DISCORDANT"]["reference_concordance"] == "discordant"
    assert rows["DISCORDANT"]["reference_stability_score"] == 0.0


def test_reference_triangulation_query_filters_rows(tmp_path: Path) -> None:
    tcga, gtex = _expression_fixtures()
    path = tmp_path / "triangulation.parquet"
    build_reference_triangulation_table(tcga, gtex).write_parquet(path)

    payload = reference_triangulation(
        cancer_type="TCGA-BRCA",
        concordance="concordant_up",
        support_tier="high",
        min_stability=0.9,
        gold_path=path,
    )

    assert payload["row_count"] == 1
    assert payload["rows"][0]["gene_symbol"] == "UP"


def test_reference_triangulation_requires_adjacent_normal_rows() -> None:
    tcga, gtex = _expression_fixtures()
    tumor_only = tcga.filter(pl.col("sample_type") == "Primary Tumor")
    assert build_reference_triangulation_table(tumor_only, gtex).is_empty()
