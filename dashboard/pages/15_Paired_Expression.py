from __future__ import annotations

import streamlit as st

from src.analytics.dashboard_data import paired_expression_support_data


st.set_page_config(page_title="Paired Expression", page_icon="PE", layout="wide")
st.title("Matched TCGA Tumor-Normal Support")
st.caption("Tests within-case tumor versus adjacent-normal expression with Wilcoxon signed-rank statistics and FDR control.")
st.warning(
    "Pairing reduces dataset-source confounding, but adjacent tissue may contain field effects. Results are not causal or clinically validated."
)

controls = st.columns(5)
cancer = controls[0].selectbox("Cancer type", ["All", "TCGA-BRCA", "TCGA-LUAD", "TCGA-COAD"])
gene_query = controls[1].text_input("Gene search", "")
tier = controls[2].selectbox(
    "Support tier",
    ["All", "paired_replicated", "paired_internal_fdr", "limited", "paired_discordant"],
)
max_fdr = controls[3].selectbox("Maximum paired FDR", [1.0, 0.10, 0.05, 0.01, 0.001])
minimum = controls[4].slider("Minimum support", 0.0, 1.0, 0.0, 0.05)

data = paired_expression_support_data(
    cancer_type=None if cancer == "All" else cancer,
    gene_query=gene_query or None,
    support_tier=None if tier == "All" else tier,
    max_fdr=max_fdr,
    min_support_score=minimum,
    limit=500,
)

if data.is_empty():
    st.info("No paired output. Run metadata, paired acquisition, silver rebuild, then `make run-paired-expression`.")
else:
    metrics = st.columns(4)
    metrics[0].metric("Tested pairs", int(data.height))
    metrics[1].metric("Maximum matched cases", int(data["matched_case_count"].max()))
    metrics[2].metric("Paired replicated", int(data.filter(data["paired_support_tier"] == "paired_replicated").height))
    metrics[3].metric("Paired discordant", int(data.filter(data["paired_support_tier"] == "paired_discordant").height))
    st.bar_chart(data.select(["gene_symbol", "paired_support_score"]).head(30), x="gene_symbol", y="paired_support_score")
    st.dataframe(data.to_pandas(), use_container_width=True, hide_index=True)
    st.download_button(
        "Download paired support",
        data.write_csv().encode("utf-8"),
        file_name="paired_tcga_expression_support.csv",
        mime="text/csv",
    )
