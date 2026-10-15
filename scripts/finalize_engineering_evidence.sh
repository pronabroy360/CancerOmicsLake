#!/bin/sh
# Finish evidence after the existing benchmark, without model polling.
set -eu
cd "$(dirname "$0")/.."
export POLARS_MAX_THREADS=4 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
PYTHON=${PYTHON:-.venv/bin/python}
STATE=outputs/research/engineering_acceptance_v1/finalization.json
mkdir -p "$(dirname "$STATE")" data/research/engineering_acceptance_v1
stage=starting
record_state() {
    "$PYTHON" -c 'import json,sys; from pathlib import Path; Path(sys.argv[1]).write_text(json.dumps(dict(status=sys.argv[2],stage=sys.argv[3],publication_enabled=False),indent=2)+"\n")' "$STATE" "$1" "$stage"
}
trap 'record_state failed; exit 1' HUP INT TERM
trap 'code=$?; if [ "$code" -ne 0 ]; then record_state failed; fi' EXIT
if [ "${1:-}" = --wait-for-pid ]; then
    pid=${2:?A benchmark process ID is required}
    case "$pid" in *[!0-9]*|'') echo 'Invalid process ID' >&2; exit 2;; esac
    stage=waiting_for_existing_benchmark
    record_state running
    while kill -0 "$pid" 2>/dev/null; do sleep 30; done
elif [ "$#" -ne 0 ]; then
    echo 'Usage: finalize_engineering_evidence.sh [--wait-for-pid PID]' >&2
    exit 2
fi
stage=checking_executed_reports
record_state running
"$PYTHON" - <<'PY'
import json
from pathlib import Path
from src.operations.engineering_evidence import verify
for name in ('engineering_numerical_v1', 'engineering_workflow_v1'):
    report=json.loads((Path('outputs/research')/name/'report.json').read_text())
    if report['execution_status'] != 'completed':
        raise RuntimeError(f'{name} execution is incomplete')
    verify(report['resources'])
PY
if [ ! -f outputs/research/global_evidence_review_v5/package_manifest.json ]; then
    stage=tests_and_read_only_quality
    record_state running
    "$PYTHON" -m pytest -q > data/research/engineering_acceptance_v1/pytest.log 2>&1
    "$PYTHON" - <<'PY'
import json, re
from collections import Counter
from pathlib import Path
from src.operations.engineering_evidence import resource
from src.quality.checks import run_silver_quality_checks, build_quality_payload
log=Path('data/research/engineering_acceptance_v1/pytest.log')
counts=re.findall(r'(\d+) passed',log.read_text())
if not counts:
    raise RuntimeError('No successful test summary')
quality=build_quality_payload('engineering_acceptance_v1',run_silver_quality_checks())
if quality['status']=='failed':
    raise RuntimeError('Read-only silver quality failed')
paths=list(Path('src/operations').glob('engineering*.py'))
paths += [Path(p) for p in ('src/operations/workflow_benchmark.py','src/quality/checks.py',
    'research/engineering_external.R','research/engineering_figures.R','scripts/finalize_engineering_evidence.sh')]
payload=dict(tests_passed=True,test_returncode=0,passed_tests=int(counts[-1]),
    silver_quality_status=quality['status'],silver_quality_check_count=len(quality['checks']),
    quality_status_counts=dict(Counter(r['status'] for r in quality['checks'])),
    pytest_log=resource(log),code_resources=[resource(p) for p in sorted(set(paths))],publication_enabled=False)
Path('outputs/research/engineering_acceptance_v1/verification.json').write_text(json.dumps(payload,indent=2)+'\n')
report=json.loads(Path('outputs/research/engineering_workflow_v1/report.json').read_text())
native=report['native_script_integration']
text=('\n\n## Executed engineering evidence (2026-10-15)\n\n'
    f"Cached preparation completed {len(report['comparisons'])} workload equivalence cells and "
    f"{len(report['timings'])} tool/pass/workload summaries in two passes. Module comparability: "
    f"{report['comparability_passed']}. Native-script comparable outputs: "
    f"{sum(bool(r['comparable']) for r in native)}/{len(native)}. "
    f"Full tests: {int(counts[-1])} passed; read-only silver quality: {quality['status']} "
    f"({len(quality['checks'])} checks). Strict numerical sensitivity failures remain retained. "
    'Shared TMM normalization and emulated hardware prohibit an end-to-end superiority claim. '
    'Independent human reproduction is unverified; author declarations and publication approval '
    'remain pending. Publication and DOI deposit are disabled. See the separate v5 review.\n')
for name in ('docs/engineering_completion.md','WORKLOGS.md','docs/research_goal_audit.md'):
    path=Path(name)
    if '## Executed engineering evidence (2026-10-15)' not in path.read_text():
        with path.open('a') as stream: stream.write(text)
PY
fi
stage=building_and_rechecking_v5
record_state running
"$PYTHON" -m src.operations.engineering_package
"$PYTHON" -m src.operations.engineering_package
stage=updating_code_graph
record_state running
graphify update .
stage=complete_preparation_only
record_state completed
