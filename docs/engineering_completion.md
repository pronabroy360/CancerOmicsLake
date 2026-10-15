# Engineering Evidence Completion

This phase executes cached-input numerical and workflow studies and prepares an aggregate-only
manuscript package. Existing frozen studies and review bundles remain unchanged.

## Commands

```sh
make setup-engineering-macos
make build-engineering-runtimes
make run-engineering-numerical
make run-engineering-workflow
make build-engineering-package
make finalize-engineering-evidence  # tests, read-only quality, package/recheck, code graph
```

The macOS alternate-Polars runtime lives under `data/research/engineering_runtimes/`; it is created
by the setup target. The Python diagnosis uses the archived source and existing specimen manifest.
The Linux comparison uses the built image ID, pinned numerical dependencies and fixed tolerances.
The historical failed report is retained. A finished diagnostic can still fail numerical acceptance.

The workflow comparison pins tcga-data-nf commit `1069eb9c01b97640fd532ffac8551096d2a2790a` and its
versioned image digest. Its real normalization implementation applies edgeR TMM; ordinary CPM is
not substituted. Both module paths share that normalization backend. The Polars path is a benchmark
extension, not evidence that the pre-existing pipeline already provided this exact normalization.
All 21 nested workloads retain the complete raw-gene universe; TCGA projects and four GTEx tissue
groups remain distinct. Two warmups and seven measurements are repeated in a second pass, with
the tool order reversed. Containers use four CPUs, a 12-GB cap and no network during data processing.

Measured module times exclude the initial raw-table read. Whole-batch wall times include startup
and reads, and memory peaks cover a whole batch. Conversion costs are recorded separately.
Both tools run as AMD64 software under emulation on the same ARM host. Native-script integration
is a separate check, and no Nextflow or network-acquisition performance comparison is claimed.
Fault results identify adapter validation, the evidence guard and manual retry separately.
The extension's intermediate-table I/O and Python child startup are included in its measured time;
this does not isolate intrinsic dataframe-engine speed. The interruption probe pauses after input
parsing and does not test a crash during export or network download.

## New evidence and author gates

The numerical study is `outputs/research/engineering_numerical_v1/`; the cached workflow study is
`outputs/research/engineering_workflow_v1/`. The current manuscript package is built under
`outputs/research/global_evidence_review_v5/`, with a local archive under `outputs/releases/`.
The package manifest verifies each aggregate artifact and scans known individual identifier
strings. It includes a code snapshot and aggregate evidence JSON so its state can be reviewed before
source commits are published. Per-specimen data, gene matrices, source tables and command logs remain private.

On another machine, record a new execution identity instead of replacing a frozen plan. An
independent Linux runtime can be built using `make build-engineering-portable-runtimes`, which
pins a public Python base digest and both Polars versions without requiring the original local
application image. These are new runtime identities, not replacements for the frozen author-run images.
The aggregate archive alone does not contain all data required for a full replay: reviewers must
reconstruct the hashed public processed inputs and obtain/reconstruct the private specimen manifests.
No independent reproduction has yet been performed.

An independent investigator can replay either corrected global study using
`src/operations/engineering_runtime.py replay` with its archived source, original study plan and
a new private output directory, then run `compare_environment_runs` with the fixed tolerance.
For the workflow benchmark, reconstruct the same private workloads from the cached/public sources,
build the digest-pinned software image and invoke the R batch worker twice in new directories.
Compare cohort/gene membership and numerical outputs before interpreting timings. Retain raw logs
and report any unavailable source, image, mismatch or failure. This handoff does not claim someone
has already performed independent reproduction.

Author affiliation, email, funding, competing interests, exact AI disclosure, manuscript review
and responsibility confirmation remain author-supplied requirements. Publication and DOI deposit
stay disabled. The method-development requirements are in `docs/method_research_protocol.md`.


## Executed engineering evidence (2026-10-15)

Cached preparation completed 21 workload equivalence cells and 84 tool/pass/workload summaries in two passes. Module comparability: True. Native-script comparable outputs: 7/7. Full tests: 297 passed; read-only silver quality: passed (65 checks). Strict numerical sensitivity failures remain retained. Shared TMM normalization and emulated hardware prohibit an end-to-end superiority claim. Independent human reproduction is unverified; author declarations and publication approval remain pending. Publication and DOI deposit are disabled. See the separate v5 review.
