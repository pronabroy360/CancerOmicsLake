import streamlit as st

st.set_page_config(page_title="CancerOmicsLake Explorer", layout="wide")

st.title("CancerOmicsLake Explorer")
st.caption("Open-access TCGA + GTEx data engineering platform")

metric_cols = st.columns(6)
metric_cols[0].metric("TCGA Projects", 3)
metric_cols[1].metric("TCGA Samples", 12)
metric_cols[2].metric("GTEx Samples", 4)
metric_cols[3].metric("Genes", 1)
metric_cols[4].metric("Mutation Records", 1)
metric_cols[5].metric("Expression Records", 4)

st.info("Tumor-vs-normal outputs are exploratory cross-dataset comparisons and may include batch effects.")
