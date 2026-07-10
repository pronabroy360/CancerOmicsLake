from __future__ import annotations

from fastapi import FastAPI

from src.analytics.candidate_priority import candidate_gene_priority
from src.analytics.evidence_confidence import evidence_confidence
from src.analytics.expression_summary import expression_by_gene
from src.analytics.gene_search import search_genes
from src.analytics.metadata import metadata_projects as metadata_projects_data
from src.analytics.metadata import metadata_samples as metadata_samples_data
from src.analytics.mutation_frequency import mutation_frequency_by_cancer, mutation_frequency_by_gene
from src.analytics.quality_latest import quality_latest as quality_latest_payload
from src.analytics.tumor_vs_normal import tumor_vs_normal_by_gene
from src.graph.build_edges import load_graph_edges
from src.graph.build_nodes import load_graph_nodes

app = FastAPI(title="CancerOmicsLake API", version="0.1.0")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/metadata/projects")
def metadata_projects() -> dict[str, list[str]]:
    return metadata_projects_data()


@app.get("/metadata/samples")
def metadata_samples(project_id: str) -> dict[str, object]:
    return metadata_samples_data(project_id)


@app.get("/genes/search")
def genes_search(query: str) -> dict[str, object]:
    return search_genes(query)


@app.get("/expression/gene/{gene_symbol}")
def expression_gene(gene_symbol: str) -> dict[str, object]:
    return expression_by_gene(gene_symbol)


@app.get("/expression/tumor-vs-normal/{gene_symbol}")
def expression_tumor_vs_normal(gene_symbol: str) -> dict[str, object]:
    return tumor_vs_normal_by_gene(gene_symbol)


@app.get("/mutations/gene/{gene_symbol}")
def mutations_gene(gene_symbol: str) -> dict[str, object]:
    return mutation_frequency_by_gene(gene_symbol)


@app.get("/mutations/cancer/{project_id}")
def mutations_cancer(project_id: str) -> dict[str, object]:
    return mutation_frequency_by_cancer(project_id)


@app.get("/research/candidate-genes")
def research_candidate_genes(
    cancer_type: str | None = None,
    gene_query: str | None = None,
    tier: str | None = None,
    min_priority_score: float | None = None,
    limit: int = 50,
) -> dict[str, object]:
    return candidate_gene_priority(
        cancer_type=cancer_type,
        gene_query=gene_query,
        tier=tier,
        min_priority_score=min_priority_score,
        limit=limit,
    )


@app.get("/research/evidence-confidence")
def research_evidence_confidence(
    cancer_type: str | None = None,
    gene_query: str | None = None,
    confidence_tier: str | None = None,
    min_confidence: float | None = None,
    limit: int = 50,
) -> dict[str, object]:
    return evidence_confidence(
        cancer_type=cancer_type,
        gene_query=gene_query,
        confidence_tier=confidence_tier,
        min_confidence=min_confidence,
        limit=limit,
    )


@app.get("/graph/nodes")
def graph_nodes() -> dict[str, object]:
    return {"nodes": load_graph_nodes()}


@app.get("/graph/edges")
def graph_edges() -> dict[str, object]:
    return {"edges": load_graph_edges()}


@app.get("/quality/latest")
def quality_latest() -> dict[str, object]:
    return quality_latest_payload()
