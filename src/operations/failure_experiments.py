"""Offline fault injection through production guards, without touching real inputs."""
from datetime import UTC, datetime
import hashlib
import json
import inspect
from pathlib import Path
import tempfile
from unittest.mock import patch

import polars as pl

from src.analytics.controlled_reference_study import _matrix, lock_plan
from src.ingestion import tcga_downloader
from src.operations.submission_readiness import _ledger_resource_integrity


def run_failure_experiments(output_path: str | Path = "outputs/research/failure_experiments.json") -> dict:
    rows = []
    with tempfile.TemporaryDirectory(prefix="canceromics-faults-") as directory:
        root = Path(directory).resolve()
        payload = b"synthetic fixture, not biomedical data\n"
        destination = root / "download.tsv"
        row = {"project_id": "TCGA-BRCA", "file_id": "fixture", "file_name": destination.name,
               "data_category": "Transcriptome Profiling", "md5sum": hashlib.md5(payload).hexdigest()}

        def corrupt(*args, **kwargs):
            destination.write_bytes(b"corrupted")

        with patch.object(tcga_downloader, "_fetch_to_path", side_effect=corrupt):
            result = tcga_downloader._download_one_row(row, destination, "https://fixture.invalid", 1, 0, 1)
        rows.append({"scenario": "corrupted_download", "passed": result["checksum_mismatch"] and not destination.exists(),
                     "observed": result["error"], "unguarded_control": "would accept corrupted bytes without checksum validation"})

        attempts = 0

        def interrupted(*args, **kwargs):
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                destination.write_bytes(payload[:4])
                raise OSError("injected interruption")
            destination.write_bytes(payload)

        with patch.object(tcga_downloader, "_fetch_to_path", side_effect=interrupted):
            result = tcga_downloader._download_one_row(row, destination, "https://fixture.invalid", 1, 0, 1)
        recovered = attempts == 2 and result["status"] == "downloaded" and destination.read_bytes() == payload
        recovery_attempts = attempts
        attempts = 0
        with patch.object(tcga_downloader, "_fetch_to_path", side_effect=interrupted):
            no_retry = tcga_downloader._download_one_row(row, destination, "https://fixture.invalid", 0, 0, 1)
        partial = destination.read_bytes() != payload
        rows.append({"scenario": "interrupted_download", "passed": recovered and no_retry["status"] == "failed" and partial,
                     "observed": result["status"], "attempts": recovery_attempts,
                     "measured_retry_disabled_control": {"status": no_retry["status"], "attempts": attempts, "partial_file": partial},
                     "unguarded_control": "No byte-range resume claim; control changes only the production retry count"})

        selected = pl.DataFrame({"sample_id": ["synthetic"]})
        frame = pl.DataFrame({"sample_id": ["synthetic"], "gene_id": ["ENSG00000000001"],
                              "expression_value": [1.0], "expression_unit": ["TPM"]})
        for scenario, damaged, expected in (
            ("changed_schema", frame.drop("expression_value"), pl.exceptions.ColumnNotFoundError),
            ("duplicate_measurement", pl.concat([frame, frame]), ValueError),
            ("negative_expression", frame.with_columns(pl.lit(-1.).alias("expression_value")), ValueError),
        ):
            detected = False
            try:
                _matrix(damaged.lazy(), selected, "sample_id")
            except expected:
                detected = True
            rows.append({"scenario": scenario, "passed": detected, "observed": "blocked" if detected else "accepted"})

        evidence = root / "evidence.json"
        evidence.write_bytes(payload)
        ledger = {"resources": [{"name": "fixture", "path": evidence.name, "bytes": len(payload),
                                 "sha256": hashlib.sha256(payload).hexdigest()}],
                  "claims": [{"source": "fixture"}]}
        clean, _ = _ledger_resource_integrity(root, ledger)
        evidence.write_bytes(b"X" * len(payload))
        size_only_accepted = evidence.stat().st_size == len(payload)
        valid, details = _ledger_resource_integrity(root, ledger)
        rows.append({"scenario": "stale_evidence_same_size", "passed": clean and not valid and size_only_accepted,
                     "observed": details, "measured_size_only_control_accepted": size_only_accepted,
                     "unguarded_control": "Control validates only the exact byte count"})

        plan = root / "study_plan.json"
        lock_plan(plan, {"seed": 1})
        detected = False
        try:
            lock_plan(plan, {"seed": 2})
        except RuntimeError:
            detected = True
        rows.append({"scenario": "changed_frozen_protocol", "passed": detected, "observed": "blocked" if detected else "accepted"})

    functions = (_matrix, lock_plan, tcga_downloader._download_one_row, _ledger_resource_integrity)
    paths = sorted({Path(inspect.getfile(function)) for function in functions} | {Path(__file__)})
    report = {"generated_at": datetime.now(UTC).isoformat(), "status": "passed" if all(r["passed"] for r in rows) else "failed",
              "implementation_resources": [{"name": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()} for path in paths],
              "experiment_type": "offline synthetic fault injection into production functions",
              "independent_reproduction": "not performed",
              "limitations": ["No external workflow comparison or runtime benefit established",
                              "Transport is mocked; no real network interruption or persistent checkpoint recovery tested"],
              "scenarios": rows}
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2) + "\n")
    if report["status"] != "passed":
        raise RuntimeError(f"Failure experiments did not pass; inspect {path}")
    return report
