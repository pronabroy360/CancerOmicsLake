from __future__ import annotations

from pathlib import Path

import polars as pl

from src.analytics.candidate_priority import candidate_gene_priority, candidate_priority_dataframe


def _write_priority_fixture(path: Path) -> None:
    pl.DataFrame(
        [
            {
                "cancer_type": "TCGA-BRCA",
                "gene_symbol": "TP53",
                "mutation_frequency": 0.40,
                "mutated_sample_count": 4,
                "total_profiled_sample_count": 10,
                "abs_log2_fold_change": 1.5,
                "log2_fold_change": 1.5,
                "graph_degree": 2,
                "evidence_count": 2,
                "priority_score": 0.72,
                "priority_tier": "high",
                "evidence_summary": "mutation_frequency=0.4;abs_log2_fold_change=1.5",
            },
            {
                "cancer_type": "TCGA-LUAD",
                "gene_symbol": "EGFR",
                "mutation_frequency": 0.20,
                "mutated_sample_count": 2,
                "total_profiled_sample_count": 10,
                "abs_log2_fold_change": 0.2,
                "log2_fold_change": 0.2,
                "graph_degree": 2,
                "evidence_count": 2,
                "priority_score": 0.24,
                "priority_tier": "medium",
                "evidence_summary": "mutation_frequency=0.2;abs_log2_fold_change=0.2",
            },
        ]
    ).write_parquet(path)


def test_candidate_gene_priority_filters_and_sorts(tmp_path: Path) -> None:
    path = tmp_path / "priority.parquet"
    _write_priority_fixture(path)

    payload = candidate_gene_priority(cancer_type="TCGA-BRCA", tier="high", limit=10, gold_path=path)

    assert payload["row_count"] == 1
    assert payload["rows"][0]["gene_symbol"] == "TP53"
    assert payload["rows"][0]["priority_score"] == 0.72
    assert "not clinically validated" in str(payload["warning"])


def test_candidate_priority_dataframe_returns_empty_schema_when_missing(tmp_path: Path) -> None:
    df = candidate_priority_dataframe(gold_path=tmp_path / "missing.parquet")

    assert df.is_empty()
    assert "priority_score" in df.columns
