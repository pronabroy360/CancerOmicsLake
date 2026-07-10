import streamlit as st

from src.analytics.dashboard_data import batch_effect_sensitivity_data


st.set_page_config(page_title="Batch Sensitivity", page_icon="BS", layout="wide")
st.title("Batch-Effect Sensitivity")
st.caption(
    "Compares TCGA tumor and GTEx normal expression using within-cohort percentile ranks "
    "and robust z-score deltas."
)
st.warning(
    "This is a sensitivity analysis, not full batch correction. Results remain exploratory "
    "until validated with harmonized or explicitly batch-corrected expression data."
)

left, middle, right = st.columns(3)
with left:
    cancer = st.selectbox("Cancer type", ["All", "TCGA-BRCA", "TCGA-LUAD", "TCGA-COAD"])
with middle:
    support = st.selectbox("Support tier", ["All", "high", "moderate", "limited"])
with right:
    direction = st.selectbox("Direction", ["All", "rank_up", "rank_down", "stable"])

gene = st.text_input("Gene contains", placeholder="TP53")
minimum = st.slider("Minimum absolute percentile delta", 0.0, 1.0, 0.2, 0.05)

data = batch_effect_sensitivity_data(
    cancer_type=None if cancer == "All" else cancer,
    gene_query=gene or None,
    support_tier=None if support == "All" else support,
    direction=None if direction == "All" else direction,
    min_abs_percentile_delta=minimum,
    limit=250,
)

if data.is_empty():
    st.info("No matching sensitivity rows. Run `make run-gold` after building silver tables.")
else:
    metrics = st.columns(4)
    metrics[0].metric("Cancer-gene rows", data.height)
    metrics[1].metric("Median |percentile delta|", f"{data['percentile_delta'].abs().median():.3f}")
    metrics[2].metric("Rank-up rows", int(data.filter(data["sensitivity_direction"] == "rank_up").height))
    metrics[3].metric("High-support rows", int(data.filter(data["support_tier"] == "high").height))

    chart = data.select(["gene_symbol", "percentile_delta"]).head(30)
    st.bar_chart(chart, x="gene_symbol", y="percentile_delta")
    st.dataframe(data, use_container_width=True, hide_index=True)
    st.download_button(
        "Download filtered sensitivity table",
        data.write_csv(),
        file_name="batch_effect_sensitivity.csv",
        mime="text/csv",
    )
