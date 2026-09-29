from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
import yaml

from src.operations.submission_readiness import build_submission_readiness_report


FIXTURE_COMMIT = "a" * 40


@pytest.fixture(autouse=True)
def _fixed_checkout_revision(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("src.operations.submission_readiness._git_commit", lambda root: FIXTURE_COMMIT)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _fixture(root: Path, *, complete: bool) -> Path:
    manuscript_dir = root / "manuscript"
    manuscript_dir.mkdir(parents=True)
    manuscript = manuscript_dir / "manuscript.md"
    ai_text = (
        "Codex assisted with tests and drafting; the human author verified all outputs."
        if complete
        else "[AI DISCLOSURE TO COMPLETE]"
    )
    author_text = "Pronab Chandra Roy" if complete else "[AUTHOR TO COMPLETE]"
    manuscript.write_text(
        f"# Paper\n\n## Generative AI Disclosure\n\n{ai_text}\n\n## Author\n\n{author_text}\n",
        encoding="utf-8",
    )
    ledger = manuscript_dir / "evidence_ledger.json"
    fixture_evidence = root / "outputs/reports/source.json"
    fixture_evidence.parent.mkdir(parents=True, exist_ok=True)
    fixture_evidence.write_text('{"count": 1}', encoding="utf-8")
    ledger.write_text(
        json.dumps(
            {
                "status": "passed",
                "git_commit": FIXTURE_COMMIT,
                "resources": [{
                    "name": "report:fixture",
                    "path": "outputs/reports/source.json",
                    "bytes": fixture_evidence.stat().st_size,
                    "sha256": _sha256(fixture_evidence),
                }],
                "claims": [{"claim_id": "C01", "source": "report:fixture"}],
            }
        ),
        encoding="utf-8",
    )
    package_manifest = {
        "status": "passed",
        "git_commit": FIXTURE_COMMIT,
        "file_count": 3,
        "files": [
            {
                "path": manuscript.name,
                "sha256": _sha256(manuscript),
            },
            {
                "path": ledger.name,
                "sha256": _sha256(ledger),
            },
        ],
    }
    (manuscript_dir / "package_manifest.json").write_text(
        json.dumps(package_manifest),
        encoding="utf-8",
    )

    citation = {
        "license": "MIT",
        "identifiers": [{"type": "doi", "value": "10.0000/fixture"}] if complete else [],
    }
    (root / "CITATION.cff").write_text(yaml.safe_dump(citation), encoding="utf-8")
    (root / "LICENSE").write_text("MIT", encoding="utf-8")
    metadata = {
        "manuscript": {
            "author": {
                "name": "Pronab Chandra Roy",
                "affiliation": "Institute" if complete else "",
                "corresponding_email": "author@example.org" if complete else "",
                "metadata_verified": complete,
            },
            "declarations": {
                "competing_interests": "None declared." if complete else "",
                "funding": "No external funding." if complete else "",
                "declarations_verified": complete,
            },
            "ai_assistance": {
                "tools": [
                    {
                        "name": "Codex",
                        "model": "fixture",
                        "scope": "Testing.",
                        "author_confirmation_required": not complete,
                    }
                ],
                "human_review_confirmed": complete,
                "author_responsibility_confirmed": complete,
            },
        }
    }
    (root / "manuscript_metadata.yml").write_text(
        yaml.safe_dump(metadata),
        encoding="utf-8",
    )

    docs = root / "docs"
    (docs / "attestations").mkdir(parents=True)
    for path in [
        docs / "publication_strategy.md",
        docs / "comparative_evaluation_protocol.md",
        docs / "biological_review_checklist.md",
        docs / "attestations/biological_review.example.yml",
    ]:
        path.write_text("fixture", encoding="utf-8")
    if complete:
        (docs / "attestations/biological_review.yml").write_text(
            yaml.safe_dump(
                {
                    "status": "approved",
                    "reviewer_name": "Reviewer",
                    "reviewer_affiliation": "Institute",
                    "review_date": "2026-07-26",
                }
            ),
            encoding="utf-8",
        )

    reports = root / "outputs/reports"
    reports.mkdir(parents=True, exist_ok=True)
    for name in ("research_benchmark_report.json", "reference_ablation_report.json"):
        (reports / name).write_text(json.dumps({"git_commit": FIXTURE_COMMIT}), encoding="utf-8")
    if complete:
        tasks = [
            {
                "tool": tool,
                "task_id": task_id,
                "task_status": "passed",
                "tool_version": f"0.1.0+{FIXTURE_COMMIT[:7]}" if tool == "CancerOmicsLake" else "fixture",
                "evidence": [f"{tool}/{task_id}.json"],
            }
            for tool in [
                "CancerOmicsLake",
                "TCGAbiolinks",
                "UCSC Xena",
                "cBioPortal",
            ]
            for task_id in ["T1", "T2", "T3", "T4", "T5"]
        ]
        (reports / "comparative_evaluation_report.json").write_text(
            json.dumps(
                {
                    "status": "passed",
                    "comparators": ["TCGAbiolinks", "UCSC Xena", "cBioPortal"],
                    "tasks": tasks,
                }
            ),
            encoding="utf-8",
        )

    config = {
        "publication": {
            "primary_venue": "GigaScience",
            "article_type": "Technical Note",
            "subject_tool": "CancerOmicsLake",
            "manuscript_path": "manuscript/manuscript.md",
            "package_manifest_path": "manuscript/package_manifest.json",
            "evidence_ledger_path": "manuscript/evidence_ledger.json",
            "citation_path": "CITATION.cff",
            "manuscript_metadata_path": "manuscript_metadata.yml",
            "biological_review_path": "docs/attestations/biological_review.yml",
            "comparative_evaluation_path": "outputs/reports/comparative_evaluation_report.json",
            "revisioned_evidence_paths": [
                "outputs/reports/research_benchmark_report.json",
                "outputs/reports/reference_ablation_report.json",
            ],
            "required_comparators": ["TCGAbiolinks", "UCSC Xena", "cBioPortal"],
            "required_comparison_tasks": ["T1", "T2", "T3", "T4", "T5"],
            "required_documents": [
                "docs/publication_strategy.md",
                "docs/comparative_evaluation_protocol.md",
                "docs/biological_review_checklist.md",
                "docs/attestations/biological_review.example.yml",
            ],
        }
    }
    config_path = root / "publication.yml"
    config_path.write_text(yaml.safe_dump(config), encoding="utf-8")
    return config_path


def test_submission_readiness_passes_complete_fixture(tmp_path: Path) -> None:
    config = _fixture(tmp_path, complete=True)

    payload = build_submission_readiness_report(
        config_path=config.relative_to(tmp_path),
        root_dir=tmp_path,
    )

    assert payload["status"] == "ready"
    assert payload["blocker_count"] == 0
    assert payload["passed_count"] == payload["check_count"] == 11


def test_submission_readiness_reports_human_and_comparison_blockers(
    tmp_path: Path,
) -> None:
    config = _fixture(tmp_path, complete=False)

    payload = build_submission_readiness_report(
        config_path=config.relative_to(tmp_path),
        root_dir=tmp_path,
    )

    failed = {
        check["check_name"]
        for check in payload["checks"]
        if check["status"] == "failed"
    }
    assert payload["status"] == "not_ready"
    assert payload["blocker_count"] == 6
    assert failed == {
        "author_and_disclosure_fields_complete",
        "generative_ai_disclosure_present",
        "persistent_identifier_registered",
        "independent_biological_review_approved",
        "comparative_evaluation_passed",
        "research_evidence_revision_current",
    }


@pytest.mark.parametrize("stale_source", ["benchmark", "package", "ledger", "comparison"])
def test_submission_readiness_rejects_stale_revisioned_evidence(tmp_path: Path, stale_source: str) -> None:
    config = _fixture(tmp_path, complete=True)
    paths = {
        "benchmark": tmp_path / "outputs/reports/research_benchmark_report.json",
        "package": tmp_path / "manuscript/package_manifest.json",
        "ledger": tmp_path / "manuscript/evidence_ledger.json",
        "comparison": tmp_path / "outputs/reports/comparative_evaluation_report.json",
    }
    path = paths[stale_source]
    payload = json.loads(path.read_text(encoding="utf-8"))
    if stale_source == "comparison":
        for task in payload["tasks"]:
            if task["tool"] == "CancerOmicsLake":
                task["tool_version"] = "0.1.0+bbbbbbb"
    else:
        payload["git_commit"] = "b" * 40
    path.write_text(json.dumps(payload), encoding="utf-8")

    report = build_submission_readiness_report(config.relative_to(tmp_path), tmp_path)

    checks = {check["check_name"]: check for check in report["checks"]}
    assert checks["research_evidence_revision_current"]["status"] == "failed"
    assert report["status"] == "not_ready"


def test_submission_readiness_requires_verifiable_checkout_revision(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = _fixture(tmp_path, complete=True)
    monkeypatch.setattr("src.operations.submission_readiness._git_commit", lambda root: None)

    report = build_submission_readiness_report(config.relative_to(tmp_path), tmp_path)

    checks = {check["check_name"]: check for check in report["checks"]}
    assert checks["research_evidence_revision_current"]["status"] == "failed"
    assert "current_git_commit=unavailable" in checks["research_evidence_revision_current"]["evidence"]


def test_submission_readiness_detects_package_hash_tampering(tmp_path: Path) -> None:
    config = _fixture(tmp_path, complete=True)
    (tmp_path / "manuscript/manuscript.md").write_text("tampered", encoding="utf-8")

    payload = build_submission_readiness_report(
        config_path=config.relative_to(tmp_path),
        root_dir=tmp_path,
    )

    package_check = next(
        check
        for check in payload["checks"]
        if check["check_name"] == "manuscript_package_integrity"
    )
    assert package_check["status"] == "failed"


def test_submission_readiness_detects_changed_source_evidence(tmp_path: Path) -> None:
    config = _fixture(tmp_path, complete=True)
    (tmp_path / "outputs/reports/source.json").write_text('{"count": 2}', encoding="utf-8")

    payload = build_submission_readiness_report(config.relative_to(tmp_path), tmp_path)

    checks = {check["check_name"]: check for check in payload["checks"]}
    assert checks["research_evidence_revision_current"]["status"] == "passed"
    assert checks["evidence_ledger_resources_current"]["status"] == "failed"
    assert payload["status"] == "not_ready"


def test_submission_readiness_rejects_ledger_path_escape(tmp_path: Path) -> None:
    config = _fixture(tmp_path, complete=True)
    ledger_path = tmp_path / "manuscript/evidence_ledger.json"
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    ledger["resources"][0]["path"] = "../../outside.json"
    ledger_path.write_text(json.dumps(ledger), encoding="utf-8")

    payload = build_submission_readiness_report(config.relative_to(tmp_path), tmp_path)

    checks = {check["check_name"]: check for check in payload["checks"]}
    assert checks["evidence_ledger_resources_current"]["status"] == "failed"


def test_submission_readiness_requires_metadata_confirmation_even_without_markers(
    tmp_path: Path,
) -> None:
    config = _fixture(tmp_path, complete=False)
    manuscript = tmp_path / "manuscript/manuscript.md"
    manuscript.write_text(
        "# Paper\n\n## Generative AI Disclosure\n\nDraft disclosure text.\n",
        encoding="utf-8",
    )
    manifest_path = tmp_path / "manuscript/package_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manuscript_entry = next(
        item for item in manifest["files"] if item["path"] == "manuscript.md"
    )
    manuscript_entry["sha256"] = _sha256(manuscript)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    payload = build_submission_readiness_report(
        config_path=config.relative_to(tmp_path),
        root_dir=tmp_path,
    )
    failed = {
        check["check_name"]
        for check in payload["checks"]
        if check["status"] == "failed"
    }

    assert "author_and_disclosure_fields_complete" in failed
    assert "generative_ai_disclosure_present" in failed
