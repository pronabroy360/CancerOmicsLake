from __future__ import annotations

from pathlib import Path

import polars as pl

from src.analytics.evidence_confidence import build_evidence_confidence, evidence_confidence


def _write_fixture(root: Path, sensitivity_direction: str = "rank_up") -> tuple[Path, Path]:
    gold = root / "gold"
    silver = root / "silver"
    gold.mkdir()
    silver.mkdir()
    pl.DataFrame(
        [
            {
                "cancer_type": "TCGA-BRCA",
                "gene_symbol": "TP53",
                "mutation_frequency": 0.2,
                "mutated_sample_count": 20,
                "total_profiled_sample_count": 100,
                "abs_log2_fold_change": 2.0,
                "log2_fold_change": 2.0,
                "graph_degree": 2,
                "evidence_count": 2,
                "priority_score": 0.7,
                "priority_tier": "high",
                "evidence_summary": "fixture",
            },
            {
                "cancer_type": "TCGA-LUAD",
                "gene_symbol": "EGFR",
                "mutation_frequency": 0.1,
                "mutated_sample_count": 2,
                "total_profiled_sample_count": 10,
                "abs_log2_fold_change": 0.0,
                "log2_fold_change": 0.0,
                "graph_degree": 1,
                "evidence_count": 1,
                "priority_score": 0.2,
                "priority_tier": "medium",
                "evidence_summary": "fixture",
            },
        ]
    ).write_parquet(gold / "gold_candidate_gene_priority.parquet")
    pl.DataFrame(
        {
            "cancer_type": ["TCGA-BRCA"],
            "gene_symbol": ["TP53"],
            "sample_count_tumor": [30],
            "sample_count_normal": [2],
        }
    ).write_parquet(gold / "gold_tumor_vs_normal_expression.parquet")
    pl.DataFrame(
        {
            "cancer_type": ["TCGA-BRCA"],
            "gene_symbol": ["TP53"],
            "sensitivity_direction": [sensitivity_direction],
            "support_tier": ["high"],
            "percentile_delta": [0.4 if sensitivity_direction == "rank_up" else -0.4],
            "robust_z_delta": [1.5 if sensitivity_direction == "rank_up" else -1.5],
        }
    ).write_parquet(gold / "gold_batch_effect_sensitivity.parquet")
    pl.DataFrame(
        {
            "node_id": ["GENE:TP53", "GENE:EGFR"],
            "node_label": ["Gene", "Gene"],
            "name": ["TP53", "EGFR"],
            "total_degree": [5, 1],
        }
    ).write_parquet(gold / "gold_graph_node_metrics.parquet")
    pl.DataFrame(
        {
            "edge_type": ["MUTATED_IN_CANCER", "MUTATED_IN_CANCER"],
            "source_node_id": ["GENE:TP53", "GENE:EGFR"],
            "target_node_id": ["TCGA-BRCA", "TCGA-LUAD"],
        }
    ).write_parquet(gold / "gold_graph_edges.parquet")
    pl.DataFrame(
        {
            "project_id": ["TCGA-BRCA", "TCGA-LUAD"],
            "gene_symbol": ["TP53", "EGFR"],
            "data_origin": ["gdc_download", "gdc_download"],
        }
    ).write_parquet(silver / "silver_mutations.parquet")
    pl.DataFrame(
        {
            "project_id": ["TCGA-BRCA"],
            "gene_symbol": ["TP53"],
            "data_origin": ["gdc_download"],
        }
    ).write_parquet(silver / "silver_expression_tcga.parquet")
    pl.DataFrame(
        {
            "tissue_site": ["Breast - Mammary Tissue"],
            "gene_symbol": ["TP53"],
            "data_origin": ["stub"],
        }
    ).write_parquet(silver / "silver_expression_gtex.parquet")
    return gold, silver


def test_build_evidence_confidence_penalizes_sparse_cross_study_expression(tmp_path: Path) -> None:
    gold, silver = _write_fixture(tmp_path)
    output = gold / "confidence.parquet"
    summary = build_evidence_confidence(gold_dir=gold, silver_dir=silver, output_path=output)
    result = pl.read_parquet(output)
    tp53 = result.filter(pl.col("gene_symbol") == "TP53").row(0, named=True)

    assert summary["row_count"] == 2
    assert tp53["expression_confidence"] < 0.3
    assert tp53["batch_effect_risk"] == "elevated"
    assert tp53["batch_concordance"] == "concordant"
    assert tp53["batch_sensitivity_confidence"] == 1.0
    assert tp53["traceability_confidence"] == 0.75
    assert "gtex_normal_support_below_30" in tp53["caveat_summary"]
    assert "source_provenance_incomplete" in tp53["caveat_summary"]
    assert result.get_column("quality_confidence").null_count() == 0
    assert result.filter(pl.col("gene_symbol") == "EGFR").row(0, named=True)["quality_status"] == "passed"


def test_build_evidence_confidence_penalizes_directional_discordance(tmp_path: Path) -> None:
    concordant_root = tmp_path / "concordant"
    discordant_root = tmp_path / "discordant"
    concordant_root.mkdir()
    discordant_root.mkdir()
    concordant_gold, concordant_silver = _write_fixture(concordant_root, "rank_up")
    discordant_gold, discordant_silver = _write_fixture(discordant_root, "rank_down")

    build_evidence_confidence(
        gold_dir=concordant_gold,
        silver_dir=concordant_silver,
        output_path=concordant_gold / "confidence.parquet",
    )
    build_evidence_confidence(
        gold_dir=discordant_gold,
        silver_dir=discordant_silver,
        output_path=discordant_gold / "confidence.parquet",
    )

    concordant = pl.read_parquet(concordant_gold / "confidence.parquet").filter(
        pl.col("gene_symbol") == "TP53"
    ).row(0, named=True)
    discordant = pl.read_parquet(discordant_gold / "confidence.parquet").filter(
        pl.col("gene_symbol") == "TP53"
    ).row(0, named=True)

    assert discordant["batch_concordance"] == "discordant"
    assert discordant["batch_effect_risk"] == "high"
    assert discordant["batch_sensitivity_confidence"] == 0.0
    assert discordant["expression_confidence"] < concordant["expression_confidence"]
    assert discordant["overall_confidence"] < concordant["overall_confidence"]
    assert "batch_sensitivity_direction_discordant" in discordant["caveat_summary"]


def test_evidence_confidence_query_filters_and_sorts(tmp_path: Path) -> None:
    gold, silver = _write_fixture(tmp_path)
    output = gold / "confidence.parquet"
    build_evidence_confidence(gold_dir=gold, silver_dir=silver, output_path=output)
    payload = evidence_confidence(
        cancer_type="TCGA-BRCA",
        gene_query="tp",
        batch_concordance="concordant",
        min_confidence=0.1,
        limit=10,
        gold_path=output,
    )

    assert payload["row_count"] == 1
    assert payload["rows"][0]["gene_symbol"] == "TP53"
    assert payload["filters"]["batch_concordance"] == "concordant"
    assert "not clinically validated" in payload["warning"]


def test_build_evidence_confidence_writes_empty_contract_without_candidates(tmp_path: Path) -> None:
    gold = tmp_path / "gold"
    silver = tmp_path / "silver"
    gold.mkdir()
    silver.mkdir()
    output = gold / "confidence.parquet"
    summary = build_evidence_confidence(gold_dir=gold, silver_dir=silver, output_path=output)

    assert summary["row_count"] == 0
    assert "overall_confidence" in pl.read_parquet(output).columns
