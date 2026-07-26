from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read_text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_readme_documents_reviewer_entrypoints() -> None:
    readme = read_text("README.md")

    assert "make run-flow-medium" in readme
    assert "make run-flow-aggressive" in readme
    assert "make run-demo-aggressive" in readme
    assert "make run-demo" in readme
    assert "make run-demo-check-strict" in readme
    assert "make run-dashboard" in readme
    assert "make run-graph-metrics" in readme
    assert "/research/candidate-genes" in readme
    assert "/research/evidence-confidence" in readme
    assert "/research/batch-effect-sensitivity" in readme
    assert "/research/reference-triangulation" in readme
    assert "/research/bootstrap-stability" in readme
    assert "/research/external-expression-validation" in readme
    assert "make run-download-tcga-normals" in readme
    assert "Candidate Gene Priority" in readme
    assert "Batch-Effect Sensitivity" in readme
    assert "daily" in readme.lower()
    assert "Graphify and Neo4j" in readme
    assert "open-access-only" in readme
    assert "make run-demo-check" in readme
    assert "make run-ingestion-traceability" in readme
    assert "make run-gtex-live" in readme
    assert "make run-external-validation" in readme
    assert "Manual Ingestion" in readme


def test_reproducibility_documents_run_profiles_and_artifacts() -> None:
    reproducibility = read_text("docs/reproducibility.md")

    assert "make run-download-tcga-medium" in reproducibility
    assert "make run-download-tcga-aggressive" in reproducibility
    assert "make run-download-tcga-ci-smoke" in reproducibility
    assert "make run-demo-check" in reproducibility
    assert "Python `3.11`" in reproducibility
    assert "pipeline_run_history.json" in reproducibility
    assert "ingestion_traceability_report.json" in reproducibility
    assert "scheduled" in reproducibility
    assert "make run-graph-export" in reproducibility
    assert "make run-external-validation" in reproducibility
    assert "manual_ingestion.yml" in reproducibility


def test_sample_queries_cover_core_marts() -> None:
    sample_queries = read_text("docs/sample_queries.md")

    assert "gold_tumor_vs_normal_expression" in sample_queries
    assert "gold_mutation_frequency_by_gene" in sample_queries
    assert "gold_graph_edges" in sample_queries
    assert "gold_candidate_gene_priority" in sample_queries
    assert "gold_graph_node_metrics" in sample_queries
    assert "gold_cancer_gene_evidence_confidence" in sample_queries
    assert "gold_batch_effect_sensitivity" in sample_queries
    assert "gold_reference_triangulation" in sample_queries
    assert "gold_candidate_bootstrap_stability" in sample_queries
    assert "gold_external_expression_validation" in sample_queries
    assert "gold_reference_method_comparison" in sample_queries
    assert "gold_consensus_ablation_stability" in sample_queries


def test_publish_safe_sql_query_files_exist() -> None:
    query_dir = ROOT / "outputs" / "sample_queries"

    assert (query_dir / "01_cohort_summary.sql").exists()
    assert (query_dir / "02_top_overexpressed_brca.sql").exists()
    assert (query_dir / "03_top_mutated_luad.sql").exists()
    assert (query_dir / "04_graph_edges.sql").exists()
    assert (query_dir / "05_candidate_gene_priority.sql").exists()
    assert (query_dir / "06_graph_node_metrics.sql").exists()
    assert (query_dir / "07_evidence_confidence.sql").exists()
    assert (query_dir / "08_batch_effect_sensitivity.sql").exists()
    assert (query_dir / "09_reference_triangulation.sql").exists()
    assert (query_dir / "10_bootstrap_stability.sql").exists()
    assert (query_dir / "11_external_expression_validation.sql").exists()
    assert (query_dir / "13_reference_ablation.sql").exists()


def test_research_api_and_dashboard_docs_are_packaged() -> None:
    api_spec = read_text("docs/api_spec.md")

    assert "/research/candidate-genes" in api_spec
    assert "/research/evidence-confidence" in api_spec
    assert "/research/batch-effect-sensitivity" in api_spec
    assert "/research/reference-triangulation" in api_spec
    assert "/research/bootstrap-stability" in api_spec
    assert "/research/external-expression-validation" in api_spec
    assert (ROOT / "dashboard" / "pages" / "7_Candidate_Gene_Priority.py").exists()
    assert (ROOT / "dashboard" / "pages" / "8_Evidence_Confidence.py").exists()
    assert (ROOT / "dashboard" / "pages" / "9_Batch_Effect_Sensitivity.py").exists()
    assert (ROOT / "dashboard" / "pages" / "10_Reference_Triangulation.py").exists()
    assert (ROOT / "dashboard" / "pages" / "11_Bootstrap_Stability.py").exists()
    assert (ROOT / "dashboard" / "pages" / "12_External_Validation.py").exists()
    assert (ROOT / "docs" / "evidence_confidence_methodology.md").exists()
    assert (ROOT / "docs" / "batch_effect_sensitivity.md").exists()
    assert (ROOT / "docs" / "reference_triangulation.md").exists()
    assert (ROOT / "docs" / "bootstrap_stability.md").exists()
    assert (ROOT / "docs" / "external_validation.md").exists()
    assert (ROOT / "docs" / "reference_ablation.md").exists()
