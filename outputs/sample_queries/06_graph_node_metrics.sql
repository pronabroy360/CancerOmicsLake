SELECT
    node_id,
    node_label,
    name,
    total_degree,
    in_degree,
    out_degree,
    weighted_degree,
    edge_type_count,
    degree_rank
FROM read_parquet('data/gold/gold_graph_node_metrics/*.parquet')
ORDER BY total_degree DESC, weighted_degree DESC
LIMIT 25;
