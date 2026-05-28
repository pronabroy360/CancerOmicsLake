SELECT
    source_node_id,
    target_node_id,
    edge_type,
    weight,
    evidence_source
FROM read_parquet('data/gold/gold_graph_edges/*.parquet')
WHERE edge_type IN ('EXPRESSED_IN_TISSUE', 'MUTATED_IN_CANCER')
ORDER BY weight DESC
LIMIT 100;
