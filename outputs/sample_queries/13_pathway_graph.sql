-- Explore pathway-cancer relationships retained by the graph projection.
-- Interpretation: hypothesis navigation only, not pathway activation or causality.

SELECT
    e.target_node_id AS cancer_type,
    n.name AS pathway_name,
    e.weight AS enrichment_score,
    e.evidence_source
FROM read_parquet('data/gold/gold_graph_edges.parquet') AS e
JOIN read_parquet('data/gold/gold_graph_nodes.parquet') AS n
  ON e.source_node_id = n.node_id
WHERE e.edge_type = 'ENRICHED_IN_CANCER'
ORDER BY cancer_type, enrichment_score DESC
LIMIT 50;
