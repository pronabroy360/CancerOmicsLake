# Research Benchmark

## Purpose

The benchmark provides reproducible technical-validation evidence for the CancerOmicsLake aggregate analytical layer.
It is an operational benchmark, not a biological result and not a cross-platform performance competition.

Run:

```bash
make run-research-benchmark
```

Output: `outputs/reports/research_benchmark_report.json`.

## Workloads

The deterministic DuckDB suite covers:

- Cohort-summary scan
- Top LUAD protein-altering mutation-frequency lookup
- Prioritized consensus-candidate lookup
- FDR-filtered pathway aggregation by cancer
- Graph edge-type aggregation
- TP53 tumor-versus-normal lookup

Every workload records its source mart, SHA-256 of the executed SQL, result cardinality, warmup count, repeat count,
and minimum, median, p95, and maximum latency. The report also records source row counts and bytes, Python/DuckDB
versions, machine/platform details, thread count, Git commit, and generation timestamp.

## Interpretation

The default two warmups and seven measured repeats characterize warm analytical response on the recorded machine.
Results must always be reported with hardware, software, threads, dataset rows/bytes, and cap profile. They must not be
presented as universal latency, full-TCGA scale, or superiority over another platform without a matched benchmark.

## Reference Run

The 2026-07-16 local reference run used macOS 15.5 arm64, Python 3.11.15, DuckDB 1.5.4, four threads, two warmups,
and seven measured repeats.

| Workload | Source rows | Median ms | p95 ms |
| --- | ---: | ---: | ---: |
| Cohort summary scan | 1 | 0.274 | 0.277 |
| Top LUAD mutated genes | 18,972 | 1.726 | 1.805 |
| Top consensus candidates | 108,600 | 3.941 | 4.044 |
| Pathway summary by cancer | 5,833 | 0.398 | 0.436 |
| Graph edge-type aggregation | 260,748 | 0.822 | 0.837 |
| TP53 expression lookup | 108,012 | 2.336 | 2.460 |

These values describe one warm local run and are technical-validation evidence only. The JSON report is the source of
truth and should be regenerated on the final tagged release and any comparison hardware.
