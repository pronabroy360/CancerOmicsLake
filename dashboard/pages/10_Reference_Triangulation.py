import streamlit as st

from src.analytics.dashboard_data import reference_triangulation_data


st.set_page_config(page_title="Reference Triangulation", page_icon="RT", layout="wide")
st.title("Reference Triangulation")
st.caption(
    "Tests whether tumor-expression direction is retained when the normal reference changes "
    "from TCGA adjacent tissue to GTEx healthy tissue."
)
st.warning(
    "TCGA adjacent normal can contain field effects and currently has limited sample support. "
    "This analysis measures reference sensitivity; it does not establish clinical validity."
)

left, middle, right = st.columns(3)
with left:
    cancer = st.selectbox("Cancer type", ["All", "TCGA-BRCA", "TCGA-LUAD", "TCGA-COAD"])
with middle:
    concordance = st.selectbox(
        "Reference concordance",
        ["All", "concordant_up", "concordant_down", "concordant_stable", "reference_sensitive", "discordant"],
    )
with right:
    support = st.selectbox("TCGA normal support", ["All", "high", "moderate", "limited"])

gene = st.text_input("Gene contains", placeholder="TP53")
minimum = st.slider("Minimum reference stability", 0.0, 1.0, 0.0, 0.05)
data = reference_triangulation_data(
    cancer_type=None if cancer == "All" else cancer,
    gene_query=gene or None,
    concordance=None if concordance == "All" else concordance,
    support_tier=None if support == "All" else support,
    min_stability=minimum,
    limit=250,
)

if data.is_empty():
    st.info("No triangulation rows. Expand TCGA adjacent-normal ingestion, then run `make run-silver run-gold`.")
else:
    metrics = st.columns(4)
    metrics[0].metric("Cancer-gene rows", data.height)
    metrics[1].metric("Median stability", f"{data['reference_stability_score'].median():.3f}")
    metrics[2].metric(
        "Reference-sensitive",
        int(data.filter(data["reference_concordance"] == "reference_sensitive").height),
    )
    metrics[3].metric("Discordant", int(data.filter(data["reference_concordance"] == "discordant").height))

    chart = data.select(["gene_symbol", "reference_stability_score"]).head(30)
    st.bar_chart(chart, x="gene_symbol", y="reference_stability_score")
    st.dataframe(data, use_container_width=True, hide_index=True)
    st.download_button(
        "Download filtered triangulation table",
        data.write_csv(),
        file_name="reference_triangulation.csv",
        mime="text/csv",
    )
