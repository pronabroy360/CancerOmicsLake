from pathlib import Path

from src.common.config import load_config
from src.ingestion import tcga_downloader


def _write_metadata_csv(path: Path, rows: list[dict[str, str]]) -> None:
    headers = list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as f:
        f.write(",".join(headers) + "\n")
        for row in rows:
            f.write(",".join(row[h] for h in headers) + "\n")


def test_download_tcga_files_skips_in_metadata_only_mode(tmp_path: Path) -> None:
    cfg = load_config("configs/project_config.yml")
    cfg.tcga.metadata_only = True
    report = tmp_path / "report.json"
    retry_log = tmp_path / "retry.json"

    summary = tcga_downloader.download_tcga_files(
        config=cfg,
        metadata_csv_path=tmp_path / "missing.csv",
        report_path=report,
        retry_log_path=retry_log,
    )
    assert summary["status"] == "skipped_metadata_only"
    assert report.exists()
    assert retry_log.exists()


def test_download_tcga_files_downloads_and_organizes_by_category(tmp_path: Path, monkeypatch) -> None:
    cfg = load_config("configs/project_config.yml")
    cfg.tcga.metadata_only = False
    cfg.gdc_api.retry_count = 0
    metadata = tmp_path / "tcga_metadata_live.csv"

    expr_bytes = b"sample_id\tgene_id\texpression_value\ns1\tENSG1\t1.0\n"
    mut_bytes = b"Hugo_Symbol\tTumor_Sample_Barcode\tStart_Position\nTP53\ts1\t1\n"
    expr_md5 = "b6d730b9ce47bcb247c42a8cb7f57203"
    mut_md5 = "17aec26147df2a46f6a928d107881479"

    _write_metadata_csv(
        metadata,
        [
            {
                "project_id": "TCGA-BRCA",
                "case_id": "case-1",
                "submitter_id": "sub-1",
                "sample_id": "sample-1",
                "sample_type": "Primary Tumor",
                "primary_site": "Breast",
                "disease_type": "Adeno",
                "file_id": "expr-id",
                "file_name": "expr.tsv",
                "data_category": "Transcriptome Profiling",
                "data_type": "Gene Expression Quantification",
                "experimental_strategy": "RNA-Seq",
                "workflow_type": "STAR",
                "access": "open",
                "file_size": str(len(expr_bytes)),
                "md5sum": expr_md5,
            },
            {
                "project_id": "TCGA-BRCA",
                "case_id": "case-1",
                "submitter_id": "sub-1",
                "sample_id": "sample-1",
                "sample_type": "Primary Tumor",
                "primary_site": "Breast",
                "disease_type": "Adeno",
                "file_id": "mut-id",
                "file_name": "mut.maf",
                "data_category": "Simple Nucleotide Variation",
                "data_type": "Masked Somatic Mutation",
                "experimental_strategy": "WXS",
                "workflow_type": "Mutect2",
                "access": "open",
                "file_size": str(len(mut_bytes)),
                "md5sum": mut_md5,
            },
            {
                "project_id": "TCGA-BRCA",
                "case_id": "case-1",
                "submitter_id": "sub-1",
                "sample_id": "sample-1",
                "sample_type": "Primary Tumor",
                "primary_site": "Breast",
                "disease_type": "Adeno",
                "file_id": "blocked-id",
                "file_name": "blocked.tsv",
                "data_category": "Clinical",
                "data_type": "Clinical Supplement",
                "experimental_strategy": "RNA-Seq",
                "workflow_type": "N/A",
                "access": "controlled",
                "file_size": "1",
                "md5sum": "",
            },
        ],
    )

    def fake_fetch(url: str, destination: Path, timeout_sec: int) -> None:  # noqa: ARG001
        if url.endswith("/expr-id"):
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(expr_bytes)
            return
        if url.endswith("/mut-id"):
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(mut_bytes)
            return
        raise RuntimeError("unexpected url")

    monkeypatch.setattr(tcga_downloader, "_fetch_to_path", fake_fetch)
    summary = tcga_downloader.download_tcga_files(
        config=cfg,
        metadata_csv_path=metadata,
        bronze_tcga_root=tmp_path / "bronze" / "tcga",
        report_path=tmp_path / "report.json",
        retry_log_path=tmp_path / "retry.json",
    )
    assert summary["downloaded_count"] == 2
    assert summary["failed_count"] == 0
    assert (tmp_path / "bronze" / "tcga" / "TCGA-BRCA" / "expression" / "expr.tsv").exists()
    assert (tmp_path / "bronze" / "tcga" / "TCGA-BRCA" / "mutations" / "mut.maf").exists()


def test_download_tcga_files_fails_on_checksum_mismatch(tmp_path: Path, monkeypatch) -> None:
    cfg = load_config("configs/project_config.yml")
    cfg.tcga.metadata_only = False
    cfg.gdc_api.retry_count = 0
    metadata = tmp_path / "tcga_metadata_live.csv"

    _write_metadata_csv(
        metadata,
        [
            {
                "project_id": "TCGA-LUAD",
                "case_id": "case-2",
                "submitter_id": "sub-2",
                "sample_id": "sample-2",
                "sample_type": "Primary Tumor",
                "primary_site": "Lung",
                "disease_type": "Adeno",
                "file_id": "bad-id",
                "file_name": "bad.tsv",
                "data_category": "Transcriptome Profiling",
                "data_type": "Gene Expression Quantification",
                "experimental_strategy": "RNA-Seq",
                "workflow_type": "STAR",
                "access": "open",
                "file_size": "4",
                "md5sum": "00000000000000000000000000000000",
            }
        ],
    )

    def fake_fetch(url: str, destination: Path, timeout_sec: int) -> None:  # noqa: ARG001
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(b"real-bytes")

    monkeypatch.setattr(tcga_downloader, "_fetch_to_path", fake_fetch)
    summary = tcga_downloader.download_tcga_files(
        config=cfg,
        metadata_csv_path=metadata,
        bronze_tcga_root=tmp_path / "bronze" / "tcga",
        report_path=tmp_path / "report.json",
        retry_log_path=tmp_path / "retry.json",
    )
    assert summary["failed_count"] == 1
    assert summary["checksum_mismatch_count"] == 1
    assert not (tmp_path / "bronze" / "tcga" / "TCGA-LUAD" / "expression" / "bad.tsv").exists()


def test_download_tcga_files_respects_max_downloads_and_subdir_filters(tmp_path: Path, monkeypatch) -> None:
    cfg = load_config("configs/project_config.yml")
    cfg.tcga.metadata_only = False
    cfg.gdc_api.retry_count = 0
    metadata = tmp_path / "tcga_metadata_live.csv"

    payload = b"ok"
    md5 = "444bcb3a3fcf8389296c49467f27e1d6"
    _write_metadata_csv(
        metadata,
        [
            {
                "project_id": "TCGA-BRCA",
                "case_id": "case-1",
                "submitter_id": "sub-1",
                "sample_id": "sample-1",
                "sample_type": "Primary Tumor",
                "primary_site": "Breast",
                "disease_type": "Adeno",
                "file_id": "expr-1",
                "file_name": "expr1.tsv",
                "data_category": "Transcriptome Profiling",
                "data_type": "Gene Expression Quantification",
                "experimental_strategy": "RNA-Seq",
                "workflow_type": "STAR",
                "access": "open",
                "file_size": str(len(payload)),
                "md5sum": md5,
            },
            {
                "project_id": "TCGA-BRCA",
                "case_id": "case-1",
                "submitter_id": "sub-1",
                "sample_id": "sample-1",
                "sample_type": "Primary Tumor",
                "primary_site": "Breast",
                "disease_type": "Adeno",
                "file_id": "expr-2",
                "file_name": "expr2.tsv",
                "data_category": "Transcriptome Profiling",
                "data_type": "Gene Expression Quantification",
                "experimental_strategy": "RNA-Seq",
                "workflow_type": "STAR",
                "access": "open",
                "file_size": str(len(payload)),
                "md5sum": md5,
            },
            {
                "project_id": "TCGA-BRCA",
                "case_id": "case-1",
                "submitter_id": "sub-1",
                "sample_id": "sample-1",
                "sample_type": "Primary Tumor",
                "primary_site": "Breast",
                "disease_type": "Adeno",
                "file_id": "clin-1",
                "file_name": "clin.tsv",
                "data_category": "Clinical",
                "data_type": "Clinical Supplement",
                "experimental_strategy": "RNA-Seq",
                "workflow_type": "N/A",
                "access": "open",
                "file_size": str(len(payload)),
                "md5sum": md5,
            },
        ],
    )

    def fake_fetch(url: str, destination: Path, timeout_sec: int) -> None:  # noqa: ARG001
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(payload)

    monkeypatch.setattr(tcga_downloader, "_fetch_to_path", fake_fetch)
    summary = tcga_downloader.download_tcga_files(
        config=cfg,
        metadata_csv_path=metadata,
        bronze_tcga_root=tmp_path / "bronze" / "tcga",
        report_path=tmp_path / "report.json",
        retry_log_path=tmp_path / "retry.json",
        max_downloads=1,
        allowed_data_subdirs={"expression"},
    )
    assert summary["total_candidates"] == 2
    assert summary["attempted_downloads"] == 1
    assert summary["downloaded_count"] == 1
    assert not (tmp_path / "bronze" / "tcga" / "TCGA-BRCA" / "clinical" / "clin.tsv").exists()
