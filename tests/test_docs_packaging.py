from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read_text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_readme_documents_reviewer_entrypoints() -> None:
    readme = read_text("README.md")

    assert "make run-flow-medium" in readme
    assert "make run-demo" in readme
    assert "make run-demo-check-strict" in readme
    assert "make run-dashboard" in readme
    assert "daily" in readme.lower()
    assert "Graphify and Neo4j" in readme
    assert "open-access-only" in readme
    assert "make run-demo-check" in readme


def test_reproducibility_documents_run_profiles_and_artifacts() -> None:
    reproducibility = read_text("docs/reproducibility.md")

    assert "make run-download-tcga-medium" in reproducibility
    assert "make run-demo-check" in reproducibility
    assert "Python `3.11`" in reproducibility
    assert "pipeline_run_history.json" in reproducibility
    assert "scheduled" in reproducibility
    assert "make run-graph-export" in reproducibility


def test_sample_queries_cover_core_marts() -> None:
    sample_queries = read_text("docs/sample_queries.md")

    assert "gold_tumor_vs_normal_expression" in sample_queries
    assert "gold_mutation_frequency_by_gene" in sample_queries
    assert "gold_graph_edges" in sample_queries


def test_publish_safe_sql_query_files_exist() -> None:
    query_dir = ROOT / "outputs" / "sample_queries"

    assert (query_dir / "01_cohort_summary.sql").exists()
    assert (query_dir / "02_top_overexpressed_brca.sql").exists()
    assert (query_dir / "03_top_mutated_luad.sql").exists()
    assert (query_dir / "04_graph_edges.sql").exists()
