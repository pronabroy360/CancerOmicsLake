from __future__ import annotations

from datetime import UTC, datetime
import hashlib
from importlib.metadata import PackageNotFoundError, version
import json
from pathlib import Path
import re
import subprocess
from typing import Any
from urllib.request import Request, urlopen
import warnings

import polars as pl
import yaml


TASK_IDS = ("T1", "T2", "T3", "T4", "T5")
PUBLIC_IDENTIFIER_PATTERN = re.compile(
    r"(?:PATIENT:|SAMPLE:|TCGA-[A-Z0-9]{2}-[A-Z0-9]{4})",
    re.IGNORECASE,
)


def _git_commit() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else "unknown"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, payload: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    temporary.replace(path)
    return path


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _relative(path: Path, root: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def _task_payload(
    tool: str,
    task_id: str,
    task_status: str,
    tool_version: str,
    execution_mode: str,
    evidence: list[str],
    result_summary: dict[str, Any],
    limitations: list[str],
) -> dict[str, Any]:
    if task_id not in TASK_IDS:
        raise ValueError(f"Unsupported comparison task: {task_id}")
    return {
        "schema_version": "1.0",
        "generated_at": datetime.now(UTC).isoformat(),
        "tool": tool,
        "task_id": task_id,
        "task_status": task_status,
        "tool_version": tool_version,
        "execution_mode": execution_mode,
        "evidence": evidence,
        "result_summary": result_summary,
        "limitations": limitations,
    }


def _http_json(url: str, timeout_seconds: int) -> Any:
    request = Request(
        url,
        headers={"User-Agent": "CancerOmicsLake-comparative-evaluation/0.1"},
    )
    with urlopen(request, timeout=timeout_seconds) as response:
        return json.loads(response.read().decode("utf-8"))


def _evidence_available(task: dict[str, Any], root: Path) -> bool:
    evidence = task.get("evidence")
    if not isinstance(evidence, list) or not evidence:
        return False
    for value in evidence:
        reference = str(value)
        if reference.startswith(("https://", "http://")):
            continue
        target = (root / reference).resolve()
        if not target.is_relative_to(root) or not target.exists():
            return False
    return True


def collect_canceromicslake_baseline(
    root_dir: str | Path = ".",
    output_root: str | Path = "outputs/comparative",
) -> list[dict[str, Any]]:
    root = Path(root_dir).resolve()
    output = root / Path(output_root) / "CancerOmicsLake"
    gold = root / "data/gold"
    reports = root / "outputs/reports"
    graph = root / "outputs/graph_exports/neo4j"
    commit = _git_commit()
    tool_version = f"0.1.0+{commit[:7]}"
    records: list[dict[str, Any]] = []

    cohort_path = gold / "gold_cohort_summary.parquet"
    cohort = pl.read_parquet(cohort_path).row(0, named=True)
    t1_result = output / "T1/result.json"
    _write_json(t1_result, cohort)
    records.append(
        _task_payload(
            "CancerOmicsLake",
            "T1",
            "passed",
            tool_version,
            "local CLI and Parquet",
            [_relative(t1_result, root), _relative(cohort_path, root)],
            {
                "projects": int(cohort["tcga_project_count"]),
                "files": int(cohort["tcga_file_count"]),
                "samples": int(cohort["tcga_sample_count"]),
                "cases": int(cohort["tcga_patient_count"]),
            },
            ["Counts describe the locally acquired open-access profile, not complete TCGA."],
        )
    )

    expression_path = gold / "gold_tumor_vs_normal_expression.parquet"
    expression = pl.read_parquet(expression_path).filter(
        (pl.col("cancer_type") == "TCGA-BRCA")
        & (pl.col("gene_symbol") == "TP53")
    )
    if expression.height != 1:
        raise RuntimeError("CancerOmicsLake T2 requires exactly one BRCA TP53 result")
    expression_row = expression.row(0, named=True)
    t2_result = output / "T2/result.json"
    _write_json(t2_result, expression_row)
    records.append(
        _task_payload(
            "CancerOmicsLake",
            "T2",
            "passed",
            tool_version,
            "local CLI and Parquet",
            [_relative(t2_result, root), _relative(expression_path, root)],
            expression_row,
            ["TCGA-GTEx effects remain sensitive to collection and processing differences."],
        )
    )

    mutation_path = gold / "gold_mutation_frequency_by_gene.parquet"
    mutation = pl.read_parquet(mutation_path).filter(
        (pl.col("cancer_type") == "TCGA-LUAD")
        & (pl.col("gene_symbol") == "TP53")
    )
    if mutation.height != 1:
        raise RuntimeError("CancerOmicsLake T3 requires exactly one LUAD TP53 result")
    mutation_row = mutation.row(0, named=True)
    t3_result = output / "T3/result.json"
    _write_json(t3_result, mutation_row)
    records.append(
        _task_payload(
            "CancerOmicsLake",
            "T3",
            "passed",
            tool_version,
            "local CLI and Parquet",
            [_relative(t3_result, root), _relative(mutation_path, root)],
            mutation_row,
            [
                "The denominator is the downloaded mutation-profile cohort.",
                "Protein-altering classification does not establish driver status.",
            ],
        )
    )

    benchmark_path = reports / "research_benchmark_report.json"
    ledger_path = root / "manuscript/evidence_ledger.json"
    benchmark = _read_json(benchmark_path)
    ledger = _read_json(ledger_path)
    t4_passed = benchmark.get("status") == "passed" and ledger.get("status") == "passed"
    t4_result = output / "T4/result.json"
    t4_summary = {
        "benchmark_status": benchmark.get("status"),
        "benchmark_workloads": len(benchmark.get("workloads", [])),
        "evidence_ledger_status": ledger.get("status"),
        "evidence_claims": len(ledger.get("claims", [])),
        "benchmark_sha256": _sha256(benchmark_path),
        "ledger_sha256": _sha256(ledger_path),
    }
    _write_json(t4_result, t4_summary)
    records.append(
        _task_payload(
            "CancerOmicsLake",
            "T4",
            "passed" if t4_passed else "failed",
            tool_version,
            "local Make/CLI",
            [
                _relative(t4_result, root),
                _relative(benchmark_path, root),
                _relative(ledger_path, root),
            ],
            t4_summary,
            ["Timing evidence is single-machine and not a cross-tool performance claim."],
        )
    )

    nodes_path = graph / "nodes.csv"
    edges_path = graph / "edges.csv"
    nodes = pl.read_csv(nodes_path)
    edges = pl.read_csv(edges_path)
    identifier_hits = 0
    for frame, columns in (
        (nodes, ["node_id"]),
        (edges, ["source_node_id", "target_node_id"]),
    ):
        for column in columns:
            identifier_hits += frame.filter(
                pl.col(column)
                .cast(pl.Utf8)
                .str.contains(PUBLIC_IDENTIFIER_PATTERN.pattern)
            ).height
    t5_result = output / "T5/result.json"
    t5_summary = {
        "public_node_count": nodes.height,
        "public_edge_count": edges.height,
        "individual_identifier_hits": identifier_hits,
        "nodes_sha256": _sha256(nodes_path),
        "edges_sha256": _sha256(edges_path),
    }
    _write_json(t5_result, t5_summary)
    records.append(
        _task_payload(
            "CancerOmicsLake",
            "T5",
            "passed" if identifier_hits == 0 else "failed",
            tool_version,
            "local graph export",
            [
                _relative(t5_result, root),
                _relative(nodes_path, root),
                _relative(edges_path, root),
            ],
            t5_summary,
            ["The scan enforces known identifier patterns, not universal re-identification risk."],
        )
    )

    for record in records:
        _write_json(output / record["task_id"] / "task.json", record)
    return records


def collect_cbioportal_t1(
    root_dir: str | Path = ".",
    output_root: str | Path = "outputs/comparative",
    timeout_seconds: int = 30,
) -> dict[str, Any]:
    root = Path(root_dir).resolve()
    output = root / Path(output_root) / "cBioPortal/T1"
    studies_url = "https://www.cbioportal.org/api/studies?projection=SUMMARY&pageSize=10000"
    specification_url = "https://www.cbioportal.org/api/v3/api-docs"
    studies = _http_json(studies_url, timeout_seconds)
    specification = _http_json(specification_url, timeout_seconds)
    target_studies = {
        study["studyId"]: study
        for study in studies
        if study.get("studyId")
        in {"brca_tcga_gdc", "coad_tcga_gdc", "luad_tcga_gdc"}
    }
    raw_path = output / "studies.json"
    _write_json(raw_path, target_studies)
    record = _task_payload(
        "cBioPortal",
        "T1",
        "passed" if len(target_studies) == 3 else "failed",
        str(specification.get("info", {}).get("version", "unreported")),
        "public REST API",
        [_relative(raw_path, root), studies_url, specification_url],
        {
            "requested_studies": 3,
            "matched_studies": len(target_studies),
            "study_ids": sorted(target_studies),
        },
        [
            "Portal study cohorts may not match local GDC acquisition counts."
        ],
    )
    _write_json(output / "task.json", record)
    return record


def collect_xena_t1(
    root_dir: str | Path = ".",
    output_root: str | Path = "outputs/comparative",
) -> dict[str, Any]:
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", FutureWarning)
            import xenaPython as xena
    except ImportError as exc:
        raise RuntimeError(
            "xenaPython is required; install requirements-comparative.txt"
        ) from exc

    root = Path(root_dir).resolve()
    output = root / Path(output_root) / "UCSC Xena/T1"
    gdc_rows = xena.cohort_summary(xena.PUBLIC_HUBS["gdcHub"], xena.excludeType)
    toil_rows = xena.cohort_summary(xena.PUBLIC_HUBS["toilHub"], xena.excludeType)
    target_names = {
        "GDC TCGA Breast Cancer (BRCA)",
        "GDC TCGA Colon Cancer (COAD)",
        "GDC TCGA Lung Adenocarcinoma (LUAD)",
    }
    target_rows = [row for row in gdc_rows if row.get("cohort") in target_names]
    integrated_rows = [
        row
        for row in toil_rows
        if row.get("cohort") in {"TCGA TARGET GTEx", "GTEX"}
    ]
    raw_path = output / "cohorts.json"
    _write_json(
        raw_path,
        {
            "gdc_target_cohorts": target_rows,
            "toil_integrated_cohorts": integrated_rows,
        },
    )
    try:
        package_version = version("xenapython")
    except PackageNotFoundError:
        package_version = "unreported"
    record = _task_payload(
        "UCSC Xena",
        "T1",
        "passed" if len(target_rows) == 3 and integrated_rows else "failed",
        f"xenaPython {package_version} @ f243bbf",
        "pinned Python API and public Xena hubs",
        [
            _relative(raw_path, root),
            "https://ucsc-xena.gitbook.io/project/overview-of-features/accessing-data-through-python",
            "https://gdc.xenahubs.net",
            "https://toil.xenahubs.net",
        ],
        {
            "requested_gdc_cohorts": 3,
            "matched_gdc_cohorts": len(target_rows),
            "integrated_tcga_gtex_cohorts": len(integrated_rows),
        },
        ["Hosted hub contents and versions can change independently of this repository."],
    )
    _write_json(output / "task.json", record)
    return record


def build_comparative_evaluation_report(
    publication_config_path: str | Path = "configs/publication_config.yml",
    root_dir: str | Path = ".",
    evidence_root: str | Path = "outputs/comparative",
) -> dict[str, Any]:
    root = Path(root_dir).resolve()
    config = yaml.safe_load(
        (root / Path(publication_config_path)).read_text(encoding="utf-8")
    )["publication"]
    subject = str(config["subject_tool"])
    comparators = [str(value) for value in config["required_comparators"]]
    required_tasks = [str(value) for value in config["required_comparison_tasks"]]
    required_tools = [subject, *comparators]
    task_paths = sorted((root / Path(evidence_root)).glob("*/T*/task.json"))
    tasks = [_read_json(path) for path in task_paths]
    valid_tasks = [
        task
        for task in tasks
        if task.get("tool") in required_tools
        and task.get("task_id") in required_tasks
        and task.get("task_status") in {"passed", "partial", "unsupported"}
        and task.get("tool_version")
        and _evidence_available(task, root)
    ]
    valid_pairs = {(task["tool"], task["task_id"]) for task in valid_tasks}
    required_pairs = {
        (tool, task_id) for tool in required_tools for task_id in required_tasks
    }
    missing = sorted(required_pairs - valid_pairs)
    failed_tasks = [task for task in tasks if task.get("task_status") == "failed"]
    return {
        "schema_version": "1.0",
        "protocol_version": "1.0",
        "generated_at": datetime.now(UTC).isoformat(),
        "status": "passed" if not missing and not failed_tasks else "in_progress",
        "subject_tool": subject,
        "comparators": comparators,
        "required_task_ids": required_tasks,
        "required_result_count": len(required_pairs),
        "completed_result_count": len(valid_pairs),
        "missing_result_count": len(missing),
        "failed_result_count": len(failed_tasks),
        "missing_results": [
            {"tool": tool, "task_id": task_id} for tool, task_id in missing
        ],
        "tasks": sorted(
            tasks,
            key=lambda task: (str(task.get("tool")), str(task.get("task_id"))),
        ),
        "claim_boundary": (
            "Capability and reproducibility comparison, not a universal tool ranking."
        ),
    }


def write_comparative_evaluation_report(
    payload: dict[str, Any],
    output_path: str | Path = "outputs/reports/comparative_evaluation_report.json",
) -> Path:
    return _write_json(Path(output_path), payload)
