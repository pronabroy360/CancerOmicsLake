from __future__ import annotations

import polars as pl
import streamlit as st

from src.analytics.dashboard_data import tumor_vs_normal_data


st.title("Tumor vs Normal Explorer")

gene = st.text_input("Gene symbol", value="TP53").strip() or "TP53"
payload = tumor_vs_normal_data(gene_symbol=gene)
rows = payload["rows"]

if payload["warning"]:
    st.warning(payload["warning"])

if rows.is_empty():
    st.info("No tumor-vs-normal rows found for this gene.")
else:
    cancer_options = sorted(rows.get_column("cancer_type").unique().to_list())
    selected_cancer = st.selectbox("Cancer type", ["All"] + cancer_options, index=0)
    filtered = rows if selected_cancer == "All" else rows.filter(pl.col("cancer_type") == selected_cancer)

    st.bar_chart(filtered.sort("log2_fold_change", descending=True), x="cancer_type", y="log2_fold_change")
    st.dataframe(filtered, use_container_width=True, hide_index=True)
    st.download_button(
        "Download tumor-vs-normal CSV",
        data=filtered.write_csv(),
        file_name=f"tumor_vs_normal_{payload['gene_symbol']}.csv",
        mime="text/csv",
    )
