from __future__ import annotations

import streamlit as st

from src.analytics.dashboard_data import consensus_candidates_data


st.set_page_config(page_title="Consensus Candidates", page_icon="CC", layout="wide")
st.title("Consensus Candidate Genes")
st.caption("Ranks cancer-gene candidates after external validation, reference triangulation, bootstrap stability, and evidence confidence.")
st.warning(
    "This is a publication-triage view. It is not batch-corrected differential expression, clinical validation, or causal evidence."
)

controls = st.columns(5)
cancer = controls[0].selectbox("Cancer type", ["All", "TCGA-BRCA", "TCGA-LUAD", "TCGA-COAD"])
gene_query = controls[1].text_input("Gene search", "")
decision = controls[2].selectbox("Decision", ["All", "prioritized", "watchlist", "deprioritized"])
tier = controls[3].selectbox(
    "Publication tier",
    ["All", "strong_candidate", "research_candidate", "exploratory", "deprioritized"],
)
minimum = controls[4].slider("Minimum score", 0.0, 1.0, 0.0, 0.05)

data = consensus_candidates_data(
    cancer_type=None if cancer == "All" else cancer,
    gene_query=gene_query or None,
    decision=None if decision == "All" else decision,
    publication_tier=None if tier == "All" else tier,
    min_consensus_score=minimum,
    limit=500,
)

if data.is_empty():
    st.info("No consensus candidate output. Run `make run-consensus-candidates` after the research validation layers.")
else:
    metrics = st.columns(4)
    metrics[0].metric("Candidate pairs", int(data.height))
    metrics[1].metric("Median consensus", f"{data['consensus_score'].median():.3f}")
    metrics[2].metric("Prioritized", int(data.filter(data["consensus_decision"] == "prioritized").height))
    metrics[3].metric("No rejection reason", int(data.filter(data["rejection_reasons"] == "none").height))

    chart = data.select(["gene_symbol", "consensus_score"]).head(30)
    st.bar_chart(chart, x="gene_symbol", y="consensus_score")
    st.dataframe(data.to_pandas(), use_container_width=True, hide_index=True)
    st.download_button(
        "Download filtered consensus candidates",
        data.write_csv().encode("utf-8"),
        file_name="consensus_candidate_genes.csv",
        mime="text/csv",
    )
