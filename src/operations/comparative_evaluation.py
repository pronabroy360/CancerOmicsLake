from __future__ import annotations

from datetime import UTC, datetime
import hashlib
from importlib.metadata import PackageNotFoundError, version
import json
import math
from pathlib import Path
import re
from statistics import fmean, median
import subprocess
from typing import Any
from urllib.request import Request, urlopen
import warnings

import polars as pl
import yaml


TASK_IDS = ("T1", "T2", "T3", "T4", "T5")
PROTEIN_ALTERING_EFFECTS = {
    "Frame_Shift_Del",
    "Frame_Shift_Ins",
    "In_Frame_Del",
    "In_Frame_Ins",
    "Missense_Mutation",
    "Nonsense_Mutation",
    "Nonstop_Mutation",
    "Splice_Site",
    "Translation_Start_Site",
}
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


def _identifier_hits(path: Path) -> int:
    return len(PUBLIC_IDENTIFIER_PATTERN.findall(path.read_text(encoding="utf-8")))


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


def collect_cbioportal_tasks(
    root_dir: str | Path = ".",
    output_root: str | Path = "outputs/comparative",
    timeout_seconds: int = 60,
) -> list[dict[str, Any]]:
    root = Path(root_dir).resolve()
    output = root / Path(output_root) / "cBioPortal"
    records = [
        collect_cbioportal_t1(
            root_dir=root,
            output_root=output_root,
            timeout_seconds=timeout_seconds,
        )
    ]
    api_root = "https://www.cbioportal.org/api"
    specification_url = f"{api_root}/v3/api-docs"
    specification = _http_json(specification_url, timeout_seconds)
    tool_version = str(specification.get("info", {}).get("version", "unreported"))
    documentation = "https://docs.cbioportal.org/web-api-and-clients/"

    studies_url = f"{api_root}/studies?projection=SUMMARY&pageSize=10000"
    profiles_url = f"{api_root}/studies/brca_tcga_gdc/molecular-profiles"
    studies = _http_json(studies_url, timeout_seconds)
    profiles = _http_json(profiles_url, timeout_seconds)
    gtex_studies = [
        study.get("studyId")
        for study in studies
        if "gtex"
        in " ".join(
            str(study.get(field, ""))
            for field in ("studyId", "name", "description")
        ).lower()
    ]
    brca_expression_profiles = [
        profile["molecularProfileId"]
        for profile in profiles
        if profile.get("molecularAlterationType") == "MRNA_EXPRESSION"
    ]
    t2_summary = {
        "project_id": "brca_tcga_gdc",
        "gene_symbol": "TP53",
        "tcga_expression_profiles": sorted(brca_expression_profiles),
        "gtex_study_count": len(gtex_studies),
        "gtex_study_ids": sorted(value for value in gtex_studies if value),
        "summary_computed": False,
    }
    t2_result = output / "T2/result.json"
    _write_json(t2_result, t2_summary)
    records.append(
        _task_payload(
            "cBioPortal",
            "T2",
            "partial",
            tool_version,
            "public REST API",
            [_relative(t2_result, root), profiles_url, studies_url, documentation],
            t2_summary,
            [
                "The portal exposes TCGA BRCA expression profiles.",
                "No GTEx study was present, so the preregistered cross-source summary "
                "was not computed.",
            ],
        )
    )

    sample_list_url = f"{api_root}/sample-lists/luad_tcga_gdc_sequenced"
    mutation_url = (
        f"{api_root}/molecular-profiles/luad_tcga_gdc_mutations/mutations"
        "?sampleListId=luad_tcga_gdc_sequenced&entrezGeneId=7157"
        "&projection=SUMMARY&pageSize=100000"
    )
    sample_list = _http_json(sample_list_url, timeout_seconds)
    mutations = _http_json(mutation_url, timeout_seconds)
    profiled_samples = set(sample_list.get("sampleIds", []))
    protein_altering_samples = {
        mutation["sampleId"]
        for mutation in mutations
        if mutation.get("mutationType") in PROTEIN_ALTERING_EFFECTS
        and mutation.get("sampleId") in profiled_samples
    }
    effect_counts: dict[str, int] = {}
    for mutation in mutations:
        effect = str(mutation.get("mutationType", "unknown"))
        effect_counts[effect] = effect_counts.get(effect, 0) + 1
    denominator = len(profiled_samples)
    t3_summary = {
        "project_id": "luad_tcga_gdc",
        "gene_symbol": "TP53",
        "entrez_gene_id": 7157,
        "mutated_sample_count": len(protein_altering_samples),
        "total_profiled_sample_count": denominator,
        "mutation_frequency": (
            len(protein_altering_samples) / denominator if denominator else None
        ),
        "protein_altering_effects": sorted(PROTEIN_ALTERING_EFFECTS),
        "all_tp53_event_count": len(mutations),
        "effect_counts": dict(sorted(effect_counts.items())),
    }
    t3_result = output / "T3/result.json"
    _write_json(t3_result, t3_summary)
    records.append(
        _task_payload(
            "cBioPortal",
            "T3",
            "passed" if denominator and protein_altering_samples else "failed",
            tool_version,
            "public REST API",
            [
                _relative(t3_result, root),
                sample_list_url,
                mutation_url,
                specification_url,
            ],
            t3_summary,
            [
                "The denominator is the portal's sequenced LUAD sample list.",
                "Portal study processing differs from the local GDC acquisition.",
            ],
        )
    )

    t4_summary = {
        "hosted_api_reachable": True,
        "api_version": tool_version,
        "mutation_result_sha256": _sha256(t3_result),
        "clean_environment_rebuild_applicable": False,
        "second_rebuild_completed": False,
    }
    t4_result = output / "T4/result.json"
    _write_json(t4_result, t4_summary)
    records.append(
        _task_payload(
            "cBioPortal",
            "T4",
            "partial",
            tool_version,
            "hosted public REST API",
            [_relative(t4_result, root), specification_url, documentation],
            t4_summary,
            [
                "The hosted service is externally operated and cannot be rebuilt "
                "locally as an equivalent clean environment.",
                "A second independent API replay has not been captured.",
            ],
        )
    )

    graph_path = output / "T5/cancer_gene_relationships.csv"
    graph_path.parent.mkdir(parents=True, exist_ok=True)
    pl.DataFrame(
        {
            "gene_symbol": ["TP53"],
            "cancer_type": ["TCGA-LUAD"],
            "relationship": ["MUTATED_IN_CANCER"],
            "weight": [t3_summary["mutation_frequency"]],
            "evidence_source": ["cBioPortal luad_tcga_gdc_mutations"],
        }
    ).write_csv(graph_path)
    t5_summary = {
        "aggregate_edge_count": 1,
        "individual_identifier_hits": _identifier_hits(graph_path),
        "output_sha256": _sha256(graph_path),
    }
    t5_result = output / "T5/result.json"
    _write_json(t5_result, t5_summary)
    records.append(
        _task_payload(
            "cBioPortal",
            "T5",
            "passed" if t5_summary["individual_identifier_hits"] == 0 else "failed",
            tool_version,
            "public REST API with aggregate CSV export",
            [_relative(t5_result, root), _relative(graph_path, root), mutation_url],
            t5_summary,
            [
                "The aggregate export is assembled by the evaluation harness from "
                "portal API results; it is not a native graph export.",
            ],
        )
    )

    for record in records[1:]:
        _write_json(output / record["task_id"] / "task.json", record)
    return records


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


def collect_xena_tasks(
    root_dir: str | Path = ".",
    output_root: str | Path = "outputs/comparative",
) -> list[dict[str, Any]]:
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", FutureWarning)
            import xenaPython as xena
    except ImportError as exc:
        raise RuntimeError(
            "xenaPython is required; install requirements-comparative.txt"
        ) from exc

    root = Path(root_dir).resolve()
    output = root / Path(output_root) / "UCSC Xena"
    records = [collect_xena_t1(root_dir=root, output_root=output_root)]
    hub = xena.PUBLIC_HUBS["toilHub"]
    phenotype_dataset = "TcgaTargetGTEX_phenotype.txt"
    expression_dataset = "TcgaTargetGtex_RSEM_Hugo_norm_count"
    mutation_dataset = "mc3.v0.2.8.PUBLIC.toil.xena"
    fields = ["_study", "_sample_type", "primary disease or tissue"]
    samples = xena.dataset_samples(hub, phenotype_dataset, None)
    field_values = xena.dataset_fetch(hub, phenotype_dataset, samples, fields)
    code_rows = xena.field_codes(hub, phenotype_dataset, fields)
    field_codes = {
        row["name"]: str(row["code"]).split("\t") for row in code_rows
    }

    def decode(field: str, value: Any) -> str | None:
        if value is None or (
            isinstance(value, float) and math.isnan(value)
        ):
            return None
        try:
            return field_codes[field][int(value)]
        except (KeyError, TypeError, ValueError, IndexError):
            return str(value)

    phenotype = [
        (
            sample,
            decode(fields[0], field_values[0][index]),
            decode(fields[1], field_values[1][index]),
            decode(fields[2], field_values[2][index]),
        )
        for index, sample in enumerate(samples)
    ]
    expression_samples = set(xena.dataset_samples(hub, expression_dataset, None))
    brca_tumor = sorted(
        row[0]
        for row in phenotype
        if row[0] in expression_samples
        and row[1] == "TCGA"
        and row[2] == "Primary Tumor"
        and row[3] == "Breast Invasive Carcinoma"
    )
    gtex_breast = sorted(
        row[0]
        for row in phenotype
        if row[0] in expression_samples
        and row[1] == "GTEX"
        and row[3] == "Breast - Mammary Tissue"
    )

    def probe_values(selected_samples: list[str]) -> list[float]:
        response = xena.dataset_probe_values(
            hub,
            expression_dataset,
            selected_samples,
            ["TP53"],
        )
        return [
            float(value)
            for value in response[1][0]
            if str(value) != "NaN" and math.isfinite(float(value))
        ]

    tumor_values = probe_values(brca_tumor)
    normal_values = probe_values(gtex_breast)
    expression_metadata = xena.dataset_metadata(hub, expression_dataset)[0]
    expression_properties = json.loads(expression_metadata["text"])
    t2_summary = {
        "project_id": "TCGA-BRCA",
        "normal_tissue": "Breast - Mammary Tissue",
        "gene_symbol": "TP53",
        "expression_dataset": expression_dataset,
        "dataset_version": expression_properties.get("version"),
        "workflow": expression_properties.get("dataproducer"),
        "expression_unit": expression_properties.get("unit"),
        "tumor_sample_count": len(tumor_values),
        "normal_sample_count": len(normal_values),
        "median_tumor_expression": median(tumor_values),
        "median_normal_expression": median(normal_values),
        "mean_tumor_expression": fmean(tumor_values),
        "mean_normal_expression": fmean(normal_values),
        "median_log2_difference": median(tumor_values) - median(normal_values),
    }
    t2_result = output / "T2/result.json"
    _write_json(t2_result, t2_summary)
    records.append(
        _task_payload(
            "UCSC Xena",
            "T2",
            "passed" if tumor_values and normal_values else "failed",
            "xenaPython 1.0.14 @ f243bbf",
            "pinned Python API and public Toil hub",
            [
                _relative(t2_result, root),
                "https://toil.xenahubs.net",
                "https://ucsc-xena.gitbook.io/project/overview-of-features/accessing-data-through-python",
            ],
            t2_summary,
            [
                "The comparison uses the hosted 2016 Toil recompute rather than "
                "the native GDC and GTEx releases.",
                "The median difference is descriptive and not a batch-corrected effect.",
            ],
        )
    )

    mutation_samples = set(xena.dataset_samples(hub, mutation_dataset, None))
    luad_profiled = sorted(
        row[0]
        for row in phenotype
        if row[0] in mutation_samples
        and row[1] == "TCGA"
        and row[2] == "Primary Tumor"
        and row[3] == "Lung Adenocarcinoma"
    )
    mutation_response = xena.sparse_data(
        hub,
        mutation_dataset,
        luad_profiled,
        "TP53",
    )
    mutation_rows = mutation_response.get("rows", {})
    effects = mutation_rows.get("effect", [])
    mutation_sample_ids = mutation_rows.get("sampleID", [])
    protein_altering_samples = {
        sample
        for sample, effect in zip(mutation_sample_ids, effects, strict=True)
        if effect in PROTEIN_ALTERING_EFFECTS
    }
    effect_counts: dict[str, int] = {}
    for effect in effects:
        effect_counts[str(effect)] = effect_counts.get(str(effect), 0) + 1
    mutation_metadata = xena.dataset_metadata(hub, mutation_dataset)[0]
    mutation_properties = json.loads(mutation_metadata["text"])
    denominator = len(luad_profiled)
    t3_summary = {
        "project_id": "TCGA-LUAD",
        "gene_symbol": "TP53",
        "mutation_dataset": mutation_dataset,
        "dataset_version": mutation_properties.get("version"),
        "mutated_sample_count": len(protein_altering_samples),
        "total_profiled_sample_count": denominator,
        "mutation_frequency": (
            len(protein_altering_samples) / denominator if denominator else None
        ),
        "protein_altering_effects": sorted(PROTEIN_ALTERING_EFFECTS),
        "all_tp53_event_count": len(effects),
        "effect_counts": dict(sorted(effect_counts.items())),
    }
    t3_result = output / "T3/result.json"
    _write_json(t3_result, t3_summary)
    records.append(
        _task_payload(
            "UCSC Xena",
            "T3",
            "passed" if denominator and protein_altering_samples else "failed",
            "xenaPython 1.0.14 @ f243bbf",
            "pinned Python API and public Toil hub",
            [_relative(t3_result, root), "https://toil.xenahubs.net"],
            t3_summary,
            [
                "The denominator is the LUAD primary-tumor intersection with MC3.",
                "MC3/Toil processing differs from the local GDC mutation profile.",
            ],
        )
    )

    t4_summary = {
        "client_pin": "xenaPython 1.0.14 @ f243bbf",
        "hosted_expression_version": expression_properties.get("version"),
        "hosted_mutation_version": mutation_properties.get("version"),
        "expression_result_sha256": _sha256(t2_result),
        "mutation_result_sha256": _sha256(t3_result),
        "clean_environment_rebuild_completed": False,
    }
    t4_result = output / "T4/result.json"
    _write_json(t4_result, t4_summary)
    records.append(
        _task_payload(
            "UCSC Xena",
            "T4",
            "partial",
            "xenaPython 1.0.14 @ f243bbf",
            "pinned Python API and hosted Toil hub",
            [
                _relative(t4_result, root),
                "https://toil.xenahubs.net",
                "https://ucsc-xena.gitbook.io/project/overview-of-features/accessing-data-through-python",
            ],
            t4_summary,
            [
                "Client and hosted dataset versions are recorded with output checksums.",
                "The externally hosted hub was not rebuilt in a clean local environment.",
            ],
        )
    )

    graph_path = output / "T5/cancer_gene_relationships.csv"
    graph_path.parent.mkdir(parents=True, exist_ok=True)
    pl.DataFrame(
        {
            "gene_symbol": ["TP53", "TP53"],
            "cancer_type": ["TCGA-BRCA", "TCGA-LUAD"],
            "relationship": ["EXPRESSION_DIFFERENCE", "MUTATED_IN_CANCER"],
            "weight": [
                t2_summary["median_log2_difference"],
                t3_summary["mutation_frequency"],
            ],
            "evidence_source": [
                expression_dataset,
                mutation_dataset,
            ],
        }
    ).write_csv(graph_path)
    t5_summary = {
        "aggregate_edge_count": 2,
        "individual_identifier_hits": _identifier_hits(graph_path),
        "output_sha256": _sha256(graph_path),
    }
    t5_result = output / "T5/result.json"
    _write_json(t5_result, t5_summary)
    records.append(
        _task_payload(
            "UCSC Xena",
            "T5",
            "passed" if t5_summary["individual_identifier_hits"] == 0 else "failed",
            "xenaPython 1.0.14 @ f243bbf",
            "pinned Python API with aggregate CSV export",
            [_relative(t5_result, root), _relative(graph_path, root), hub],
            t5_summary,
            [
                "The aggregate export is assembled by the evaluation harness from "
                "hosted Xena results; it is not a native graph export.",
            ],
        )
    )

    for record in records[1:]:
        _write_json(output / record["task_id"] / "task.json", record)
    return records


def collect_tcgabiolinks(
    root_dir: str | Path = ".",
    output_root: str | Path = "outputs/comparative",
    image: str = "canceromicslake-tcgabiolinks:bioc-3.21",
) -> list[dict[str, Any]]:
    root = Path(root_dir).resolve()
    output = root / Path(output_root) / "TCGAbiolinks"
    raw = output / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    command = [
        "docker",
        "run",
        "--rm",
        "-v",
        f"{raw.resolve()}:/evidence",
        image,
        "Rscript",
        "/opt/canceromicslake/run_comparative_tasks.R",
    ]
    subprocess.run(command, cwd=root, check=True)
    inspection = subprocess.run(
        ["docker", "image", "inspect", image, "--format", "{{.Id}}"],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    )
    image_id = inspection.stdout.strip()

    runtime = _read_json(raw / "runtime.json")
    expression = _read_json(raw / "expression_capability.json")
    mutation = _read_json(raw / "mutation_capability.json")
    cohort_path = raw / "cohort_discovery.csv"
    if not runtime or not expression or not mutation or not cohort_path.exists():
        raise RuntimeError("TCGAbiolinks container did not produce complete raw evidence")

    cohorts = pl.read_csv(cohort_path)
    version_label = (
        f"TCGAbiolinks {runtime['package_version']}; "
        f"Bioconductor {runtime['bioconductor_version']}; "
        f"image {image_id.removeprefix('sha256:')[:12]}"
    )
    documentation = (
        "https://bioconductor.org/packages/3.21/bioc/html/TCGAbiolinks.html"
    )
    runtime_evidence = _relative(raw / "runtime.json", root)
    records = [
        _task_payload(
            "TCGAbiolinks",
            "T1",
            "passed" if cohorts.height == 3 else "failed",
            version_label,
            "pinned Bioconductor Docker image and live GDC API",
            [_relative(cohort_path, root), runtime_evidence, documentation],
            {
                "projects": cohorts.height,
                "files": int(cohorts["file_count"].sum()),
                "samples": int(cohorts["sample_count"].sum()),
                "cases": int(cohorts["case_count"].sum()),
                "wall_time_seconds": runtime["wall_time_seconds"],
            },
            ["Counts reflect open STAR-Counts files visible at evaluation time."],
        ),
        _task_payload(
            "TCGAbiolinks",
            "T2",
            "partial",
            version_label,
            "pinned Bioconductor Docker image and live GDC API",
            [
                _relative(raw / "expression_capability.json", root),
                runtime_evidence,
                documentation,
            ],
            expression,
            [
                "The package queried TCGA BRCA STAR-Counts metadata.",
                "No GTEx-named package API was available, so the preregistered "
                "TCGA-versus-GTEx TP53 summary was not computed.",
            ],
        ),
        _task_payload(
            "TCGAbiolinks",
            "T3",
            "partial",
            version_label,
            "pinned Bioconductor Docker image and live GDC API",
            [
                _relative(raw / "mutation_capability.json", root),
                runtime_evidence,
                documentation,
            ],
            mutation,
            [
                "Live LUAD masked-mutation metadata supplied a candidate denominator.",
                "Variant files were not downloaded, so the protein-altering TP53 "
                "numerator and frequency were not computed.",
            ],
        ),
        _task_payload(
            "TCGAbiolinks",
            "T4",
            "partial",
            version_label,
            "clean pinned Docker container",
            [runtime_evidence, _relative(cohort_path, root), documentation],
            {
                "clean_container_completed": True,
                "wall_time_seconds": runtime["wall_time_seconds"],
                "cohort_output_sha256": _sha256(cohort_path),
                "image_id": image_id,
                "second_rebuild_completed": False,
            },
            [
                "The clean container run completed with pinned base and package versions.",
                "A second independent rebuild has not yet been executed.",
            ],
        ),
        _task_payload(
            "TCGAbiolinks",
            "T5",
            "partial",
            version_label,
            "documented package API inventory",
            [runtime_evidence, documentation],
            {
                "exported_function_count": len(runtime["exported_functions"]),
                "graph_named_exports": runtime["graph_named_exports"],
                "aggregate_cancer_gene_export_created": False,
            },
            [
                "No graph or Neo4j/GraphML-named export was found in the package API inventory.",
                "This does not prove impossibility; the requested aggregate export was not produced.",
            ],
        ),
    ]
    for record in records:
        _write_json(output / record["task_id"] / "task.json", record)
    return records


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
