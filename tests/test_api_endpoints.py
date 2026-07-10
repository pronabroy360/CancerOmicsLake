from fastapi.testclient import TestClient

from src.api.main import app


client = TestClient(app)


def test_health_endpoint() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_metadata_projects_endpoint() -> None:
    response = client.get("/metadata/projects")
    assert response.status_code == 200
    payload = response.json()
    assert "projects" in payload
    assert isinstance(payload["projects"], list)


def test_genes_search_endpoint() -> None:
    response = client.get("/genes/search", params={"query": "TP53"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["query"] == "TP53"
    assert "results" in payload


def test_expression_gene_endpoint() -> None:
    response = client.get("/expression/gene/TP53")
    assert response.status_code == 200
    payload = response.json()
    assert payload["gene_symbol"] == "TP53"
    assert "rows" in payload


def test_tumor_vs_normal_endpoint() -> None:
    response = client.get("/expression/tumor-vs-normal/TP53")
    assert response.status_code == 200
    payload = response.json()
    assert payload["gene_symbol"] == "TP53"
    assert "rows" in payload


def test_mutations_gene_endpoint() -> None:
    response = client.get("/mutations/gene/TP53")
    assert response.status_code == 200
    payload = response.json()
    assert payload["gene_symbol"] == "TP53"
    assert "rows" in payload


def test_research_candidate_genes_endpoint() -> None:
    response = client.get("/research/candidate-genes", params={"limit": 5})
    assert response.status_code == 200
    payload = response.json()
    assert "rows" in payload
    assert "filters" in payload
    assert payload["filters"]["limit"] == 5


def test_research_evidence_confidence_endpoint() -> None:
    response = client.get("/research/evidence-confidence", params={"limit": 5})
    assert response.status_code == 200
    payload = response.json()
    assert "rows" in payload
    assert payload["filters"]["limit"] == 5


def test_research_batch_effect_sensitivity_endpoint() -> None:
    response = client.get("/research/batch-effect-sensitivity", params={"limit": 5})
    assert response.status_code == 200
    payload = response.json()
    assert "rows" in payload
    assert payload["filters"]["limit"] == 5


def test_quality_latest_endpoint() -> None:
    response = client.get("/quality/latest")
    assert response.status_code == 200
    payload = response.json()
    assert "status" in payload
    assert "checks" in payload
    assert "summary" in payload
