import streamlit as st

from src.analytics.dashboard_data import evidence_confidence_data


st.set_page_config(page_title="Evidence Confidence", page_icon="EC", layout="wide")
st.title("Cancer-Gene Evidence Confidence")
st.caption(
    "Separates evidence strength from reliability using sample support, graph structure, "
    "row integrity, and source provenance."
)
st.warning(
    "TCGA-GTEx expression comparisons retain high batch-effect risk until harmonized, "
    "batch-aware expression data are available. Scores are exploratory, not clinical evidence."
)

left, middle, right = st.columns(3)
with left:
    cancer = st.selectbox("Cancer type", ["All", "TCGA-BRCA", "TCGA-LUAD", "TCGA-COAD"])
with middle:
    tier = st.selectbox("Confidence tier", ["All", "high", "moderate", "limited", "low"])
with right:
    gene = st.text_input("Gene contains", placeholder="TP53")

minimum = st.slider("Minimum confidence", 0.0, 1.0, 0.0, 0.05)
data = evidence_confidence_data(
    cancer_type=None if cancer == "All" else cancer,
    gene_query=gene or None,
    confidence_tier=None if tier == "All" else tier,
    min_confidence=minimum,
    limit=250,
)

if data.is_empty():
    st.info("No matching confidence rows. Run `make run-graph-export` after building gold tables.")
else:
    metrics = st.columns(4)
    metrics[0].metric("Cancer-gene pairs", data.height)
    metrics[1].metric("Median confidence", f"{data['overall_confidence'].median():.3f}")
    metrics[2].metric("Multi-modal pairs", int(data.filter(data["mutation_evidence"] & data["expression_evidence"]).height))
    metrics[3].metric("High batch-risk pairs", int(data.filter(data["batch_effect_risk"] == "high").height))

    chart = data.select(["gene_symbol", "overall_confidence"]).head(30)
    st.bar_chart(chart, x="gene_symbol", y="overall_confidence")
    st.dataframe(data, use_container_width=True, hide_index=True)
    st.download_button(
        "Download filtered confidence table",
        data.write_csv(),
        file_name="cancer_gene_evidence_confidence.csv",
        mime="text/csv",
    )
