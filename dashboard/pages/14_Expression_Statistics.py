from __future__ import annotations

import streamlit as st

from src.analytics.dashboard_data import expression_statistical_support_data


st.set_page_config(page_title="Expression Statistics", page_icon="ES", layout="wide")
st.title("Expression Statistical Support")
st.caption("Tests sample-level tumor-normal expression associations in native and recount3 data with FDR control.")
st.warning(
    "Source and disease status remain confounded. These results are not causal, clinical, or batch-corrected differential-expression claims."
)

controls = st.columns(5)
cancer = controls[0].selectbox("Cancer type", ["All", "TCGA-BRCA", "TCGA-LUAD", "TCGA-COAD"])
gene_query = controls[1].text_input("Gene search", "")
tier = controls[2].selectbox(
    "Support tier",
    ["All", "replicated_fdr", "recount3_fdr_supported", "native_only_fdr", "limited", "discordant"],
)
max_fdr = controls[3].selectbox("Maximum recount3 FDR", [1.0, 0.10, 0.05, 0.01, 0.001])
minimum = controls[4].slider("Minimum support", 0.0, 1.0, 0.0, 0.05)

data = expression_statistical_support_data(
    cancer_type=None if cancer == "All" else cancer,
    gene_query=gene_query or None,
    support_tier=None if tier == "All" else tier,
    max_fdr=max_fdr,
    min_support_score=minimum,
    limit=500,
)

if data.is_empty():
    st.info("No statistical support output. Run `make run-expression-statistics` after native and recount3 expression are available.")
else:
    metrics = st.columns(4)
    metrics[0].metric("Tested pairs", int(data.height))
    metrics[1].metric("Median support", f"{data['statistical_support_score'].median():.3f}")
    metrics[2].metric("Replicated FDR", int(data.filter(data["statistical_support_tier"] == "replicated_fdr").height))
    metrics[3].metric("Discordant", int(data.filter(data["statistical_support_tier"] == "discordant").height))
    st.bar_chart(data.select(["gene_symbol", "statistical_support_score"]).head(30), x="gene_symbol", y="statistical_support_score")
    st.dataframe(data.to_pandas(), use_container_width=True, hide_index=True)
    st.download_button(
        "Download filtered statistics",
        data.write_csv().encode("utf-8"),
        file_name="expression_statistical_support.csv",
        mime="text/csv",
    )
