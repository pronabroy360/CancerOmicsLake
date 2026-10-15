from dataclasses import replace
import json
from pathlib import Path

import numpy as np
import polars as pl
import pytest
from scipy.stats import mannwhitneyu
import yaml

from src.analytics.controlled_reference_study import (
    StudyConfig, _matrix, cluster_bootstrap, development_sensitivity, evaluate_ranking,
    expression_mask, fold_change, grouped_partition, global_partition, assert_no_global_leakage, lock_plan,
    rank_biserial, run_controlled_reference_study, select_balanced_units, paired_subsample_indices,
)


def config(**kwargs) -> StudyConfig:
    return StudyConfig(study_id="fixture", projects={"TCGA-BRCA": "Breast - Mammary Tissue"},
                       min_units_per_group=4, max_units_per_group=6, development_repeats=2,
                       training_bootstraps=20, holdout_bootstraps=20, top_k=(2,),
                       expression_thresholds=(0.0, 1.0), pseudocounts=(1.0,), scale_factors=(0.1, 1.0, 10.0),
                       **kwargs)


def matrices():
    tumor = np.array([[10., 11, 12, 13], [0.2, 0.3, 0.4, 0.5], [8, 9, 10, 11], [1, 2, 3, 4]])
    adjacent = np.array([[1., 2, 3, 4], [0.01, 0.02, 0.03, 0.04], [1, 2, 3, 4], [1, 2, 3, 4]])
    gtex = np.array([[1., 2, 3, 4], [0.01, 0.02, 0.03, 0.04], [20, 21, 22, 23], [1, 2, 3, 4]])
    return {"tumor": tumor, "adjacent": adjacent, "gtex": gtex}


def units():
    return {"tumor": ["a", "b", "c", "d"], "adjacent": ["a", "b", "c", "d"],
            "gtex": ["w", "x", "y", "z"]}


def test_grouped_split_keeps_all_case_and_donor_samples_together():
    rows = [{"source": "TCGA", "unit_id": f"p{i}", "sample_id": f"p{i}-{group}", "group": group}
            for i in range(10) for group in ("tumor", "adjacent")]
    rows += [{"source": "GTEX", "unit_id": f"d{i}", "sample_id": f"d{i}-{s}", "group": "gtex"}
             for i in range(10) for s in range(2)]
    result = grouped_partition(pl.DataFrame(rows), 0.5, 42)
    assert result.group_by(["source", "unit_id"]).agg(pl.col("partition").n_unique())["partition"].max() == 1
    assert result.sort("sample_id").equals(grouped_partition(pl.DataFrame(rows).reverse(), 0.5, 42).sort("sample_id"))


def test_effect_agrees_with_u_and_is_invariant_to_monotone_scale():
    data = matrices()
    observed = rank_biserial(data["tumor"], data["gtex"])
    expected = [2 * mannwhitneyu(t, n).statistic / (len(t) * len(n)) - 1
                for t, n in zip(data["tumor"], data["gtex"])]
    assert np.allclose(observed, expected)
    assert np.allclose(observed, rank_biserial(np.log1p(data["tumor"] * 10), np.log1p(data["gtex"] * 10)))
    baseline = fold_change(data["tumor"], data["gtex"], 1)
    assert np.allclose(baseline, fold_change(data["tumor"], data["gtex"], 1, 10, True))
    assert not np.allclose(baseline, fold_change(data["tumor"], data["gtex"], 1, 10, False))


def test_cluster_bootstrap_resamples_tcga_pairs_together():
    data = {g: np.tile(np.arange(4, dtype=float), (2, 1)) for g in units()}
    draw = cluster_bootstrap(data, units(), np.random.default_rng(7))
    assert np.array_equal(draw["tumor"], draw["adjacent"])


def test_balanced_pair_selection_preserves_case_matches_and_partition():
    rows = [{"source": "TCGA", "unit_id": f"p{i}", "sample_id": f"p{i}-{g}", "group": g}
            for i in range(20) for g in ("tumor", "adjacent")]
    rows += [{"source": "GTEX", "unit_id": f"d{i}", "sample_id": f"d{i}", "group": "gtex"}
             for i in range(20)]
    split = grouped_partition(pl.DataFrame(rows), .5, 7)
    selected = select_balanced_units(split, 6, 8, True)
    for partition in ("development", "holdout"):
        subset = selected.filter(pl.col("partition") == partition)
        cases = {g: set(subset.filter(pl.col("group") == g)["unit_id"]) for g in ("tumor", "adjacent", "gtex")}
        assert cases["tumor"] == cases["adjacent"]
        assert all(len(ids) == 6 for ids in cases.values())
    assert selected.group_by("source", "unit_id").agg(pl.col("partition").n_unique())["partition"].max() == 1


def test_paired_subsampling_keeps_matching_cases_even_if_columns_are_reordered():
    identities = units()
    identities["adjacent"] = identities["adjacent"][::-1]
    selected = paired_subsample_indices(identities, 3, np.random.default_rng(8))
    cases = {g: {identities[g][i] for i in selected[g]} for g in identities}
    assert cases["tumor"] == cases["adjacent"] and len(cases["tumor"]) == 3
    assert len(cases["gtex"]) == 3
    broken = {**identities, "adjacent": ["a", "b", "c", "unmatched"]}
    with pytest.raises(ValueError, match="matched"):
        paired_subsample_indices(broken, 3, np.random.default_rng(8))


def test_holdout_values_do_not_change_training_selection():
    cfg = config()
    train = matrices()
    rows, scores, directions = evaluate_ranking(train, train, units(), units(), cfg, 7)
    changed = {g: value[::-1].copy() for g, value in train.items()}
    other_rows, other_scores, other_directions = evaluate_ranking(train, changed, units(), units(), cfg, 7)
    assert all(np.array_equal(scores[g], other_scores[g]) for g in scores)
    assert all(np.array_equal(directions[g], other_directions[g]) for g in directions)
    assert rows != other_rows
    assert scores["reference_stability_lower_quantile"][0] > 0
    assert scores["reference_stability_lower_quantile"][2] == 0
    assert all(-1 <= r["mean_worst_reference_effect"] <= 1 for r in rows)


def test_sensitivity_is_development_only_and_equivariant():
    result = development_sensitivity(matrices(), units(), config(), 1)
    assert len({row["repeat"] for row in result}) == 2
    assert all(row["group_size"] == 3 for row in result)
    assert all(row["scaled_pseudocount_scale_jaccard"] == 1 for row in result)
    assert expression_mask(matrices(), 1, 0.2).tolist() == [True, False, True, True]


def test_plan_rejects_protocol_or_snapshot_changes(tmp_path):
    path = tmp_path / "plan.json"
    first = lock_plan(path, {"seed": 1, "input_sha256": "a"})
    assert first == lock_plan(path, {"input_sha256": "a", "seed": 1})
    with pytest.raises(RuntimeError, match="Frozen study"):
        lock_plan(path, {"seed": 1, "input_sha256": "b"})
    assert json.loads(path.read_text())["input_sha256"] == "a"


def test_matrix_keeps_distinct_pseudoautosomal_loci():
    frame = pl.DataFrame({"sample_id": ["s", "s"],
                          "gene_id": ["ENSG00000002586.20", "ENSG00000002586.20_PAR_Y"],
                          "expression_value": [1., 2.], "expression_unit": ["TPM", "TPM"]})
    result = _matrix(frame.lazy(), pl.DataFrame({"sample_id": ["s"]}), "sample_id")
    assert set(result["gene_id"]) == {"ENSG00000002586", "ENSG00000002586_PAR_Y"}


@pytest.mark.parametrize("change", [{"study_id": "../escape"}, {"holdout_fraction": 1},
                                    {"top_k": (0,)}, {"scale_factors": (float("nan"),)},
                                    {"seed": -1}, {"training_bootstraps": 3}])
def test_invalid_protocol_rejected(change):
    with pytest.raises(ValueError):
        replace(config(), **change)


def _write_fixture(silver: Path):
    silver.mkdir()
    tcga, gtex = [], []
    for i in range(12):
        for group in ("Primary Tumor", "Solid Tissue Normal"):
            for g in range(10):
                tcga.append({"project_id": "TCGA-BRCA", "case_id": f"p{i}",
                             "sample_id": f"p{i}-{group}", "sample_type": group,
                             "gene_id": f"ENSG{g:011d}", "expression_unit": "TPM",
                             "expression_value": float(3 + i / 20 + (g + 1 if group == "Primary Tumor" else 0))})
        for g in range(10):
            gtex.append({"gtex_sample_id": f"d{i}-a", "donor_id": f"d{i}",
                         "tissue_site": "Breast - Mammary Tissue", "gene_id": f"ENSG{g:011d}",
                         "expression_unit": "TPM", "expression_value": float(1 + i / 20)})
    pl.DataFrame(tcga).write_parquet(silver / "silver_expression_tcga.parquet")
    pl.DataFrame(gtex).write_parquet(silver / "silver_expression_gtex.parquet")


def test_global_partition_keeps_shared_donors_together_across_cancers():
    rows = [{"cancer_type": cancer, "source": "GTEX", "unit_id": f"d{i}",
             "sample_id": f"{cancer}-d{i}", "group": "gtex"}
            for cancer in ("TCGA-BRCA", "TCGA-LUAD", "TCGA-COAD") for i in range(24)]
    index = pl.DataFrame(rows)
    split = global_partition(index, .5, 42)
    assert_no_global_leakage(split)
    assert split.sort("sample_id").equals(global_partition(index.reverse(), .5, 42).sort("sample_id"))
    assert set(split["group"]) == {"gtex"}
    broken = split.with_columns(pl.when(pl.col("sample_id") == "TCGA-BRCA-d0")
                               .then(pl.when(pl.col("partition") == "holdout")
                                     .then(pl.lit("development")).otherwise(pl.lit("holdout")))
                               .otherwise(pl.col("partition")).alias("partition"))
    with pytest.raises(RuntimeError, match="Global patient/donor leakage"):
        assert_no_global_leakage(broken)


def test_end_to_end_multicancer_shared_donors_use_global_partition(tmp_path):
    from dataclasses import asdict
    silver = tmp_path / "silver"
    _write_fixture(silver)
    tcga_path = silver / "silver_expression_tcga.parquet"
    tcga = pl.read_parquet(tcga_path)
    lung = tcga.with_columns(pl.lit("TCGA-LUAD").alias("project_id"),
                             (pl.lit("lung-") + pl.col("sample_id")).alias("sample_id"),
                             (pl.lit("lung-") + pl.col("case_id")).alias("case_id"))
    pl.concat([tcga, lung]).write_parquet(tcga_path)
    gtex_path = silver / "silver_expression_gtex.parquet"
    gtex = pl.read_parquet(gtex_path)
    pl.concat([gtex, gtex.with_columns(pl.lit("Lung").alias("tissue_site"),
               (pl.lit("lung-") + pl.col("gtex_sample_id")).alias("gtex_sample_id"))]).write_parquet(gtex_path)
    cfg_path = tmp_path / "config.yml"
    cfg_path.write_text(yaml.safe_dump(asdict(replace(config(), projects={"TCGA-BRCA": "Breast - Mammary Tissue", "TCGA-LUAD": "Lung"}))))
    report = run_controlled_reference_study(cfg_path, silver, tmp_path / "output", tmp_path / "private")
    assert report["global_group_leakage_count"] == 0
    assert len(report["cohort_audit"]) == 2
    split = pl.read_parquet(tmp_path / "private/fixture/sample_split_manifest.parquet")
    assert_no_global_leakage(split)
    assert_no_global_leakage(split.filter(pl.col("selected")))


def test_end_to_end_study_keeps_split_private_and_deterministic(tmp_path):
    from dataclasses import asdict
    silver = tmp_path / "silver"
    _write_fixture(silver)
    cfg_path = tmp_path / "config.yml"
    cfg_path.write_text(yaml.safe_dump(asdict(config())))
    output, private = tmp_path / "outputs", tmp_path / "private"
    result = run_controlled_reference_study(cfg_path, silver, output, private)
    assert result["status"] == "completed"
    assert result["cohort_audit"][0]["group_leakage_count"] == 0
    split = pl.read_parquet(private / "fixture/sample_split_manifest.parquet")
    assert split.group_by(["source", "unit_id"]).agg(pl.col("partition").n_unique())["partition"].max() == 1
    for artifact in result["outputs"]:
        columns = pl.read_parquet_schema(artifact["path"])
        assert not {"case_id", "donor_id", "sample_id", "unit_id"} & set(columns)
    second = run_controlled_reference_study(cfg_path, silver, output, private)
    assert second["outputs"] == result["outputs"]
