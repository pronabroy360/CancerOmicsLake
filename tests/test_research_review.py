import hashlib
import json

import pytest
import polars as pl

from src.operations.research_review import _load_processing, _load_study, build_research_review


def write_plan(root, plan, report):
    root.mkdir(exist_ok=True)
    (root / "study_plan.json").write_text(json.dumps(plan))
    report["plan_sha256"] = hashlib.sha256(json.dumps(plan, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    (root / "report.json").write_text(json.dumps(report))


def test_review_draft_uses_current_measurement_counts_and_preserves_limits(tmp_path):
    source = tmp_path / "silver_expression_tcga.parquet"
    pl.DataFrame({"value": [1, 2, 3]}).write_parquet(source)
    study, simulation = tmp_path / "native", tmp_path / "simulation"
    study.mkdir()
    table = pl.DataFrame({"cancer_type": ["TCGA-BRCA"], "method": ["reference_maximin"], "top_k": [50],
                          "proposed_minus_baseline_replication_fraction": [0.],
                          "proposed_minus_baseline_replication_fraction_ci_low": [0.],
                          "proposed_minus_baseline_replication_fraction_ci_high": [0.]})
    path = study / "heldout_evaluation.parquet"
    table.write_parquet(path)
    plan = {"config": {"paired_only": False}, "input_resources": [{"path": str(source),
            "sha256": hashlib.sha256(source.read_bytes()).hexdigest()}]}
    write_plan(study, plan, {"status": "completed", "study_id": "fixture", "pilot": True,
                            "cohort_audit": [], "outputs": [{"path": str(path),
                             "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}]})
    simulation.mkdir()
    truth = simulation / "truth_metrics.parquet"
    pl.DataFrame({"scenario": ["shared_normal_bias"], "method": ["reference_stability_lower_quantile"],
                  "top_k": [25], "precision_at_k": [.02], "heldout_reference_replication_fraction": [1.]}).write_parquet(truth)
    write_plan(simulation, {"seed": 1}, {"output_sha256": hashlib.sha256(truth.read_bytes()).hexdigest()})
    faults = tmp_path / "faults.json"
    faults.write_text(json.dumps({"status": "passed", "scenarios": [{"passed": True}],
                                 "independent_reproduction": "not performed"}))
    output = tmp_path / "review"
    report = build_research_review([study], simulation, faults, output)
    assert report["measurement_counts"] == {"tcga": 3}
    assert report["status"] == "research_incomplete" and not report["publication_enabled"]
    draft = (output / "manuscript_draft.md").read_text()
    assert "3 TCGA expression measurement rows" in draft
    assert "truth precision was 0.020" in draft
    assert "not biological-validation rates" in draft
    assert "10.1093/gigascience/giaf126" in draft
    assert "without a verified global donor/case partition" in draft
    report_path = study / "report.json"
    bad_report = json.loads(report_path.read_text())
    bad_report["global_group_leakage_count"] = 1
    report_path.write_text(json.dumps(bad_report))
    with pytest.raises(ValueError, match="Global donor/case leakage"):
        build_research_review([study], simulation, faults, output)
    bad_report["global_group_leakage_count"] = 0
    bad_report["partition_scope"] = "global_across_all_configured_projects"
    report_path.write_text(json.dumps(bad_report))
    build_research_review([study], simulation, faults, output)
    assert "All included studies report a globally consistent" in (output / "manuscript_draft.md").read_text()
    pl.DataFrame({"value": [4]}).write_parquet(source)
    with pytest.raises(ValueError, match="snapshot"):
        build_research_review([study], simulation, faults, output)


def test_review_verifies_frozen_plan_and_output_hashes(tmp_path):
    artifact = tmp_path / "result.parquet"
    artifact.write_bytes(b"synthetic artifact")
    plan = {"seed": 1}
    plan_hash = hashlib.sha256(json.dumps(plan, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    (tmp_path / "study_plan.json").write_text(json.dumps(plan))
    report = {"plan_sha256": plan_hash, "outputs": [{"path": str(artifact),
              "sha256": hashlib.sha256(artifact.read_bytes()).hexdigest()}]}
    (tmp_path / "report.json").write_text(json.dumps(report))
    result, loaded, resources = _load_study(tmp_path)
    assert result == report and loaded == plan
    assert len(resources) == 3
    artifact.write_bytes(b"changed")
    with pytest.raises(ValueError, match="artifact integrity"):
        _load_study(tmp_path)
    (tmp_path / "study_plan.json").write_text(json.dumps({"seed": 2}))
    with pytest.raises(ValueError, match="plan integrity"):
        _load_study(tmp_path)


def test_processing_review_verifies_private_and_public_resources(tmp_path):
    private = tmp_path / "private.parquet"
    public = tmp_path / "aggregate.csv"
    private.write_bytes(b"private fixture")
    public.write_text("metric,value\ncorrelation,0.9\n")

    def resource(path):
        return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "bytes": path.stat().st_size}

    plan = {"input_resources": [resource(private)], "implementation_resources": [],
            "selection_summary": [{"matched_samples": 2}]}
    report = {"status": "completed", "study_id": "fixture", "matched_specimens": 2,
              "individual_identifiers_exported": False, "outputs": [resource(public)],
              "private_manifest_resource": resource(private), "private_metrics_resource": resource(private)}
    write_plan(tmp_path, plan, report)
    loaded, resources = _load_processing(tmp_path)
    assert loaded["matched_specimens"] == 2 and len(resources) == 6
    public.write_text("metric,value\ncorrelation,0.1\n")
    with pytest.raises(ValueError, match="artifact integrity"):
        _load_processing(tmp_path)
