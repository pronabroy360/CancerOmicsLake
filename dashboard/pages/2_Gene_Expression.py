from __future__ import annotations

import streamlit as st

from src.analytics.dashboard_data import gene_expression_data


st.title("Gene Expression Explorer")

gene = st.text_input("Gene symbol", value="TP53").strip() or "TP53"
payload = gene_expression_data(gene)

st.caption(f"Results for `{payload['gene_symbol']}`")

tcga = payload["tcga"]
gtex = payload["gtex"]
combined = payload["combined"]

col1, col2 = st.columns(2)
col1.subheader("TCGA Expression by Cancer")
if not tcga.is_empty():
    col1.bar_chart(tcga.sort("median_expression", descending=True), x="project_id", y="median_expression")
    col1.dataframe(tcga.sort("median_expression", descending=True), use_container_width=True, hide_index=True)
else:
    col1.info("No TCGA rows found for this gene.")

col2.subheader("GTEx Expression by Tissue")
if not gtex.is_empty():
    col2.bar_chart(gtex.sort("median_expression", descending=True), x="tissue_site", y="median_expression")
    col2.dataframe(gtex.sort("median_expression", descending=True), use_container_width=True, hide_index=True)
else:
    col2.info("No GTEx rows found for this gene.")

st.subheader("Combined Expression Table")
st.dataframe(combined, use_container_width=True, hide_index=True)
st.download_button(
    "Download expression CSV",
    data=combined.write_csv(),
    file_name=f"expression_{payload['gene_symbol']}.csv",
    mime="text/csv",
)
