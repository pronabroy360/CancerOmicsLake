from __future__ import annotations

import streamlit as st

from src.analytics.dashboard_data import overview_metrics


st.set_page_config(page_title="CancerOmicsLake Explorer", layout="wide")

metrics = overview_metrics()

st.title("CancerOmicsLake Explorer")
st.caption("Open-access TCGA + GTEx data engineering platform")

top = st.columns(6)
top[0].metric("TCGA Projects", int(metrics.get("tcga_projects", 0)))
top[1].metric("TCGA Samples", int(metrics.get("tcga_samples", 0)))
top[2].metric("GTEx Samples", int(metrics.get("gtex_samples", 0)))
top[3].metric("Genes", int(metrics.get("genes", 0)))
top[4].metric("Mutation Records", int(metrics.get("mutation_records", 0)))
top[5].metric("Expression Records", int(metrics.get("expression_records", 0)))

st.info("Tumor-vs-normal outputs are exploratory cross-dataset comparisons and may include batch effects.")
st.write(
    f"Latest quality status: `{metrics.get('quality_status', 'unknown')}` | "
    f"Run: `{metrics.get('quality_run_id', '')}` | "
    f"Generated: `{metrics.get('quality_generated_at', '')}`"
)
