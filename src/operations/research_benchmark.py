from __future__ import annotations

from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
import platform
import statistics
import subprocess
import time
from typing import Any

import duckdb


WORKLOADS = (
    {
        "name": "cohort_summary_scan",
        "file": "gold_cohort_summary.parquet",
        "sql": "select * from read_parquet('{path}')",
    },
    {
        "name": "top_luad_mutated_genes",
        "file": "gold_mutation_frequency_by_gene.parquet",
        "sql": (
            "select gene_symbol, mutation_frequency from read_parquet('{path}') "
            "where cancer_type = 'TCGA-LUAD' order by mutation_frequency desc, gene_symbol limit 20"
        ),
    },
    {
        "name": "top_consensus_candidates",
        "file": "gold_consensus_candidate_genes.parquet",
        "sql": (
            "select cancer_type, gene_symbol, consensus_score from read_parquet('{path}') "
            "where consensus_decision = 'prioritized' order by consensus_score desc, gene_symbol limit 50"
        ),
    },
    {
        "name": "pathway_summary_by_cancer",
        "file": "gold_pathway_enrichment.parquet",
        "sql": (
            "select cancer_type, count(*) as pathway_count from read_parquet('{path}') "
            "where fdr_q_value <= 0.05 group by cancer_type order by cancer_type"
        ),
    },
    {
        "name": "graph_edge_type_aggregation",
        "file": "gold_graph_edges.parquet",
        "sql": (
            "select edge_type, count(*) as edge_count from read_parquet('{path}') "
            "group by edge_type order by edge_count desc"
        ),
    },
    {
        "name": "tp53_expression_lookup",
        "file": "gold_tumor_vs_normal_expression.parquet",
        "sql": (
            "select cancer_type, log2_fold_change from read_parquet('{path}') "
            "where upper(gene_symbol) = 'TP53' order by cancer_type"
        ),
    },
)


def _percentile(values: list[float], percentile: float) -> float:
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * percentile
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def _git_commit() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else "unknown"


def _safe_sql_path(path: Path) -> str:
    return str(path.resolve()).replace("'", "''")


def run_research_benchmark(
    gold_dir: str | Path = "data/gold",
    output_path: str | Path = "outputs/reports/research_benchmark_report.json",
    repeats: int = 7,
    warmups: int = 2,
    threads: int = 4,
) -> dict[str, Any]:
    if repeats < 1 or warmups < 0 or threads < 1:
        raise ValueError("repeats and threads must be positive; warmups must be non-negative")

    root = Path(gold_dir)
    connection = duckdb.connect(":memory:")
    connection.execute(f"set threads = {int(threads)}")
    datasets: dict[str, dict[str, Any]] = {}
    results: list[dict[str, Any]] = []

    try:
        for workload in WORKLOADS:
            path = root / str(workload["file"])
            if not path.exists():
                results.append(
                    {
                        "name": workload["name"],
                        "status": "skipped_missing_input",
                        "dataset": str(path),
                    }
                )
                continue

            sql = str(workload["sql"]).format(path=_safe_sql_path(path))
            try:
                if str(path) not in datasets:
                    row_count = int(
                        connection.execute(
                            f"select count(*) from read_parquet('{_safe_sql_path(path)}')"
                        ).fetchone()[0]
                    )
                    datasets[str(path)] = {
                        "path": str(path),
                        "bytes": path.stat().st_size,
                        "row_count": row_count,
                    }

                for _ in range(warmups):
                    connection.execute(sql).fetchall()

                latencies: list[float] = []
                result_rows = 0
                for _ in range(repeats):
                    started = time.perf_counter_ns()
                    rows = connection.execute(sql).fetchall()
                    elapsed_ms = (time.perf_counter_ns() - started) / 1_000_000
                    latencies.append(elapsed_ms)
                    result_rows = len(rows)

                results.append(
                    {
                        "name": workload["name"],
                        "status": "passed",
                        "dataset": str(path),
                        "query_sha256": hashlib.sha256(str(workload["sql"]).encode("utf-8")).hexdigest(),
                        "result_rows": result_rows,
                        "repeats": repeats,
                        "warmups": warmups,
                        "latency_ms": {
                            "min": round(min(latencies), 3),
                            "median": round(statistics.median(latencies), 3),
                            "p95": round(_percentile(latencies, 0.95), 3),
                            "max": round(max(latencies), 3),
                        },
                    }
                )
            except Exception as exc:
                results.append(
                    {
                        "name": workload["name"],
                        "status": "failed",
                        "dataset": str(path),
                        "error": str(exc),
                    }
                )
    finally:
        connection.close()

    statuses = {str(result["status"]) for result in results}
    status = "passed"
    if "failed" in statuses:
        status = "failed"
    elif "skipped_missing_input" in statuses:
        status = "passed_with_warnings"

    payload = {
        "schema_version": "1.0",
        "generated_at": datetime.now(UTC).isoformat(),
        "status": status,
        "git_commit": _git_commit(),
        "scope": "aggregate_queries_over_gold_parquet",
        "environment": {
            "python": platform.python_version(),
            "duckdb": duckdb.__version__,
            "platform": platform.platform(),
            "machine": platform.machine(),
            "processor": platform.processor() or "unknown",
            "threads": threads,
        },
        "datasets": list(datasets.values()),
        "workloads": results,
        "interpretation": (
            "Warm analytical query timings for this recorded environment only; not a cross-system performance claim."
        ),
    }
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload
