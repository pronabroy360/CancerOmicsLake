import json

from src.operations.failure_experiments import run_failure_experiments
from src.processing.normalize_gene_ids import strip_ensembl_version


def test_offline_failure_experiments(tmp_path):
    path = tmp_path / "faults.json"
    report = run_failure_experiments(path)
    assert report["status"] == "passed"
    assert len(report["scenarios"]) == 7
    assert all(row["passed"] for row in report["scenarios"])
    assert json.loads(path.read_text()) == report
    assert report["independent_reproduction"] == "not performed"
    controls = {row["scenario"]: row for row in report["scenarios"]}
    assert controls["interrupted_download"]["measured_retry_disabled_control"]["attempts"] == 1
    assert controls["stale_evidence_same_size"]["measured_size_only_control_accepted"]


def test_gene_version_normalization_preserves_pseudoautosomal_locus():
    assert strip_ensembl_version("ENSG00000002586.20_PAR_Y") == "ENSG00000002586_PAR_Y"
    assert strip_ensembl_version("ENSG00000002586.20") == "ENSG00000002586"
    assert strip_ensembl_version("ENSG00000002586_PAR_Y") == "ENSG00000002586_PAR_Y"
