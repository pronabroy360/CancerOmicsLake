from __future__ import annotations

from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
from typing import Any

import yaml


PLACEHOLDER_MARKERS = (
    "[AUTHOR TO COMPLETE]",
    "[COLLABORATOR TO COMPLETE]",
    "[AI DISCLOSURE TO COMPLETE]",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_mapping(path: Path, *, yaml_input: bool = False) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        payload = (
            yaml.safe_load(path.read_text(encoding="utf-8"))
            if yaml_input
            else json.loads(path.read_text(encoding="utf-8"))
        )
    except (json.JSONDecodeError, yaml.YAMLError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _check(
    check_name: str,
    passed: bool,
    evidence: list[str],
    remediation: str,
) -> dict[str, Any]:
    return {
        "check_name": check_name,
        "status": "passed" if passed else "failed",
        "required": True,
        "evidence": evidence,
        "remediation": "" if passed else remediation,
    }


def _package_integrity(root: Path, manifest_path: Path) -> tuple[bool, str]:
    manifest = _read_mapping(manifest_path)
    files = manifest.get("files", [])
    if manifest.get("status") != "passed" or not isinstance(files, list) or not files:
        return False, "missing or invalid package manifest"
    package_root = manifest_path.parent
    for item in files:
        if not isinstance(item, dict) or not item.get("path") or not item.get("sha256"):
            return False, "invalid package file entry"
        target = (package_root / str(item["path"])).resolve()
        if not target.is_relative_to(package_root.resolve()):
            return False, f"package path escapes root: {item['path']}"
        if not target.exists() or _sha256(target) != item["sha256"]:
            return False, f"hash mismatch for {target.relative_to(root)}"
    expected_count = manifest.get("file_count")
    actual_count = sum(path.is_file() for path in package_root.rglob("*"))
    if expected_count != actual_count:
        return False, f"package file count mismatch: expected={expected_count} actual={actual_count}"
    return True, f"verified {len(files)} hashes across {actual_count} package files"


def _citation_has_doi(citation: dict[str, Any]) -> bool:
    if citation.get("doi"):
        return True
    identifiers = citation.get("identifiers", [])
    return isinstance(identifiers, list) and any(
        isinstance(item, dict)
        and str(item.get("type", "")).lower() == "doi"
        and bool(item.get("value"))
        for item in identifiers
    )


def _metadata_confirmation(
    metadata: dict[str, Any],
) -> tuple[bool, list[str], bool, list[str]]:
    author = metadata.get("author", {})
    declarations = metadata.get("declarations", {})
    ai = metadata.get("ai_assistance", {})
    author_missing: list[str] = []
    if not isinstance(author, dict):
        author = {}
    if not isinstance(declarations, dict):
        declarations = {}
    for field in ("name", "affiliation", "corresponding_email"):
        if not str(author.get(field, "")).strip():
            author_missing.append(f"author.{field}")
    if author.get("metadata_verified") is not True:
        author_missing.append("author.metadata_verified")
    for field in ("competing_interests", "funding"):
        if not str(declarations.get(field, "")).strip():
            author_missing.append(f"declarations.{field}")
    if declarations.get("declarations_verified") is not True:
        author_missing.append("declarations.declarations_verified")

    ai_missing: list[str] = []
    if not isinstance(ai, dict):
        ai = {}
    tools = ai.get("tools", [])
    if not isinstance(tools, list) or not tools:
        ai_missing.append("ai_assistance.tools")
    else:
        for index, tool in enumerate(tools):
            if not isinstance(tool, dict):
                ai_missing.append(f"ai_assistance.tools[{index}]")
                continue
            for field in ("name", "model", "scope"):
                if not str(tool.get(field, "")).strip():
                    ai_missing.append(f"ai_assistance.tools[{index}].{field}")
            if tool.get("author_confirmation_required") is True:
                ai_missing.append(
                    f"ai_assistance.tools[{index}].author_confirmation_required"
                )
    for field in ("human_review_confirmed", "author_responsibility_confirmed"):
        if ai.get(field) is not True:
            ai_missing.append(f"ai_assistance.{field}")
    return not author_missing, author_missing, not ai_missing, ai_missing


def _comparison_evidence_complete(
    comparison: dict[str, Any],
    required_tools: set[str],
    required_tasks: set[str],
) -> tuple[bool, set[str]]:
    rows = comparison.get("tasks", [])
    if not isinstance(rows, list):
        return False, set()
    valid_pairs = {
        (str(row.get("tool")), str(row.get("task_id")))
        for row in rows
        if isinstance(row, dict)
        and row.get("task_status") in {"passed", "partial", "unsupported"}
        and row.get("tool_version")
        and row.get("evidence")
    }
    expected_pairs = {
        (tool, task_id)
        for tool in required_tools
        for task_id in required_tasks
    }
    completed_tools = {
        tool
        for tool in required_tools
        if all((tool, task_id) in valid_pairs for task_id in required_tasks)
    }
    complete = (
        comparison.get("status") == "passed"
        and expected_pairs.issubset(valid_pairs)
    )
    return complete, completed_tools


def build_submission_readiness_report(
    config_path: str | Path = "configs/publication_config.yml",
    root_dir: str | Path = ".",
) -> dict[str, Any]:
    root = Path(root_dir).resolve()
    config_target = root / Path(config_path)
    config = _read_mapping(config_target, yaml_input=True).get("publication", {})
    if not isinstance(config, dict):
        config = {}

    def target(key: str) -> Path:
        return root / Path(str(config.get(key, "")))

    manuscript_path = target("manuscript_path")
    package_manifest_path = target("package_manifest_path")
    evidence_ledger_path = target("evidence_ledger_path")
    citation_path = target("citation_path")
    metadata_path = target("manuscript_metadata_path")
    review_path = target("biological_review_path")
    comparison_path = target("comparative_evaluation_path")

    manuscript = (
        manuscript_path.read_text(encoding="utf-8") if manuscript_path.exists() else ""
    )
    package_ok, package_detail = _package_integrity(root, package_manifest_path)
    ledger = _read_mapping(evidence_ledger_path)
    citation = _read_mapping(citation_path, yaml_input=True)
    metadata = _read_mapping(metadata_path, yaml_input=True).get("manuscript", {})
    if not isinstance(metadata, dict):
        metadata = {}
    review = _read_mapping(review_path, yaml_input=True)
    comparison = _read_mapping(comparison_path)
    required_comparators = {
        str(value) for value in config.get("required_comparators", [])
    }
    subject_tool = str(config.get("subject_tool", "CancerOmicsLake"))
    required_tools = {subject_tool, *required_comparators}
    required_tasks = {
        str(value) for value in config.get("required_comparison_tasks", [])
    }
    comparison_complete, completed_tools = _comparison_evidence_complete(
        comparison,
        required_tools,
        required_tasks,
    )
    required_documents = [
        root / Path(str(value)) for value in config.get("required_documents", [])
    ]
    placeholder_hits = [marker for marker in PLACEHOLDER_MARKERS if marker in manuscript]
    author_confirmed, author_missing, ai_confirmed, ai_missing = (
        _metadata_confirmation(metadata)
    )

    review_fields = ("reviewer_name", "reviewer_affiliation", "review_date")
    review_complete = review.get("status") == "approved" and all(
        review.get(field) for field in review_fields
    )
    checks = [
        _check(
            "manuscript_package_integrity",
            package_ok,
            [str(package_manifest_path.relative_to(root)), package_detail],
            "Rebuild the manuscript package from current passing evidence.",
        ),
        _check(
            "evidence_ledger_passed",
            ledger.get("status") == "passed"
            and isinstance(ledger.get("claims"), list)
            and bool(ledger.get("claims")),
            [str(evidence_ledger_path.relative_to(root))],
            "Regenerate a passing, non-empty claim evidence ledger.",
        ),
        _check(
            "author_and_disclosure_fields_complete",
            bool(manuscript)
            and not placeholder_hits
            and author_confirmed
            and ai_confirmed,
            [
                str(manuscript_path.relative_to(root)),
                str(metadata_path.relative_to(root)),
                *placeholder_hits,
                *author_missing,
                *ai_missing,
            ],
            "Complete and confirm author, declaration, and AI-assistance metadata, then rebuild.",
        ),
        _check(
            "generative_ai_disclosure_present",
            "## Generative AI Disclosure" in manuscript
            and "[AI DISCLOSURE TO COMPLETE]" not in manuscript
            and ai_confirmed,
            [
                str(manuscript_path.relative_to(root)),
                str(metadata_path.relative_to(root)),
                *ai_missing,
            ],
            "Confirm exact AI tools/models, assistance scope, human review, and author responsibility.",
        ),
        _check(
            "persistent_identifier_registered",
            _citation_has_doi(citation),
            [str(citation_path.relative_to(root))],
            "Create a versioned repository/data deposit and add its DOI to CITATION.cff.",
        ),
        _check(
            "independent_biological_review_approved",
            review_complete,
            [str(review_path.relative_to(root))],
            "Obtain independent biological review and complete the attestation from the provided template.",
        ),
        _check(
            "comparative_evaluation_passed",
            comparison_complete,
            [
                str(comparison_path.relative_to(root)),
                f"required={sorted(required_tools)}",
                f"completed={sorted(completed_tools)}",
                f"tasks={sorted(required_tasks)}",
            ],
            "Run the preregistered comparison against TCGAbiolinks, UCSC Xena, and cBioPortal.",
        ),
        _check(
            "submission_documents_present",
            bool(required_documents) and all(path.exists() for path in required_documents),
            [str(path.relative_to(root)) for path in required_documents],
            "Restore all publication strategy and scientific-review documents.",
        ),
        _check(
            "open_source_license_present",
            (root / "LICENSE").exists() and str(citation.get("license", "")).upper() == "MIT",
            ["LICENSE", str(citation_path.relative_to(root))],
            "Provide an OSI-approved license and matching citation metadata.",
        ),
    ]
    failed = [check for check in checks if check["status"] == "failed"]
    return {
        "schema_version": "1.0",
        "generated_at": datetime.now(UTC).isoformat(),
        "status": "ready" if not failed else "not_ready",
        "primary_venue": config.get("primary_venue"),
        "article_type": config.get("article_type"),
        "check_count": len(checks),
        "passed_count": len(checks) - len(failed),
        "blocker_count": len(failed),
        "checks": checks,
        "next_actions": [check["remediation"] for check in failed],
        "interpretation": (
            "A ready status confirms packaging requirements only; it does not predict peer review "
            "or establish biological validity."
        ),
    }


def write_submission_readiness_report(
    payload: dict[str, Any],
    output_path: str | Path = "outputs/reports/submission_readiness_report.json",
) -> Path:
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(f"{target.suffix}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    temporary.replace(target)
    return target
