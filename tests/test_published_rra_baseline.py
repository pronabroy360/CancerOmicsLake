import hashlib
import json
from pathlib import Path

import numpy as np
import polars as pl
import pytest

from src.analytics.published_rra_baseline import _rank_inputs, _rra_rows, _validate_r_scores, _verify_frozen
from src.analytics.controlled_reference_study import StudyConfig, evaluate_ranking
from src.operations.published_rra_review import build_review


def _matrices():
    return {"tumor": np.array([[10., 11., 12., 13.], [1., 1., 1., 1.], [2., 3., 4., 5.]]),
            "adjacent": np.array([[1., 2., 1., 2.], [1., 1., 1., 1.], [5., 4., 3., 2.]]),
            "gtex": np.array([[1., 2., 1., 2.], [1., 1., 1., 1.], [0., 0., 0., 0.]])}


def _config():
    return StudyConfig(study_id="rra_fixture", projects={"TCGA-BRCA": "Breast - Mammary Tissue"},
                       min_units_per_group=4, max_units_per_group=4, development_repeats=2,
                       training_bootstraps=20, holdout_bootstraps=20, top_k=(2,),
                       expression_thresholds=(0., 1.), pseudocounts=(1.,), scale_factors=(1.,))


def _units():
    return {"tumor": list("abcd"), "adjacent": list("abcd"), "gtex": list("wxyz")}


def test_rra_rank_input_uses_full_permutations_and_canonical_ties():
    genes = np.array(["ENSG1", "ENSG2", "ENSG3"])
    frame = _rank_inputs(genes, _matrices())
    assert frame["gene_id"].to_list() == genes.tolist()
    assert sorted(frame["adjacent_rank"].to_list()) == [1, 2, 3]
    assert sorted(frame["gtex_rank"].to_list()) == [1, 2, 3]
    all_tied = {group: np.ones_like(values) for group, values in _matrices().items()}
    assert _rank_inputs(genes, all_tied)["adjacent_rank"].to_list() == [1, 2, 3]
    with pytest.raises(ValueError, match="canonical"):
        _rank_inputs(genes[::-1], _matrices())
    with pytest.raises(ValueError, match="unique"):
        _rank_inputs(np.array(["ENSG1", "ENSG1", "ENSG3"]), _matrices())


def test_rra_output_rejects_missing_reordered_or_nonfinite_genes():
    genes = np.array(["ENSG1", "ENSG2"])
    good = pl.DataFrame({"gene_id": genes, "score": [.1, .9]})
    assert np.allclose(_validate_r_scores(good, genes), [.9, .1])
    with pytest.raises(ValueError, match="ordering"):
        _validate_r_scores(good.reverse(), genes)
    with pytest.raises(ValueError, match="Invalid"):
        _validate_r_scores(good.with_columns(pl.lit(float("nan")).alias("score")), genes)
    with pytest.raises(ValueError, match="schema"):
        _validate_r_scores(good.rename({"score": "pvalue"}), genes)


def test_frozen_candidate_verification_fails_on_changed_gene():
    matrices, units, config = _matrices(), _units(), _config()
    rows, scores, _ = evaluate_ranking(matrices, matrices, units, units, config, 42)
    genes = np.array(["ENSG1", "ENSG2", "ENSG3"])
    candidates = pl.DataFrame([{"cancer_type": "TCGA-BRCA", "method": method, "rank": rank,
                                "gene_id": genes[i]}
                               for method, score in scores.items()
                               for rank, i in enumerate(np.argsort(-np.round(score, 12), kind="stable")[:2], 1)])
    evaluation = pl.DataFrame([{"cancer_type": "TCGA-BRCA", **r} for r in rows])
    _verify_frozen("TCGA-BRCA", rows, scores, genes, candidates, evaluation, (2,))
    changed = candidates.with_columns(pl.when(pl.col("rank") == 1).then(pl.lit("ENSG999"))
                                      .otherwise(pl.col("gene_id")).alias("gene_id"))
    with pytest.raises(RuntimeError, match="candidates"):
        _verify_frozen("TCGA-BRCA", rows, scores, genes, changed, evaluation, (2,))


def test_rra_paired_bootstrap_rows_have_valid_denominators():
    matrices, units, config = _matrices(), _units(), _config()
    existing, scores, _ = evaluate_ranking(matrices, matrices, units, units, config, 42)
    rows = _rra_rows(np.array(["ENSG1", "ENSG2", "ENSG3"]), matrices, matrices,
                     units, units, config, 42, np.array([.8, .1, .5]), existing, scores["rra_style"])
    assert len(rows) == 1
    row = rows[0]
    assert row["selected_count"] == 2
    assert 0 <= row["discordant_reference_direction_count"] <= 2
    assert 0 <= row["rra_style_topk_jaccard"] <= 1
    assert row["replication_fraction_ci_low"] <= row["replication_fraction_ci_high"]
    assert row == _rra_rows(np.array(["ENSG1", "ENSG2", "ENSG3"]), matrices, matrices,
                            units, units, config, 42, np.array([.8, .1, .5]), existing,
                            scores["rra_style"])[0]


def test_review_requires_all_cells_and_is_immutable(tmp_path):
    previous, comparator, private, output = [tmp_path / name for name in ("previous", "comparator", "private", "new")]
    for path in (previous, comparator):
        path.mkdir()
    sample_id = "private-sample-0001"
    studies = ("native_reference_global_v1", "native_reference_paired_global_v1")
    for name in studies:
        root = private / name
        root.mkdir(parents=True)
        pl.DataFrame({"sample_id": [sample_id], "unit_id": ["private-donor-0001"]}).write_parquet(
            root / "sample_split_manifest.parquet")
    (previous / "review.json").write_text(json.dumps({"resources": [], "publication_enabled": False}))
    plan = {"studies": list(studies), "implementation_resources": [], "input_resources": [],
            "frozen_resources": []}
    (comparator / "study_plan.json").write_text(json.dumps(plan))
    (comparator / "comparison.csv").write_text("aggregate-only\n")
    rows = [{"study_id": study, "cancer_type": cancer, "top_k": k,
             "replication_fraction": .4, "proposed_minus_baseline_replication_fraction": -.1,
             "proposed_minus_baseline_replication_fraction_ci_low": -.2,
             "proposed_minus_baseline_replication_fraction_ci_high": 0.,
             "discordant_reference_direction_count": 1, "selected_count": k}
            for study in studies for cancer in ("TCGA-BRCA", "TCGA-COAD", "TCGA-LUAD")
            for k in (25, 50, 100)]
    report = {"status": "completed", "publication_enabled": False,
              "individual_identifiers_exported": False,
              "plan_sha256": hashlib.sha256(json.dumps(plan, sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
              "study_id": "published_rra_baseline_v1", "r_package": {}, "r_image": {},
              "comparisons": rows, "limitations": [],
              "outputs": [{"path": str(comparator / "comparison.csv"),
                           "sha256": hashlib.sha256((comparator / "comparison.csv").read_bytes()).hexdigest()}]}
    (comparator / "report.json").write_text(json.dumps(report))
    first = build_review(previous, comparator, output, private)
    assert first["publication_enabled"] is False
    assert build_review(previous, comparator, output, private) == first
    report["comparisons"][0]["study_id"] = sample_id
    (comparator / "report.json").write_text(json.dumps(report))
    with pytest.raises(RuntimeError, match="missing study/cancer/top-k"):
        build_review(previous, comparator, tmp_path / "leak", private)
