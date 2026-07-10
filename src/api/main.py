from __future__ import annotations

from fastapi import FastAPI

from src.analytics.batch_effect_sensitivity import batch_effect_sensitivity
from src.analytics.bootstrap_stability import bootstrap_stability
from src.analytics.candidate_priority import candidate_gene_priority
from src.analytics.consensus_candidates import consensus_candidates
from src.analytics.evidence_confidence import evidence_confidence
from src.analytics.external_validation import external_expression_validation
from src.analytics.expression_summary import expression_by_gene
from src.analytics.gene_search import search_genes
from src.analytics.metadata import metadata_projects as metadata_projects_data
from src.analytics.metadata import metadata_samples as metadata_samples_data
from src.analytics.mutation_frequency import mutation_frequency_by_cancer, mutation_frequency_by_gene
from src.analytics.reference_triangulation import reference_triangulation
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
    batch_concordance: str | None = None,
    min_confidence: float | None = None,
    limit: int = 50,
) -> dict[str, object]:
    return evidence_confidence(
        cancer_type=cancer_type,
        gene_query=gene_query,
        confidence_tier=confidence_tier,
        batch_concordance=batch_concordance,
        min_confidence=min_confidence,
        limit=limit,
    )


@app.get("/research/batch-effect-sensitivity")
def research_batch_effect_sensitivity(
    cancer_type: str | None = None,
    gene_query: str | None = None,
    support_tier: str | None = None,
    direction: str | None = None,
    min_abs_percentile_delta: float | None = None,
    limit: int = 50,
) -> dict[str, object]:
    return batch_effect_sensitivity(
        cancer_type=cancer_type,
        gene_query=gene_query,
        support_tier=support_tier,
        direction=direction,
        min_abs_percentile_delta=min_abs_percentile_delta,
        limit=limit,
    )


@app.get("/research/reference-triangulation")
def research_reference_triangulation(
    cancer_type: str | None = None,
    gene_query: str | None = None,
    concordance: str | None = None,
    support_tier: str | None = None,
    min_stability: float | None = None,
    limit: int = 50,
) -> dict[str, object]:
    return reference_triangulation(
        cancer_type=cancer_type,
        gene_query=gene_query,
        concordance=concordance,
        support_tier=support_tier,
        min_stability=min_stability,
        limit=limit,
    )


@app.get("/research/bootstrap-stability")
def research_bootstrap_stability(
    cancer_type: str | None = None,
    gene_query: str | None = None,
    stability_tier: str | None = None,
    min_stability: float | None = None,
    limit: int = 50,
) -> dict[str, object]:
    return bootstrap_stability(
        cancer_type=cancer_type,
        gene_query=gene_query,
        stability_tier=stability_tier,
        min_stability=min_stability,
        limit=limit,
    )


@app.get("/research/external-expression-validation")
def research_external_expression_validation(
    cancer_type: str | None = None,
    gene_query: str | None = None,
    validation_tier: str | None = None,
    direction_agreement: str | None = None,
    min_validation_score: float | None = None,
    limit: int = 50,
) -> dict[str, object]:
    return external_expression_validation(
        cancer_type=cancer_type,
        gene_query=gene_query,
        validation_tier=validation_tier,
        direction_agreement=direction_agreement,
        min_validation_score=min_validation_score,
        limit=limit,
    )


@app.get("/research/consensus-candidates")
def research_consensus_candidates(
    cancer_type: str | None = None,
    gene_query: str | None = None,
    decision: str | None = None,
    publication_tier: str | None = None,
    min_consensus_score: float | None = None,
    limit: int = 50,
) -> dict[str, object]:
    return consensus_candidates(
        cancer_type=cancer_type,
        gene_query=gene_query,
        decision=decision,
        publication_tier=publication_tier,
        min_consensus_score=min_consensus_score,
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
