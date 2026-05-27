import json
from pathlib import Path

import streamlit as st

st.title("Data Quality Report")
report_path = Path("outputs/reports/data_quality_report.json")
if report_path.exists():
    data = json.loads(report_path.read_text(encoding="utf-8"))
    st.json(data)
else:
    st.info("Run `make run-metadata` to generate the latest quality report.")
