from pathlib import Path


def test_manual_ingestion_workflow_contract() -> None:
    workflow = Path(".github/workflows/manual_ingestion.yml").read_text(encoding="utf-8")

    assert "workflow_dispatch" in workflow
    assert "profile:" in workflow
    assert "- medium" in workflow
    assert "- aggressive" in workflow
    assert "strict_no_stub" in workflow
    assert "run_metadata_strict" in workflow
    assert "make run-demo-aggressive" in workflow
    assert "make run-demo" in workflow
    assert "make run-demo-check-strict" in workflow
    assert "manual-reports-${{ inputs.profile }}" in workflow
