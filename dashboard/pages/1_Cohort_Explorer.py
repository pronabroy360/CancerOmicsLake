from __future__ import annotations

import polars as pl
import streamlit as st

from src.analytics.dashboard_data import cohort_distribution_data, overview_metrics


st.title("Cohort Explorer")

cohort = cohort_distribution_data()
metrics = overview_metrics()
samples = cohort["samples"]

project_options = list(cohort["project_options"])
sample_type_options = list(cohort["sample_type_options"])

selected_projects = st.multiselect("Cancer types", options=project_options, default=project_options)
selected_sample_types = st.multiselect("Sample types", options=sample_type_options, default=sample_type_options)

filtered = samples
if selected_projects:
    filtered = filtered.filter(pl.col("project_id").is_in(selected_projects))
if selected_sample_types:
    filtered = filtered.filter(pl.col("sample_type").is_in(selected_sample_types))

col1, col2, col3, col4 = st.columns(4)
col1.metric("Filtered Samples", int(filtered.get_column("sample_id").n_unique()) if not filtered.is_empty() else 0)
col2.metric("Filtered Cases", int(filtered.get_column("case_id").n_unique()) if not filtered.is_empty() else 0)
col3.metric("GTEx Samples", int(metrics.get("gtex_samples", 0)))
col4.metric("TCGA Projects", int(metrics.get("tcga_projects", 0)))

by_cancer = (
    filtered.group_by("project_id").agg(pl.col("sample_id").n_unique().alias("count")).sort("count", descending=True)
    if not filtered.is_empty()
    else pl.DataFrame({"project_id": [], "count": []})
)
by_type = (
    filtered.group_by("sample_type").agg(pl.col("sample_id").n_unique().alias("count")).sort("count", descending=True)
    if not filtered.is_empty()
    else pl.DataFrame({"sample_type": [], "count": []})
)

left, right = st.columns(2)
left.subheader("Sample Count by Cancer")
left.bar_chart(by_cancer, x="project_id", y="count")
left.dataframe(by_cancer, use_container_width=True, hide_index=True)

right.subheader("Sample Type Distribution")
right.bar_chart(by_type, x="sample_type", y="count")
right.dataframe(by_type, use_container_width=True, hide_index=True)

st.subheader("Filtered Sample Table")
st.dataframe(filtered.sort(["project_id", "case_id"]), use_container_width=True, hide_index=True)
st.download_button(
    "Download filtered cohort CSV",
    data=filtered.write_csv(),
    file_name="cohort_filtered_samples.csv",
    mime="text/csv",
)
