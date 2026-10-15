"""Cached-input engineering comparison using the published preparation methods."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import time
import uuid

import numpy as np
import polars as pl

from src.analytics.controlled_reference_study import lock_plan, sha256_file
from src.operations.engineering_evidence import image_id, resource, verify, write_once

ROOT = Path("outputs/research/engineering_workflow_v1")
PRIVATE = Path("data/research/engineering_workflow_v1")
IMAGE = "canceromicslake-workflow:20261015"
SEED = 20261015
COMMIT = "1069eb9c01b97640fd532ffac8551096d2a2790a"


def select_specimens(manifest: pl.DataFrame, maximum: int = 30) -> pl.DataFrame:
    required = ("source", "cohort", "tissue_site", "recount_sample_id", "unit_id")
    if any(c not in manifest.columns for c in required) or manifest.select(
            pl.any_horizontal([pl.col(c).is_null() for c in required]).any()).item():
        raise ValueError("Missing benchmark specimen metadata")
    rows = []
    for block in manifest.partition_by("source", "cohort", "tissue_site", maintain_order=True):
        records = sorted(block.to_dicts(), key=lambda r: hashlib.sha256(
            f"{SEED}|{r['source']}|{r['unit_id']}|{r['recount_sample_id']}".encode()).hexdigest())
        seen, selected = set(), []
        for row in records:
            if row["unit_id"] not in seen:
                seen.add(row["unit_id"])
                selected.append(row)
        if len(selected) < maximum:
            raise ValueError("Benchmark group has fewer than 30 distinct biological units")
        source, cohort, tissue = (selected[0][c] for c in ("source", "cohort", "tissue_site"))
        suffix = "_sigmoid" if "Sigmoid" in tissue else "_transverse" if "Transverse" in tissue else ""
        key = f"{source.lower()}_{cohort.lower()}{suffix}"
        for rank, row in enumerate(selected[:maximum], 1):
            rows.append({**row, "benchmark_group": key, "nested_rank": rank})
    return pl.DataFrame(rows).sort("benchmark_group", "nested_rank")


def compare_expression(first: Path, second: Path) -> dict:
    a, b = [pl.read_csv(p, separator="\t", infer_schema_length=1000) for p in (first, second)]
    if not a.columns or not b.columns:
        raise ValueError("Empty expression export")
    a = a.rename({a.columns[0]: "gene_id"})
    b = b.rename({b.columns[0]: "gene_id"})
    if (a.columns != b.columns or a.height != b.height or a["gene_id"].n_unique() != a.height or
            b["gene_id"].n_unique() != b.height or a["gene_id"].to_list() != b["gene_id"].to_list()):
        return {"comparable": False, "reason": "gene/sample membership or ordering differs"}
    x, y = [f.select(f.columns[1:]).to_numpy().astype(float) for f in (a, b)]
    finite = np.isfinite(x).all() and np.isfinite(y).all()
    same = bool(finite and np.allclose(x, y, rtol=1e-10, atol=1e-12))
    return {"comparable": same, "gene_count": a.height, "sample_count": len(a.columns) - 1,
            "maximum_absolute_difference": float(np.max(np.abs(x-y))) if finite and x.size else None,
            "rtol": 1e-10, "atol": 1e-12}


def docker_command(image: str, arguments: list[str]) -> list[str]:
    return ["docker", "run", "--rm", "--platform", "linux/amd64", "--cpus", "4", "--memory", "12g", "--network", "none",
            "-e", "POLARS_MAX_THREADS=4", "-e", "OPENBLAS_NUM_THREADS=1", "-e", "OMP_NUM_THREADS=1",
            "-v", f"{Path.cwd()}:/app", "-w", "/app", image, *arguments]


def run_container(image: str, arguments: list[str], log: Path, environment: dict | None = None) -> dict:
    log.parent.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    with log.open("w") as stream:
        command = docker_command(image, arguments)
        if environment:
            location = command.index(image)
            command[location:location] = [x for k, v in environment.items() for x in ("-e", f"{k}={v}")]
        result = subprocess.run(command, stdout=stream, stderr=subprocess.STDOUT)
    return {"returncode": result.returncode, "wall_seconds_including_container": time.monotonic() - started}


def failure_experiments(image: str) -> list[dict]:
    directory = PRIVATE / "faults"
    directory.mkdir(exist_ok=True)
    clean = directory / "clean.tsv"
    clean.write_text("gene_id\tsampleA\tsampleB\nsafeGene1\t10\t20\nsafeGene2\t20\t10\nsafeGene3\t5\t9\n")
    faults = {"corrupted_input": clean.read_text().replace("10", "broken", 1),
              "missing_metadata": clean.read_text().replace("gene_id", "missing_gene_metadata", 1),
              "conflicting_duplicate": clean.read_text() + "safeGene1\t999\t999\n"}
    results = []
    for name, text in faults.items():
        source = directory / f"{name}.tsv"
        source.write_text(text)
        for tool in ("reference", "extension"):
            target = directory / f"{name}_{tool}_output.tsv"
            target.unlink(missing_ok=True)
            result = run_container(image, ["Rscript", "research/engineering_external.R", tool, str(source), str(target)],
                                   directory / f"{name}_{tool}.log")
            results.append({"scenario": name, "tool": tool, "rejected": result["returncode"] != 0,
                            "incorrect_output_committed": target.exists(), "validation_layer": "shared benchmark adapter and R parser"})
    evidence = resource(clean)
    clean.write_text(clean.read_text().replace("10", "11", 1))
    rejected = False
    try:
        verify([evidence])
    except ValueError:
        rejected = True
    results.append({"scenario": "stale_evidence", "tool": "evidence_orchestrator", "rejected": rejected,
                    "validation_layer": "CancerOmicsLake evidence hash guard; external native capability unmeasured"})
    clean.write_text("gene_id\tsampleA\tsampleB\nsafeGene1\t10\t20\nsafeGene2\t20\t10\nsafeGene3\t5\t9\n")
    for tool in ("reference", "extension"):
        marker = directory / f"{tool}_paused.txt"
        marker.unlink(missing_ok=True)
        target = directory / f"{tool}_interrupt.tsv"
        target.unlink(missing_ok=True)
        name = f"canceromics-interrupt-{uuid.uuid4().hex[:10]}"
        command = docker_command(image, ["Rscript", "research/engineering_external.R", tool, str(clean), str(target)])
        location = command.index(image)
        command[location:location] = ["--name", name, "-e", f"ENGINEERING_PAUSE_MARKER={marker}"]
        with (directory / f"{tool}_interrupt.log").open("w") as stream:
            process = subprocess.Popen(command, stdout=stream, stderr=subprocess.STDOUT)
            deadline = time.monotonic() + 60
            while not marker.exists() and process.poll() is None and time.monotonic() < deadline:
                time.sleep(.2)
            reached = marker.exists()
            subprocess.run(["docker", "kill", name], capture_output=True, check=False)
            process.wait(timeout=30)
        committed_before_recovery = target.exists()
        recovery = run_container(image, ["Rscript", "research/engineering_external.R", tool, str(clean), str(target)],
                                 directory / f"{tool}_recovery.log")
        results.append({"scenario": "interrupted_execution", "tool": tool,
                        "paused_after_real_input_read": reached, "incorrect_output_committed": committed_before_recovery,
                        "recovery_completed": recovery["returncode"] == 0 and target.exists(),
                        "validation_layer": "actual module call with explicit pause hook; fresh retry, not native automatic resume"})
    recovery = compare_expression(directory / "reference_interrupt.tsv", directory / "extension_interrupt.tsv")
    results.append({"scenario": "recovery_equivalence", "tool": "shared", **recovery,
                    "validation_layer": "recovered real module outputs"})
    return results


def native_integration(image: str, workloads: list[dict]) -> list[dict]:
    selected = pl.read_parquet(PRIVATE / "specimen_manifest.parquet")
    directory = PRIVATE / "native_script"
    directory.mkdir(exist_ok=True)
    results = []
    for workload in (w for w in workloads if w["size"] == 30):
        key = workload["group"]
        block = selected.filter(pl.col("benchmark_group") == key).sort("nested_rank")
        row = block.row(0, named=True)
        source = row["source"].lower()
        cohort = row["cohort"]
        metadata_path = Path("data/bronze/recount3") / source / cohort / f"{source}.{source}.{cohort}.MD.gz"
        metadata = pl.read_csv(metadata_path, separator="\t", infer_schema_length=0).filter(
            pl.col("external_id").is_in(block["recount_sample_id"]))
        if source == "tcga":
            metadata = metadata.select("external_id", pl.col("tcga_barcode").alias("tcga.tcga_barcode"))
        else:
            metadata = metadata.select("external_id", "SAMPID", "SMTSD")
        meta = directory / f"{key}_metadata.tsv"
        metadata.write_csv(meta, separator="\t")
        rds = directory / f"{key}.rds"
        adapter = run_container(image, ["Rscript", "research/engineering_external.R", "make-rds", workload["input"],
                                str(meta), "data/bronze/recount3/human.gene_sums.G026.gtf.gz", str(rds)],
                                directory / f"{key}_adapter.log")
        result = {"group": key, "adapter": adapter, "execution_status": "failed", "comparable": False}
        if adapter["returncode"] == 0:
            output = directory / f"{key}.tsv"
            command = ["Rscript", "data/research/engineering_sources/tcga-data-nf/prepare_expression_recount.R",
                       "--project", f"{source}_{cohort.lower()}", "--expression", str(rds),
                       "--output_rds", str(directory / f"{key}_prepared.rds"), "--output_table", str(output),
                       "--output_pca", str(directory / f"{key}_pca.png"), "--normalization", "cpm",
                       "--th_purity", "0", "--min_tpm", "1", "--frac_samples", "0.2",
                       "--batch_correction", "", "--adjustment_variable", "", "--tissue_type", "all"]
            execution = run_container(image, command, directory / f"{key}_execution.log")
            result.update(execution=execution, execution_status="completed" if execution["returncode"] == 0 else "failed")
            if output.exists() and execution["returncode"] == 0:
                frame = pl.read_csv(output, separator="\t")
                frame = frame.rename({frame.columns[0]: "gene_id"})
                if source == "tcga":
                    mapping = {r["tcga.tcga_barcode"]: r["external_id"] for r in metadata.to_dicts()}
                    frame = frame.rename({c: mapping[c] for c in frame.columns[1:] if c in mapping})
                expected = pl.read_csv(PRIVATE / "pass1_reference" / f"{workload['key']}.tsv", separator="\t")
                if set(frame.columns) == set(expected.columns):
                    frame = frame.select(expected.columns).sort("gene_id")
                canonical = directory / f"{key}_canonical.tsv"
                frame.write_csv(canonical, separator="\t")
                result.update(compare_expression(PRIVATE / "pass1_reference" / f"{workload['key']}.tsv", canonical))
        results.append(result)
    return results


def prepare_inputs() -> tuple[list[dict], list[dict], list[dict]]:
    report = json.loads(Path("outputs/research/matched_processing_v1/report.json").read_text())
    manifest_path = Path(report["private_manifest_resource"]["path"])
    verify([report["private_manifest_resource"]])
    manifest = pl.read_parquet(manifest_path)
    selected = select_specimens(manifest)
    PRIVATE.mkdir(parents=True, exist_ok=True)
    selected.write_parquet(PRIVATE / "specimen_manifest.parquet")
    resources = [resource(manifest_path)]
    workloads, audit = [], []
    for block in selected.partition_by("benchmark_group", maintain_order=True):
        row = block.row(0, named=True)
        source, cohort, key = row["source"].lower(), row["cohort"], row["benchmark_group"]
        path = Path("data/bronze/recount3") / source / cohort / f"{source}.gene_sums.{cohort}.G026.gz"
        resources.append(resource(path))
        ids = block.sort("nested_rank")["recount_sample_id"].to_list()
        counts = pl.read_csv(path, separator="\t", skip_rows=2, columns=["gene_id", *ids]).sort("gene_id")
        if counts["gene_id"].n_unique() != counts.height or counts.null_count().sum_horizontal().sum():
            raise ValueError("Duplicate genes or missing measurements in benchmark input")
        for size in (10, 20, 30):
            target = PRIVATE / "inputs" / f"{key}_{size}.tsv"
            target.parent.mkdir(exist_ok=True)
            counts.select("gene_id", *ids[:size]).write_csv(target, separator="\t")
            workloads.append({"key": f"{key}_{size}", "group": key, "size": size,
                              "input": str(target), "gene_count": counts.height})
        audit.append({"group": key, "available_specimens": manifest.filter(
            (pl.col("source") == row["source"]) & (pl.col("cohort") == cohort) &
            (pl.col("tissue_site") == row["tissue_site"])).height,
                      "selected_units": block["unit_id"].n_unique(), "gene_count": counts.height})
    (PRIVATE / "workloads.json").write_text(json.dumps(workloads, indent=2))
    return workloads, audit, resources


def benchmark() -> dict:
    image = image_id(IMAGE)
    if (ROOT / "report.json").exists():
        old = json.loads((ROOT / "report.json").read_text())
        verify(old["resources"])
        if old["image_id"] != image:
            raise ValueError("Benchmark image drift")
        return old
    adapter_started = time.monotonic()
    workloads, audit, resources = prepare_inputs()
    input_adapter = {"wall_seconds": time.monotonic() - adapter_started,
                     "output_bytes": sum(Path(w["input"]).stat().st_size for w in workloads),
                     "scope": "one-time extraction/serialization of identical cached raw counts for both tools"}
    runtime_path = PRIVATE / "external_runtime.json"
    result = run_container(image, ["Rscript", "research/engineering_external.R", "runtime", str(runtime_path)],
                           PRIVATE / "runtime.log")
    if result["returncode"]:
        raise RuntimeError("Official external package runtime failed; inspect private runtime.log")
    runtime = json.loads(runtime_path.read_text())
    python_runtime = json.loads(subprocess.check_output(docker_command(image, ["python3", "-c",
        "import json,platform,polars,numpy; print(json.dumps(dict(python=platform.python_version(),polars=polars.__version__,numpy=numpy.__version__,machine=platform.machine())))"]), text=True))
    if runtime.get("memory_limit_bytes") != 12 * 1024**3 or runtime.get("cpu_quota") != "400000 100000":
        raise ValueError("Benchmark container resource limits differ")
    if python_runtime["polars"] != "1.42.1" or python_runtime["numpy"] != "2.2.6":
        raise ValueError("Benchmark extension dependency drift")
    if "calcNormFactors" not in runtime["normalization_source"] or ">=" not in runtime["filtering_source"]:
        raise ValueError("External normalization/filtering semantics differ; do not freeze benchmark")
    if runtime.get("boundary_kept") != [1, 3]:
        raise ValueError("Published filtering boundary smoke test failed")
    preflight = []
    for tool in ("reference", "extension"):
        result = run_container(image, ["Rscript", "research/engineering_external.R", "batch",
                               str(PRIVATE / "workloads.json"), tool, str(PRIVATE / f"preflight_{tool}")],
                               PRIVATE / f"preflight_{tool}.log", {"ENGINEERING_PREFLIGHT": "1"})
        if result["returncode"]:
            raise RuntimeError(f"Shared-task preflight failed for {tool}; inspect the private log")
    for w in workloads:
        preflight.append({"workload": w["key"], **compare_expression(
            PRIVATE / "preflight_reference" / f"{w['key']}.tsv", PRIVATE / "preflight_extension" / f"{w['key']}.tsv")})
    resources += [resource(Path(__file__)), resource(Path("research/engineering_external.R")),
                  resource(Path("src/operations/engineering_evidence.py")),
                  resource(Path("src/operations/engineering_runtime.py")), resource(Path("research/Dockerfile.workflow")), resource(runtime_path),
                  resource(PRIVATE / "specimen_manifest.parquet"), resource(PRIVATE / "workloads.json")]
    resources += [resource(Path(w["input"])) for w in workloads]
    resources += [resource(Path("data/research/engineering_sources/tcga-data-nf/prepare_expression_recount.R")),
                  resource(Path("data/bronze/recount3/human.gene_sums.G026.gtf.gz"))]
    resources += [resource(p) for p in Path("data/bronze/recount3").glob("*/*/*.MD.gz")]
    plan = {"study_id": ROOT.name, "seed": SEED, "external_commit": COMMIT, "image_id": image,
            "runtime": runtime, "extension_runtime": python_runtime,
            "host_platform": platform.platform(), "host_machine": platform.machine(),
            "resources": resources, "workloads": [{k: v for k, v in w.items() if k != "input"}
                                                                         for w in workloads],
            "preflight_equivalence": preflight,
            "settings": {"cpus": 4, "memory_bytes": 12 * 1024**3, "warmups": 2, "measured": 7,
                         "passes": 2, "threshold": 1., "prevalence": .2, "inclusive": True,
                         "normalization": "official edgeR TMM coverage-CPM shared backend",
                         "purity_filter": False, "batch_correction": False},
            "measurement_scope": "direct published normalization/filter module; no Nextflow speed claim",
            "extension": "CancerOmicsLake benchmark extension uses the same R normalization backend plus Polars filtering/export"}
    plan_hash = lock_plan(ROOT / "study_plan.json", plan)
    runs = []
    for trial in (1, 2):
        for tool in (("reference", "extension") if trial == 1 else ("extension", "reference")):
            target = PRIVATE / f"pass{trial}_{tool}"
            result = run_container(image, ["Rscript", "research/engineering_external.R", "batch",
                                   str(PRIVATE / "workloads.json"), tool, str(target)], PRIVATE / f"pass{trial}_{tool}.log")
            if result["returncode"]:
                raise RuntimeError(f"External benchmark {tool} pass {trial} failed; keep failure log")
            runs.append({"pass": trial, "tool": tool, **result,
                         "memory": json.loads((target / "memory.json").read_text())})
            print(f"benchmark pass {trial} {tool} completed", flush=True)
    comparisons, timings = [], []
    for w in workloads:
        row = {"workload": w["key"], "group": w["group"], "sample_count": w["size"], "input_genes": w["gene_count"]}
        paths = [PRIVATE / f"pass{p}_{t}" / f"{w['key']}.tsv" for p in (1, 2) for t in ("reference", "extension")]
        row.update(compare_expression(paths[0], paths[1]))
        row["reference_deterministic"] = sha256_file(paths[0]) == sha256_file(paths[2])
        row["extension_deterministic"] = sha256_file(paths[1]) == sha256_file(paths[3])
        row["performance_comparison_allowed"] = row["comparable"] and row["reference_deterministic"] and row["extension_deterministic"]
        comparisons.append(row)
    for run in runs:
        frame = pl.read_csv(PRIVATE / f"pass{run['pass']}_{run['tool']}" / "timings.csv")
        for block in frame.filter(pl.col("measured")).partition_by("key"):
            timings.append({"pass": run["pass"], "tool": run["tool"], "workload": block["key"][0],
                            "measured_executions": block.height,
                            "median_seconds": block["elapsed_seconds"].median(),
                            "minimum_seconds": block["elapsed_seconds"].min(),
                            "maximum_seconds": block["elapsed_seconds"].max(),
                            "median_normalization_seconds": block["normalization_seconds"].median(),
                            "output_bytes": block["output_bytes"][-1]})
    verify(resources)
    ROOT.mkdir(parents=True, exist_ok=True)
    pl.DataFrame(comparisons).write_csv(ROOT / "correctness.csv")
    pl.DataFrame(timings).write_csv(ROOT / "timings.csv")
    private_results = [resource(p) for p in PRIVATE.glob("pass*/*") if p.is_file()]
    report = {"study_id": ROOT.name, "plan_sha256": plan_hash, "execution_status": "completed", "image_id": image,
              "evidence_completeness": len(comparisons) == 21 and len(timings) == 84,
              "comparability_passed": all(r["performance_comparison_allowed"] for r in comparisons),
              "comparisons": comparisons, "timings": timings, "runs": runs, "cohort_audit": audit,
              "failure_experiments": failure_experiments(image), "input_adapter": input_adapter,
              "native_script_integration": native_integration(image, workloads),
              "publication_enabled": False, "individual_identifiers_exported": False,
              "limitations": [plan["measurement_scope"], plan["extension"],
                              "Memory peak is measured over a whole tool batch, not separately for each iteration",
                              "Both benchmark paths use the same AMD64 image under emulation on an ARM host",
                              "Warm process and OS file cache behavior differ from fresh-host cold starts",
                              "No superiority is inferred from incomplete or non-equivalent tasks"],
              "resources": resources + private_results + [resource(p) for name in ("faults", "native_script")
                                                          for p in (PRIVATE / name).glob("*") if p.is_file()] +
                  [resource(ROOT / "correctness.csv"), resource(ROOT / "timings.csv")]}
    write_once(ROOT / "report.json", report)
    return report


if __name__ == "__main__":
    argparse.ArgumentParser().parse_args()
    print(benchmark()["execution_status"])
