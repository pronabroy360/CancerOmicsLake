from pathlib import Path

import polars as pl

from src.analytics.pathway_enrichment import PATHWAY_ENRICHMENT_SCHEMA
from src.graph.pathway_projection import select_enriched_pathways, selected_pathway_memberships


def _row(
    cancer_type: str,
    pathway_id: str,
    *,
    candidate_set: str = "prioritized",
    fdr: float = 0.01,
    score: float = 0.8,
    tier: str = "fdr_enriched",
) -> dict[str, object]:
    return {
        "cancer_type": cancer_type,
        "candidate_set": candidate_set,
        "pathway_id": pathway_id,
        "pathway_name": f"Pathway {pathway_id}",
        "pathway_source": "Reactome",
        "background_gene_count": 100,
        "candidate_gene_count": 10,
        "pathway_gene_count": 5,
        "overlap_gene_count": 3,
        "overlap_genes": "G1,G2,G3",
        "enrichment_ratio": 3.0,
        "odds_ratio": 4.0,
        "p_value": fdr / 2,
        "fdr_q_value": fdr,
        "enrichment_score": score,
        "enrichment_tier": tier,
        "pathway_caveat": "Hypothesis generation only.",
    }


def test_select_enriched_pathways_deduplicates_and_caps_per_cancer(tmp_path: Path) -> None:
    path = tmp_path / "pathways.parquet"
    rows = [
        _row("TCGA-BRCA", "R-HSA-1", candidate_set="watchlist_plus_prioritized", fdr=0.02),
        _row("TCGA-BRCA", "R-HSA-1", candidate_set="prioritized", fdr=0.005, score=0.9),
        _row("TCGA-BRCA", "R-HSA-2", fdr=0.01),
        _row("TCGA-BRCA", "R-HSA-3", fdr=0.03),
        _row("TCGA-BRCA", "R-HSA-4", fdr=0.001, tier="nominal"),
        _row("TCGA-LUAD", "R-HSA-5", fdr=0.04),
    ]
    pl.DataFrame(rows, schema=PATHWAY_ENRICHMENT_SCHEMA).write_parquet(path)

    selected = select_enriched_pathways(path, max_pathways_per_cancer=2)

    brca = selected.filter(pl.col("cancer_type") == "TCGA-BRCA")
    assert brca.height == 2
    assert set(brca.get_column("pathway_id")) == {"R-HSA-1", "R-HSA-2"}
    strongest = brca.filter(pl.col("pathway_id") == "R-HSA-1").to_dicts()[0]
    assert strongest["candidate_set"] == "prioritized"
    assert selected.filter(pl.col("cancer_type") == "TCGA-LUAD").height == 1
    assert "R-HSA-4" not in selected.get_column("pathway_id").to_list()


def test_selected_pathway_memberships_uses_only_projected_pathways(tmp_path: Path) -> None:
    enrichment_path = tmp_path / "pathways.parquet"
    pl.DataFrame(
        [_row("TCGA-BRCA", "R-HSA-1"), _row("TCGA-BRCA", "R-HSA-2", tier="nominal")],
        schema=PATHWAY_ENRICHMENT_SCHEMA,
    ).write_parquet(enrichment_path)
    gmt_path = tmp_path / "reactome.gmt"
    gmt_path.write_text(
        "Selected\tR-HSA-1\tTP53\tCDK1\tCCNB1\tMDM2\tCDKN1A\n"
        "Excluded\tR-HSA-2\tEGFR\tKRAS\tALK\tMET\tROS1\n",
        encoding="utf-8",
    )

    selected = select_enriched_pathways(enrichment_path)
    memberships = selected_pathway_memberships(selected, gmt_path)

    assert memberships.height == 5
    assert set(memberships.get_column("pathway_id")) == {"R-HSA-1"}
    assert set(memberships.get_column("gene_symbol")) == {"TP53", "CDK1", "CCNB1", "MDM2", "CDKN1A"}
