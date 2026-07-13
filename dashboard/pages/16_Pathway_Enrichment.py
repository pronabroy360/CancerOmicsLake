from __future__ import annotations

import streamlit as st

from src.analytics.dashboard_data import pathway_enrichment_data


st.set_page_config(page_title="Pathway Enrichment", page_icon="PW", layout="wide")
st.title("Candidate Pathway Enrichment")
st.caption("Runs over-representation analysis on consensus candidate gene sets against the tested cancer-specific background.")
st.warning(
    "Pathway enrichment is hypothesis generation. It does not establish mechanism, causality, or clinical actionability."
)

controls = st.columns(6)
cancer = controls[0].selectbox("Cancer type", ["All", "TCGA-BRCA", "TCGA-LUAD", "TCGA-COAD"])
candidate_set = controls[1].selectbox(
    "Candidate set",
    ["All", "prioritized", "watchlist_plus_prioritized", "research_candidate_plus"],
)
tier = controls[2].selectbox("Enrichment tier", ["All", "fdr_enriched", "nominal", "limited"])
pathway_query = controls[3].text_input("Pathway search", "")
max_fdr = controls[4].selectbox("Maximum FDR", [1.0, 0.25, 0.10, 0.05, 0.01])
min_overlap = controls[5].number_input("Minimum overlap", min_value=1, max_value=100, value=2, step=1)

data = pathway_enrichment_data(
    cancer_type=None if cancer == "All" else cancer,
    candidate_set=None if candidate_set == "All" else candidate_set,
    pathway_query=pathway_query or None,
    enrichment_tier=None if tier == "All" else tier,
    max_fdr=max_fdr,
    min_overlap=int(min_overlap),
    limit=500,
)

if data.is_empty():
    st.info("No pathway enrichment output. Add a GMT file and run `make run-pathway-enrichment`.")
else:
    metrics = st.columns(4)
    metrics[0].metric("Enriched rows", int(data.height))
    metrics[1].metric("Cancer types", int(data["cancer_type"].n_unique()))
    metrics[2].metric("Pathways", int(data["pathway_id"].n_unique()))
    metrics[3].metric("Max overlap", int(data["overlap_gene_count"].max()))
    st.bar_chart(data.select(["pathway_name", "enrichment_score"]).head(30), x="pathway_name", y="enrichment_score")
    st.dataframe(data.to_pandas(), use_container_width=True, hide_index=True)
    st.download_button(
        "Download pathway enrichment",
        data.write_csv().encode("utf-8"),
        file_name="pathway_enrichment.csv",
        mime="text/csv",
    )
