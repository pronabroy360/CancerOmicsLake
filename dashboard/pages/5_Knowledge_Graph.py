from __future__ import annotations

from pathlib import Path

import polars as pl
import streamlit as st

from src.analytics.dashboard_data import graph_explorer_data, graph_node_metrics_data


st.title("Knowledge Graph Explorer")
st.caption("Graph tables loaded from `data/gold/gold_graph_nodes.parquet` and `data/gold/gold_graph_edges.parquet`.")

base = graph_explorer_data(max_rows=50000)
all_edge_types = sorted(base["edges"].get_column("edge_type").unique().to_list()) if not base["edges"].is_empty() else []

selected_edge_types = st.multiselect("Edge types", options=all_edge_types, default=all_edge_types)
node_query = st.text_input("Node search (id, label, or name)", value="").strip()
max_rows = st.slider("Max rows", min_value=50, max_value=2000, value=500, step=50)

view = graph_explorer_data(
    edge_types=selected_edge_types or None,
    node_query=node_query or None,
    max_rows=max_rows,
)

nodes = view["nodes"]
edges = view["edges"]
edge_counts = view["edge_type_counts"]
node_counts = view["node_label_counts"]

col1, col2 = st.columns(2)
col1.metric("Visible Nodes", nodes.height)
col2.metric("Visible Edges", edges.height)

left, right = st.columns(2)
left.subheader("Edge Type Counts")
left.dataframe(edge_counts, use_container_width=True, hide_index=True)
right.subheader("Node Label Counts")
right.dataframe(node_counts, use_container_width=True, hide_index=True)

metrics = graph_node_metrics_data(limit=25)
st.subheader("Top Graph Hub Nodes")
if metrics.is_empty():
    st.info("Run `make run-graph-export` or `make run-graph-metrics` to create graph node metrics.")
else:
    st.dataframe(metrics, use_container_width=True, hide_index=True, height=260)

st.subheader("Nodes")
st.dataframe(nodes, use_container_width=True, hide_index=True, height=280)
st.download_button("Download nodes CSV", data=nodes.write_csv(), file_name="graph_nodes_filtered.csv", mime="text/csv")

st.subheader("Edges")
st.dataframe(edges, use_container_width=True, hide_index=True, height=340)
st.download_button("Download edges CSV", data=edges.write_csv(), file_name="graph_edges_filtered.csv", mime="text/csv")

st.subheader("Exports on Disk")
neo4j_bulk = Path("outputs/graph_exports/neo4j/bulk")
if neo4j_bulk.exists():
    files = sorted(p.name for p in neo4j_bulk.glob("*.csv"))
    st.write("Neo4j bulk CSV files:")
    st.dataframe(pl.DataFrame({"file_name": files}), use_container_width=True, hide_index=True)
else:
    st.info("Run `make run-graph-export` to create Neo4j/Graphify export bundles.")
