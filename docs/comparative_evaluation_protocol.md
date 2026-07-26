# Comparative Evaluation Protocol

## Objective

Evaluate CancerOmicsLake against established tools without using an unfair single performance score.
The comparison asks whether a reviewer can reproduce defined TCGA/GTEx engineering tasks and audit
their provenance. It does not claim that tools with different purposes are inferior.

Required comparators:

- TCGAbiolinks
- UCSC Xena
- cBioPortal

Primary references:

- [TCGAbiolinks Bioconductor documentation](https://bioconductor.org/packages/release/bioc/html/TCGAbiolinks.html)
- [UCSC Xena platform paper](https://pubmed.ncbi.nlm.nih.gov/32444850/)
- [cBioPortal platform paper](https://pubmed.ncbi.nlm.nih.gov/22588877/)

## Preregistered Tasks

### T1. Cohort discovery

Retrieve open metadata for TCGA-BRCA, TCGA-COAD, and TCGA-LUAD and report project, file, sample, and
case counts with source timestamps.

### T2. Tumor-normal expression

Produce a TP53 tumor-normal summary for BRCA using TCGA tumor and GTEx breast reference data. Record
expression unit, workflow, gene identifier normalization, sample counts, and caveats.

### T3. Mutation denominator

Report LUAD protein-altering TP53 mutation frequency with an explicit profiled-sample denominator
and consequence-filter definition.

### T4. Reproducible rebuild

Starting from a clean environment, regenerate the requested result and capture commands, versions,
wall time, peak memory when available, output checksum, and failure/retry behavior.

### T5. Publication-safe export

Export an aggregate cancer-gene relationship table and verify that no patient, donor, or sample
identifier is present.

## Measurements

Record each task using:

| Field | Meaning |
| --- | --- |
| `task_status` | passed, partial, unsupported, or failed |
| `tool_version` | Exact software or hosted-resource version/date |
| `execution_mode` | CLI, API, R package, hosted UI, or local web application |
| `steps_to_result` | Count of documented user actions or commands |
| `wall_time_seconds` | Same-machine time where locally executable |
| `peak_memory_mb` | Same-machine peak memory where measurable |
| `output_sha256` | Output checksum where export is supported |
| `provenance_fields` | Source URL/version, workflow, unit, denominator, timestamp, checksum |
| `rebuild_result` | Whether a second run reproduces the output |
| `limitations` | Tool-purpose differences and unsupported comparisons |

Runtime and memory may only be compared when tools execute on the same machine over equivalent
inputs. Hosted-service latency must be reported separately and never ranked against local execution.

## Execution Controls

- Freeze tool versions and record the evaluation date.
- Use only open-access data.
- Use the same cancer projects, gene symbols, and requested outputs.
- Preserve raw command logs and machine-readable result files.
- Repeat local timing tasks seven times after two warmups.
- Do not infer an unsupported feature from missing documentation; record it as unverified.
- Have a second person reproduce at least T2 and T3 before manuscript submission.

## Required Report Contract

Write `outputs/reports/comparative_evaluation_report.json`:

```json
{
  "status": "passed",
  "protocol_version": "1.0",
  "comparators": ["TCGAbiolinks", "UCSC Xena", "cBioPortal"],
  "tasks": [
    {
      "tool": "TCGAbiolinks",
      "task_id": "T1",
      "task_status": "passed",
      "tool_version": "RECORD_EXACT_VERSION",
      "evidence": ["outputs/comparative/TCGAbiolinks/T1/result.json"]
    }
  ],
  "claim_boundary": "Capability and reproducibility comparison, not a universal tool ranking."
}
```

The example contains one row for brevity; the completed report needs all 15 tool-task combinations.
`status=passed` requires every tool to have an evidence-backed result for every task, including
`unsupported` where the tool's documented scope does not provide the capability. Failed execution,
missing version information, or absent raw evidence cannot pass.

## Interpretation

The expected contribution is not that CancerOmicsLake replaces established portals or analysis
packages. The testable advantage is integrated provenance, lakehouse contracts, denominator
semantics, multi-reference sensitivity, quality gates, and aggregate-safe release from one
reproducible workflow.
