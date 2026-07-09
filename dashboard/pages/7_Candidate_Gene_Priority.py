from __future__ import annotations

import streamlit as st

from src.analytics.dashboard_data import candidate_priority_data


st.title("Candidate Gene Priority")
st.caption("Exploratory cancer-gene prioritization from mutation frequency, expression shift, and evidence coverage.")
st.warning("Priority scores are research triage signals only; they are not clinically validated biomarkers.")

base = candidate_priority_data(limit=50000)
cancer_options = sorted(base.get_column("cancer_type").unique().to_list()) if not base.is_empty() else []
tier_options = sorted(base.get_column("priority_tier").unique().to_list()) if not base.is_empty() else []

col1, col2, col3, col4 = st.columns(4)
selected_cancer = col1.selectbox("Cancer type", ["All"] + cancer_options, index=0)
selected_tier = col2.selectbox("Priority tier", ["All"] + tier_options, index=0)
gene_query = col3.text_input("Gene contains", value="").strip()
min_score = col4.slider("Minimum score", min_value=0.0, max_value=1.0, value=0.0, step=0.05)
limit = st.slider("Rows", min_value=10, max_value=500, value=100, step=10)

df = candidate_priority_data(
    cancer_type=None if selected_cancer == "All" else selected_cancer,
    gene_query=gene_query or None,
    tier=None if selected_tier == "All" else selected_tier,
    min_priority_score=min_score,
    limit=limit,
)

if df.is_empty():
    st.info("No candidate priority rows found for selected filters. Run `make run-gold` if the mart is missing.")
else:
    top = df.sort("priority_score", descending=True).head(20)
    st.bar_chart(top, x="gene_symbol", y="priority_score")
    st.dataframe(df, use_container_width=True, hide_index=True, height=460)
    st.download_button(
        "Download candidate priority CSV",
        data=df.write_csv(),
        file_name="candidate_gene_priority.csv",
        mime="text/csv",
    )
