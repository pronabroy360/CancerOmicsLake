from __future__ import annotations

import streamlit as st

from src.analytics.dashboard_data import quality_report_data


st.title("Data Quality Report")

payload = quality_report_data()
checks = payload["checks"]
status_counts = payload["status_counts"]

col1, col2, col3 = st.columns(3)
col1.metric("Overall Status", str(payload["status"]))
col2.metric("Pipeline Run", str(payload["pipeline_run_id"]))
col3.metric("Generated At", str(payload["generated_at"]))

if checks.is_empty():
    st.info("No silver quality report found. Run `make run-quality`.")
else:
    st.subheader("Check Status Counts")
    st.dataframe(status_counts, use_container_width=True, hide_index=True)

    st.subheader("All Checks")
    st.dataframe(checks, use_container_width=True, hide_index=True, height=420)
    st.download_button(
        "Download quality checks CSV",
        data=checks.write_csv(),
        file_name="silver_quality_checks.csv",
        mime="text/csv",
    )
