from __future__ import annotations

import gzip
from pathlib import Path

import polars as pl

from src.ingestion.recount3_expression import (
    COHORTS,
    _cohort_urls,
    _harmonize_cohort,
    _parse_gene_annotation,
    _read_selected_samples,
)


def _write_gzip(path: Path, content: str) -> None:
    with gzip.open(path, "wt", encoding="utf-8") as stream:
        stream.write(content)


def test_cohort_urls_are_stable_public_release_paths() -> None:
    urls = _cohort_urls(COHORTS[0], "https://example.test/release")

    assert urls["counts"].endswith("/gene_sums/CA/BRCA/tcga.gene_sums.BRCA.G026.gz")
    assert urls["metadata"].endswith("/metadata/CA/BRCA/tcga.tcga.BRCA.MD.gz")
    assert urls["qc"].endswith("/metadata/CA/BRCA/tcga.recount_qc.BRCA.MD.gz")


def test_annotation_and_auc_scaling_produce_validation_contract(tmp_path: Path) -> None:
    annotation_path = tmp_path / "annotation.gtf.gz"
    _write_gzip(
        annotation_path,
        'chr1\tHAVANA\tgene\t1\t10\t.\t+\t.\tgene_id "ENSG1.2"; gene_name "GeneA";\n',
    )
    annotation = _parse_gene_annotation(annotation_path)
    counts_path = tmp_path / "counts.gz"
    _write_gzip(
        counts_path,
        "##annotation=G026\n##date.generated=test\ngene_id\tsample-1\nENSG1.2\t20\n",
    )
    selected = pl.DataFrame(
        {
            "external_id": ["sample-1"],
            "sample_type": ["Primary Tumor"],
            "tissue_site": [""],
            "project_id": ["TCGA-BRCA"],
            "auc": [80_000_000.0],
        }
    )

    result = _harmonize_cohort(COHORTS[0], counts_path, selected, annotation)

    assert result.schema == {
        "source": pl.String,
        "project_id": pl.String,
        "sample_id": pl.String,
        "sample_type": pl.String,
        "tissue_site": pl.String,
        "gene_id": pl.String,
        "gene_symbol": pl.String,
        "expression_value": pl.Float64,
        "expression_unit": pl.String,
        "external_annotation": pl.String,
    }
    assert result.row(0, named=True)["gene_symbol"] == "GENEA"
    assert result.row(0, named=True)["gene_id"] == "ENSG1"
    assert result.row(0, named=True)["expression_value"] == 10.0


def test_sample_selection_is_filtered_sorted_and_capped(tmp_path: Path) -> None:
    metadata_path = tmp_path / "metadata.gz"
    qc_path = tmp_path / "qc.gz"
    _write_gzip(
        metadata_path,
        "external_id\tcgc_sample_sample_type\n"
        "sample-b\tPrimary Tumor\n"
        "sample-normal\tSolid Tissue Normal\n"
        "sample-a\tPrimary Tumor\n",
    )
    _write_gzip(
        qc_path,
        "external_id\tbc_auc.all_reads_all_bases\n"
        "sample-a\t100\n"
        "sample-b\t200\n"
        "sample-normal\t300\n",
    )

    result = _read_selected_samples(COHORTS[0], metadata_path, qc_path, sample_cap=1)

    assert result.get_column("external_id").to_list() == ["sample-a"]
    assert result.get_column("project_id").to_list() == ["TCGA-BRCA"]
