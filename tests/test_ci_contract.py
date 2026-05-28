from pathlib import Path


def test_ci_workflow_enforces_demo_gate_and_artifacts() -> None:
    workflow = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")

    assert 'cron: "0 2 * * *"' in workflow
    assert "make run-dbt" in workflow
    assert "make test-dbt" in workflow
    assert "make run-graph-export" in workflow
    assert "make run-demo-check" in workflow
    assert "make run-ingestion-traceability" in workflow
    assert "name: graph-exports" in workflow
