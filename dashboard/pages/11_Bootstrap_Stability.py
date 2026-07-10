import streamlit as st

from src.analytics.dashboard_data import bootstrap_stability_data


st.set_page_config(page_title="Bootstrap Stability", page_icon="BS", layout="wide")
st.title("Candidate Bootstrap Stability")
st.caption(
    "Quantifies sampling stability of candidate directions and ranks under TCGA-adjacent and GTEx-normal references."
)
st.warning(
    "This candidate-restricted bootstrap measures resampling robustness, not external replication or clinical validity."
)

left, middle, right = st.columns(3)
with left:
    cancer = st.selectbox("Cancer type", ["All", "TCGA-BRCA", "TCGA-LUAD", "TCGA-COAD"])
with middle:
    tier = st.selectbox("Stability tier", ["All", "high", "moderate", "limited", "unstable"])
with right:
    gene = st.text_input("Gene contains", placeholder="TP53")

minimum = st.slider("Minimum bootstrap stability", 0.0, 1.0, 0.0, 0.05)
data = bootstrap_stability_data(
    cancer_type=None if cancer == "All" else cancer,
    gene_query=gene or None,
    stability_tier=None if tier == "All" else tier,
    min_stability=minimum,
    limit=250,
)

if data.is_empty():
    st.info("No bootstrap output. Run `make run-bootstrap-stability` after building silver and gold tables.")
else:
    metrics = st.columns(4)
    metrics[0].metric("Candidates", data.height)
    metrics[1].metric("Median stability", f"{data['bootstrap_stability_score'].median():.3f}")
    metrics[2].metric("High stability", int(data.filter(data["bootstrap_stability_tier"] == "high").height))
    metrics[3].metric("Median concordance", f"{data['reference_concordance_rate'].median():.3f}")

    chart = data.select(["gene_symbol", "bootstrap_stability_score"]).head(30)
    st.bar_chart(chart, x="gene_symbol", y="bootstrap_stability_score")
    st.dataframe(data, use_container_width=True, hide_index=True)
    st.download_button(
        "Download filtered bootstrap table",
        data.write_csv(),
        file_name="candidate_bootstrap_stability.csv",
        mime="text/csv",
    )
