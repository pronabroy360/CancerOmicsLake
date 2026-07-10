from __future__ import annotations

import streamlit as st

from src.analytics.dashboard_data import external_expression_validation_data


st.title("External Expression Validation")
st.caption("Compares native TCGA/GTEx effects with a uniformly processed recount3 expression extract.")
st.warning(
    "This is an external reproducibility check. Agreement strengthens candidate confidence, but it is not clinical validation."
)

controls = st.columns(5)
cancer = controls[0].selectbox("Cancer type", ["All", "TCGA-BRCA", "TCGA-LUAD", "TCGA-COAD"])
gene_query = controls[1].text_input("Gene search", "")
tier = controls[2].selectbox("Validation tier", ["All", "high", "moderate", "limited", "discordant"])
agreement = controls[3].selectbox("Direction agreement", ["All", "concordant", "inconclusive", "discordant"])
minimum = controls[4].slider("Minimum score", 0.0, 1.0, 0.0, 0.05)

data = external_expression_validation_data(
    cancer_type=None if cancer == "All" else cancer,
    gene_query=gene_query or None,
    validation_tier=None if tier == "All" else tier,
    direction_agreement=None if agreement == "All" else agreement,
    min_validation_score=minimum,
    limit=500,
)

if data.is_empty():
    st.info("No external validation output. Run `make run-external-validation` after adding a recount3 extract.")
else:
    metrics = st.columns(4)
    metrics[0].metric("Validated pairs", int(data.height))
    metrics[1].metric("Median score", f"{data['validation_score'].median():.3f}")
    metrics[2].metric("Concordant", int(data.filter(data["direction_agreement"] == "concordant").height))
    metrics[3].metric("Top-k overlap", int(data.filter(data["top_k_overlap"]).height))

    chart = data.select(["gene_symbol", "validation_score"]).head(30)
    st.bar_chart(chart, x="gene_symbol", y="validation_score")
    st.dataframe(data.to_pandas(), use_container_width=True, hide_index=True)
    st.download_button(
        "Download filtered validation table",
        data.write_csv().encode("utf-8"),
        file_name="external_expression_validation.csv",
        mime="text/csv",
    )
