from __future__ import annotations

import gzip
import hashlib
from pathlib import Path

import polars as pl
import pytest

from src.common.config import load_config
from src.ingestion import gtex_downloader
from src.ingestion.gtex_downloader import build_gtex_download_plan, download_gtex_files
from src.processing.gtex_harmonizer import harmonize_gtex_gct_files


def _configure_one_tissue():
    config = load_config("configs/project_config.yml")
    config.gtex.tissues = ["Lung"]
    config.gtex.tissue_files = {"Lung": "lung.gct.gz"}
    config.gtex.sample_attributes_url = "https://example.test/SampleAttributes.txt"
    return config


def _write_gct(path: Path) -> None:
    with gzip.open(path, "wt", encoding="utf-8") as stream:
        stream.write("#1.3\n")
        stream.write("2\t3\t0\t0\n")
        stream.write("id\tName\tDescription\tGTEX-AAAA-0001-SM-X\tGTEX-BBBB-0001-SM-X\tGTEX-CCCC-0001-SM-X\n")
        stream.write("0\tENSG000001.7\tGENE1\t1.0\t2.0\t3.0\n")
        stream.write("1\tENSG000002.3\tGENE2\t0.0\t4.0\t5.0\n")


def _write_metadata(path: Path, tissue: str = "Lung") -> None:
    path.write_text(
        "SAMPID\tSMTSD\n"
        f"GTEX-AAAA-0001-SM-X\t{tissue}\n"
        f"GTEX-BBBB-0001-SM-X\t{tissue}\n"
        f"GTEX-CCCC-0001-SM-X\t{tissue}\n",
        encoding="utf-8",
    )


def test_build_gtex_download_plan_is_config_driven() -> None:
    config = _configure_one_tissue()
    plan = build_gtex_download_plan(config)

    assert [row["kind"] for row in plan] == ["sample_attributes", "expression"]
    assert plan[1]["url"].endswith("/lung.gct.gz")
    assert plan[1]["tissue"] == "Lung"


def test_download_gtex_files_verifies_remote_metadata(tmp_path: Path, monkeypatch) -> None:
    config = _configure_one_tissue()
    config.gtex.metadata_only = False
    payloads = {
        "SampleAttributes.txt": b"SAMPID\tSMTSD\n",
        "lung.gct.gz": b"compressed-gct",
    }

    def remote(url: str, timeout_sec: int) -> dict[str, object]:
        data = payloads[Path(url).name]
        return {
            "content_length": len(data),
            "md5": hashlib.md5(data).hexdigest(),
            "etag": "fixture",
            "last_modified": "now",
        }

    def download(url: str, destination: Path, timeout_sec: int) -> int:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(payloads[Path(url).name])
        return destination.stat().st_size

    monkeypatch.setattr(gtex_downloader, "_remote_metadata", remote)
    monkeypatch.setattr(gtex_downloader, "_stream_download", download)
    report = tmp_path / "report.json"
    summary = download_gtex_files(config, output_dir=tmp_path / "bronze", report_path=report)

    assert summary["status"] == "completed"
    assert summary["downloaded_count"] == 2
    assert summary["failed_count"] == 0
    assert report.exists()


def test_harmonize_gtex_gct_files_caps_samples_and_normalizes_genes(tmp_path: Path) -> None:
    config = _configure_one_tissue()
    source = tmp_path / "lung.gct.gz"
    metadata = tmp_path / "SampleAttributes.txt"
    output = tmp_path / "silver_gtex.parquet"
    _write_gct(source)
    _write_metadata(metadata)

    summary = harmonize_gtex_gct_files(
        config,
        input_dir=tmp_path,
        output_path=output,
        report_path=tmp_path / "harmonization.json",
        sample_cap_per_tissue=2,
        gene_batch_size=1,
    )
    result = pl.read_parquet(output)

    assert summary["selected_sample_count"] == 2
    assert summary["total_rows"] == 4
    assert result.get_column("gene_id").unique().sort().to_list() == ["ENSG000001", "ENSG000002"]
    assert result.get_column("donor_id").unique().sort().to_list() == ["GTEX-AAAA", "GTEX-BBBB"]
    assert result.get_column("expression_unit").unique().to_list() == ["TPM"]
    assert result.get_column("data_origin").str.ends_with("lung.gct.gz").all()


def test_harmonize_gtex_rejects_tissue_metadata_mismatch(tmp_path: Path) -> None:
    config = _configure_one_tissue()
    _write_gct(tmp_path / "lung.gct.gz")
    _write_metadata(tmp_path / "SampleAttributes.txt", tissue="Breast - Mammary Tissue")

    with pytest.raises(ValueError, match="tissue mismatch"):
        harmonize_gtex_gct_files(
            config,
            input_dir=tmp_path,
            output_path=tmp_path / "silver.parquet",
            sample_cap_per_tissue=2,
        )
