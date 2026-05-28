from pathlib import Path

import polars as pl

from src.common.config import load_config
from src.processing.expression_loaders import load_gtex_expression_table, load_tcga_expression_table


def test_load_tcga_expression_table_from_file(tmp_path: Path) -> None:
    config = load_config("configs/project_config.yml")
    ingest_time = "2026-05-28T00:00:00Z"

    tcga_root = tmp_path / "tcga"
    expr_dir = tcga_root / "TCGA-BRCA" / "expression"
    expr_dir.mkdir(parents=True, exist_ok=True)
    expr_file = expr_dir / "sample_expr.tsv"
    expr_file.write_text(
        "sample_id\tgene_id\tgene_symbol\texpression_value\n"
        "TCGA-BRCA-SAMPLE-0001\tENSG00000141510.17\tTP53\t5.0\n",
        encoding="utf-8",
    )

    metadata_df = pl.DataFrame(
        {
            "project_id": ["TCGA-BRCA"],
            "case_id": ["TCGA-BRCA-CASE-0001"],
            "sample_id": ["TCGA-BRCA-SAMPLE-0001"],
            "sample_type": ["Primary Tumor"],
            "workflow_type": ["STAR - Counts"],
        }
    )

    df = load_tcga_expression_table(
        config=config,
        ingest_time=ingest_time,
        metadata_df=metadata_df,
        tcga_expression_dir=tcga_root,
    )
    assert df.height == 1
    row = df.row(0, named=True)
    assert row["project_id"] == "TCGA-BRCA"
    assert row["gene_id"] == "ENSG00000141510"
    assert row["gene_symbol"] == "TP53"
    assert row["expression_value"] == 5.0
    assert row["pipeline_workflow"] == "STAR - Counts"
    assert row["ingested_at"] == ingest_time


def test_load_gtex_expression_table_prefers_file_and_falls_back_to_stub(tmp_path: Path) -> None:
    config = load_config("configs/project_config.yml")
    ingest_time = "2026-05-28T00:00:00Z"

    gtex_expr_dir = tmp_path / "gtex" / "expression"
    gtex_expr_dir.mkdir(parents=True, exist_ok=True)
    file_path = gtex_expr_dir / "gtex_expr.tsv"
    file_path.write_text(
        "gtex_sample_id\ttissue_site\ttissue_detail\tgene_id\tgene_symbol\texpression_value\texpression_unit\tsource_version\n"
        "GTEX-LUNG-0001\tLung\tLung\tENSG00000141510.17\tTP53\t2.0\tTPM\tv8\n",
        encoding="utf-8",
    )

    df_file = load_gtex_expression_table(config=config, ingest_time=ingest_time, gtex_expression_dir=gtex_expr_dir)
    assert df_file.height == 1
    assert df_file.row(0, named=True)["data_origin"].endswith("gtex_expr.tsv")
    assert df_file.row(0, named=True)["gene_id"] == "ENSG00000141510"

    missing_dir = tmp_path / "missing"
    df_stub = load_gtex_expression_table(config=config, ingest_time=ingest_time, gtex_expression_dir=missing_dir)
    assert df_stub.height == len(config.gtex.tissues)
    assert set(df_stub["data_origin"].to_list()) == {"stub"}
