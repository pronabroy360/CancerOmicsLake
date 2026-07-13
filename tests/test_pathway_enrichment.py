from pathlib import Path

import polars as pl

from src.analytics.pathway_enrichment import (
    PATHWAY_ENRICHMENT_SCHEMA,
    build_pathway_enrichment,
    load_gmt_pathways,
    pathway_enrichment,
)


def _write_consensus(path: Path) -> None:
    genes = [f"GENE{i}" for i in range(1, 11)]
    rows = []
    for gene in genes:
        rows.append(
            {
                "cancer_type": "TCGA-BRCA",
                "gene_symbol": gene,
                "consensus_decision": "prioritized" if gene in {"GENE1", "GENE2", "GENE3", "GENE4"} else "deprioritized",
                "publication_tier": "research_candidate" if gene in {"GENE1", "GENE2", "GENE3"} else "exploratory",
            }
        )
    pl.DataFrame(rows).write_parquet(path)


def _write_gmt(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                "Cell cycle\tR-HSA-1640170\tGENE1\tGENE2\tGENE3\tGENE5\tGENE6",
                "Immune signaling\tR-HSA-168256\tGENE7\tGENE8\tGENE9\tGENE10\tGENE11",
            ]
        ),
        encoding="utf-8",
    )


def test_load_gmt_pathways_parses_reactome_ids(tmp_path: Path) -> None:
    gmt = tmp_path / "reactome.gmt"
    _write_gmt(gmt)

    pathways = load_gmt_pathways(gmt)

    assert pathways[0]["pathway_id"] == "R-HSA-1640170"
    assert pathways[0]["genes"] == ["GENE1", "GENE2", "GENE3", "GENE5", "GENE6"]


def test_build_pathway_enrichment_scores_candidate_overlap(tmp_path: Path) -> None:
    consensus = tmp_path / "consensus.parquet"
    gmt = tmp_path / "reactome.gmt"
    output = tmp_path / "pathway.parquet"
    _write_consensus(consensus)
    _write_gmt(gmt)

    summary = build_pathway_enrichment(
        consensus_path=consensus,
        pathway_gmt_path=gmt,
        output_path=output,
        report_path=tmp_path / "report.json",
        min_overlap=2,
    )
    result = pl.read_parquet(output)
    rows = {(row["candidate_set"], row["pathway_name"]): row for row in result.to_dicts()}

    assert summary["status"] == "completed"
    assert summary["pathway_count"] == 2
    assert rows[("prioritized", "Cell cycle")]["overlap_gene_count"] == 3
    assert rows[("prioritized", "Cell cycle")]["p_value"] <= 1.0
    assert rows[("prioritized", "Cell cycle")]["enrichment_score"] > 0.0


def test_pathway_enrichment_query_filters_rows(tmp_path: Path) -> None:
    consensus = tmp_path / "consensus.parquet"
    gmt = tmp_path / "reactome.gmt"
    output = tmp_path / "pathway.parquet"
    _write_consensus(consensus)
    _write_gmt(gmt)
    build_pathway_enrichment(
        consensus_path=consensus,
        pathway_gmt_path=gmt,
        output_path=output,
        report_path=tmp_path / "report.json",
        min_overlap=2,
    )

    payload = pathway_enrichment(
        cancer_type="TCGA-BRCA",
        candidate_set="prioritized",
        pathway_query="cycle",
        max_fdr=1.0,
        min_overlap=2,
        gold_path=output,
    )

    assert payload["row_count"] == 1
    assert payload["rows"][0]["pathway_name"] == "Cell cycle"
    assert "hypothesis generation" in payload["warning"]


def test_pathway_enrichment_missing_inputs_writes_empty_contract(tmp_path: Path) -> None:
    output = tmp_path / "pathway.parquet"
    summary = build_pathway_enrichment(
        consensus_path=tmp_path / "missing.parquet",
        pathway_gmt_path=tmp_path / "missing.gmt",
        output_path=output,
        report_path=tmp_path / "report.json",
    )

    assert summary["status"] == "skipped_missing_inputs"
    assert pl.read_parquet(output).schema == PATHWAY_ENRICHMENT_SCHEMA
