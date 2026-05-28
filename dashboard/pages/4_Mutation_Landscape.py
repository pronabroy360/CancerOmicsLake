from __future__ import annotations

import polars as pl
import streamlit as st

from src.analytics.dashboard_data import mutation_landscape_data


st.title("Mutation Landscape")

base = mutation_landscape_data(limit=1000)
cancer_options = sorted(base.get_column("cancer_type").unique().to_list()) if not base.is_empty() else []
selected_cancer = st.selectbox("Cancer type", ["All"] + cancer_options, index=0)
gene_query = st.text_input("Gene contains", value="").strip()
limit = st.slider("Rows", min_value=10, max_value=200, value=50, step=10)

df = mutation_landscape_data(
    cancer_type=None if selected_cancer == "All" else selected_cancer,
    gene_query=gene_query or None,
    limit=limit,
)

if df.is_empty():
    st.info("No mutation rows found for selected filters.")
else:
    st.bar_chart(df.sort("mutation_frequency", descending=True).head(20), x="gene_symbol", y="mutation_frequency")
    st.dataframe(df, use_container_width=True, hide_index=True)
    st.download_button(
        "Download mutation landscape CSV",
        data=df.write_csv(),
        file_name="mutation_landscape.csv",
        mime="text/csv",
    )

variant_breakdown = (
    df.group_by("top_variant_classification").agg(pl.len().alias("count")).sort("count", descending=True)
    if not df.is_empty()
    else pl.DataFrame({"top_variant_classification": [], "count": []})
)
st.subheader("Variant Classification Breakdown")
st.dataframe(variant_breakdown, use_container_width=True, hide_index=True)
