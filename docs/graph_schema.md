# Graph Schema

## Overview

CancerOmicsLake builds graph tables from silver and gold marts, then exports:

- `data/gold/gold_graph_nodes.parquet`
- `data/gold/gold_graph_edges.parquet`
- `outputs/graph_exports/neo4j/nodes.csv`
- `outputs/graph_exports/neo4j/edges.csv`
- `outputs/graph_exports/neo4j/bulk/*.csv`
- `outputs/graph_exports/neo4j/import_bulk.cypher`
- `outputs/graph_exports/graphify/nodes.csv`
- `outputs/graph_exports/graphify/edges.csv`
- `data/gold/gold_graph_node_metrics.parquet`
- `outputs/reports/graph_metrics_report.json`

## Node Types

Node rows are stored in `gold_graph_nodes` with core columns:

- `node_id`
- `node_label`
- `name`
- `primary_site`
- `source`

Current labels:

- `CancerType`
- `Gene`
- `Sample`
- `Patient`
- `Tissue`
- `Dataset`
- `Pathway`

## Edge Types

Edge rows are stored in `gold_graph_edges` with core columns:

- `edge_id`
- `source_node_id`
- `target_node_id`
- `edge_type`
- `weight`
- `evidence_source`

Current edge types:

- `HAS_SAMPLE`
- `BELONGS_TO_CANCER`
- `EXPRESSED_IN_TISSUE`
- `MUTATED_IN_CANCER`
- `MEMBER_OF_PATHWAY`
- `ENRICHED_IN_CANCER`

## Pathway Projection Guardrails

- `Pathway` nodes come from Reactome pathways retained by the enrichment projection.
- `MEMBER_OF_PATHWAY` links Reactome member genes to projected pathways and has weight `1.0`.
- `ENRICHED_IN_CANCER` links a pathway to a TCGA cancer and uses the bounded enrichment score as weight.
- Only `fdr_enriched` rows with `fdr_q_value <= 0.05` are eligible.
- Duplicate candidate-set hits are reduced deterministically to the lowest-FDR row per cancer and pathway.
- At most 50 pathways per cancer are projected, limiting graph density and reviewer selection bias.
- These relationships encode pathway membership and statistical over-representation, not mechanism, causality,
  clinical utility, or pathway activation.

## Neo4j Import (No APOC Required)

1. Build graph data and exports:

```bash
make run-gold
make run-graph-export
```

2. Copy files from `outputs/graph_exports/neo4j/bulk/` and `outputs/graph_exports/neo4j/import_bulk.cypher`
   into your Neo4j `import/` directory.

3. Open `cypher-shell` and run:

```cypher
:source import_bulk.cypher
```

The generated script imports label-specific node CSV files and edge-type-specific CSV files.

## Graphify Import

Use:

- `outputs/graph_exports/graphify/nodes.csv`
- `outputs/graph_exports/graphify/edges.csv`

These files follow the same node/edge IDs and relationship semantics as Neo4j exports.

## Graph Metrics

`make run-graph-export` also writes graph analytics outputs:

- `data/gold/gold_graph_node_metrics.parquet`
- `outputs/reports/graph_metrics_report.json`

The node metrics table includes total degree, in-degree, out-degree, weighted degree, connected edge-type count, and degree rank. Use it to identify graph hub genes, cancer types, samples, and tissue references for exploratory review.

## Example Neo4j Queries

```cypher
MATCH (g:Gene)-[r:MUTATED_IN_CANCER]->(c:CancerType)
RETURN c.node_id AS cancer, g.name AS gene, r.weight AS mutation_frequency
ORDER BY mutation_frequency DESC
LIMIT 20;
```

```cypher
MATCH (p:Patient)-[:HAS_SAMPLE]->(s:Sample)-[:BELONGS_TO_CANCER]->(c:CancerType)
RETURN c.node_id AS cancer, count(DISTINCT s.node_id) AS sample_count
ORDER BY sample_count DESC;
```

```cypher
MATCH (g:Gene)-[r:EXPRESSED_IN_TISSUE]->(t:Tissue)
RETURN t.name AS tissue, g.name AS gene, r.weight AS mean_log2_expression
ORDER BY mean_log2_expression DESC
LIMIT 20;
```

```cypher
MATCH (g:Gene)-[:MEMBER_OF_PATHWAY]->(p:Pathway)-[r:ENRICHED_IN_CANCER]->(c:CancerType)
RETURN c.node_id AS cancer, p.name AS pathway, count(DISTINCT g) AS member_genes,
       r.weight AS enrichment_score, r.evidence_source AS evidence
ORDER BY enrichment_score DESC
LIMIT 25;
```
