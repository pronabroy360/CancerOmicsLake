from dataclasses import asdict
import gzip
import shutil

import numpy as np
import polars as pl
import pytest
import yaml

from src.analytics.controlled_reference_study import rank_biserial
from src.analytics.matched_processing import run_study as run_v1
from src.analytics.matched_processing_v2 import (
    Config, _bootstrap, _metric_rows, annotation_audit, prepare, run_study as run_v2,
)
from src.operations.matched_processing_v2_review import _check, _no_ids
from src.analytics.matched_processing_v2_metrics import (
    bootstrap_indices, chunked_effects, concordance, effect_distribution,
    informative_genes, tie_overlap,
)
from tests.test_matched_processing import _fixture


def test_filter_requires_detection_in_every_group_and_pipeline():
    matrices = {"native": (np.array([[1, 0, 0, 0, 0], [1, 1, 0, 0, 0], [1] * 5]),
                           np.array([[1] * 5, [0] * 5, [1] * 5])),
                "recount3": (np.array([[1] * 5, [1] * 5, [1] * 5]),
                             np.array([[1] * 5, [1] * 5, [1] * 5]))}
    assert informative_genes(matrices, .2).tolist() == [True, False, True]
    assert informative_genes(matrices, .4).tolist() == [False, False, True]


def test_ties_direction_and_effect_saturation_are_explicit():
    genes = np.array(["A", "B", "C", "D", "E"])
    native = np.array([1., 1., 1., .5, 0.])
    recount = np.array([1., -.7, .3, 0., 0.])
    a = tie_overlap(genes, native, recount, 2, 200, np.random.default_rng(7))
    b = tie_overlap(genes, native, recount, 2, 200, np.random.default_rng(7))
    assert a == b and a["native_boundary_ties"] == 3 and a["native_boundary_slots"] == 2
    assert a["tie_q025_jaccard"] <= a["tie_mean_jaccard"] <= a["tie_q975_jaccard"]
    result = concordance(native, recount, .2)
    assert result["direction_denominator"] == 3
    assert result["direction_agreement"] == pytest.approx(2 / 3)
    assert effect_distribution(native)["saturated_effect_genes"] == 3
    assert effect_distribution(native)["zero_effect_genes"] == 1
    all_tied = tie_overlap(genes, np.ones(5), np.ones(5), 2, 30, np.random.default_rng(1))
    assert all_tied["native_boundary_ties"] == all_tied["recount_boundary_ties"] == 5
    assert all_tied["deterministic_jaccard"] == 1
    assert concordance(np.zeros(5), np.zeros(5), .2)["kendall_tau_b"] is None


def test_biological_unit_bootstrap_keeps_grouped_samples_and_chunk_effects():
    units = ["case-a", "case-a", "case-b"]
    draw = bootstrap_indices(units, np.random.default_rng(4))
    assert len(draw) in (2, 3, 4) and set(draw).issubset({0, 1, 2})
    assert np.count_nonzero(draw == 0) == np.count_nonzero(draw == 1)
    tumor = np.array([[1., 2., 3.], [0., 0., 1.]])
    normal = np.array([[0., 1.], [0., 0.]])
    indices_t, indices_n = np.array([0, 1, 1, 2]), np.array([0, 0, 1])
    assert np.allclose(chunked_effects(tumor, normal, indices_t, indices_n, 1),
                       rank_biserial(tumor[:, indices_t], normal[:, indices_n]))


def test_v2_lock_rejects_changed_v1_snapshot_and_annotation_conflicts(tmp_path):
    v1_config, bronze, silver, output, private = _fixture(tmp_path)
    for source in ("tcga", "gtex"):
        path = silver / f"silver_expression_{source}.parquet"
        pl.read_parquet(path).with_columns(pl.lit("TPM").alias("expression_unit")).write_parquet(path)
    v1 = run_v1(v1_config, bronze, silver, output, private)
    shutil.copyfile(silver / "silver_expression_recount3_fixture_matched.parquet",
                    silver / "silver_expression_recount3_matched_processing_v1.parquet")
    config = tmp_path / "v2.yml"
    settings = asdict(Config(expected_matched_specimens=14, bootstrap_repeats=2,
                             tie_draws=2, bootstrap_tie_draws=2))
    settings["top_k"] = list(settings["top_k"])
    config.write_text(yaml.safe_dump(settings))
    _, manifest, plan, _, _ = prepare(config, output / "fixture_matched", silver,
                                      tmp_path / "private-v2", tmp_path / "output-v2")
    assert manifest.height == 14 and plan["input_row_counts"]["silver_expression_tcga"] == 18
    audit = annotation_audit(manifest, silver)
    assert len(audit) == 6 and all(row["shared_gene_ids"] == 3 for row in audit)
    tcga = pl.read_parquet(silver / "silver_expression_tcga.parquet")
    tcga.with_columns(pl.when(pl.col("gene_id") == "ENSG1").then(pl.lit("OTHER"))
                      .otherwise(pl.col("gene_id")).alias("gene_symbol")).write_parquet(
                          silver / "silver_expression_tcga.parquet")
    changed = annotation_audit(manifest, silver)
    assert sum(row["shared_symbol_conflicts"] for row in changed if row["source"] == "TCGA") > 0
    with pytest.raises(ValueError, match="v1 frozen input"):
        prepare(config, output / "fixture_matched", silver, tmp_path / "private-v2",
                tmp_path / "output-v2")


def test_v2_metric_rows_and_paired_bootstrap_are_deterministic(tmp_path):
    config = Config(expected_matched_specimens=5, bootstrap_repeats=2,
                    tie_draws=5, bootstrap_tie_draws=3)
    genes = np.array([f"GENE{i:03}" for i in range(120)])
    tumor = np.tile(np.array([[4., 5., 6.]]), (120, 1)).astype(float)
    normal = np.tile(np.array([[1., 2.]]), (120, 1)).astype(float)
    tumor[::4] = 0
    matrices = {"native": (tumor, normal), "recount3": (tumor * 100, normal * 100)}
    all_mask = np.ones(120, dtype=bool)
    effects = {name: chunked_effects(t, n, np.arange(3), np.arange(2), 17)
               for name, (t, n) in matrices.items()}
    summary, top = _metric_rows(genes, effects, all_mask, config, "TCGA-BRCA", "all_shared", 3)
    assert summary["status"] == "completed" and len(top) == 3
    assert top[0]["native_boundary_ties"] >= 25
    incomplete, skipped_top = _metric_rows(genes, effects, np.arange(120) < 99,
                                           config, "TCGA-BRCA", "informative", 3)
    assert incomplete["status"] == "incomplete_too_few_genes" and skipped_top == []
    units = {"tumor": ["case-a", "case-a", "case-b"], "normal": ["donor-a", "donor-b"]}
    first = _bootstrap(matrices, units, genes, {"all_shared": all_mask},
                       config, "TCGA-BRCA", tmp_path)
    second = _bootstrap(matrices, units, genes, {"all_shared": all_mask},
                        config, "TCGA-BRCA", tmp_path)
    assert first == second and len(first[0]) == 2 and len(first[1]) == 6


def test_review_rejects_individual_ids():
    with pytest.raises(ValueError, match="Individual specimen identifier"):
        _no_ids("specimen TCGA-ABC-123", {"TCGA-ABC-123"})
    _no_ids("BRCA aggregate count 162", {"TCGA-ABC-123"})


def test_review_rejects_changed_hashed_output(tmp_path):
    import hashlib
    path = tmp_path / "aggregate.csv"
    path.write_text("count,2\n")
    item = {"path": str(path), "bytes": path.stat().st_size,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    assert _check(item)["sha256"] == item["sha256"]
    path.write_text("count,3\n")
    with pytest.raises(ValueError, match="hash mismatch"):
        _check(item)


def test_v2_end_to_end_synthetic_report_preserves_v1(tmp_path):
    v1_config, bronze, silver, output, private = _fixture(tmp_path)
    v1_settings = yaml.safe_load(v1_config.read_text())
    v1_settings["top_k"] = [25, 50, 100]
    v1_config.write_text(yaml.safe_dump(v1_settings))
    genes = [f"ENSG{i:011d}" for i in range(1, 121)]
    annotation = bronze / "human.gene_sums.G026.gtf.gz"
    with gzip.open(annotation, "wt") as stream:
        for i, gene in enumerate(genes):
            stream.write(f'chr1\tHAVANA\tgene\t{i+1}\t{i+2}\t.\t+\t.\t'
                         f'gene_id "{gene}.1"; gene_name "G{i}";\n')
    for source in ("tcga", "gtex"):
        path = silver / f"silver_expression_{source}.parquet"
        original = pl.read_parquet(path)
        fields = [field for field in original.columns if field not in
                  ("gene_id", "gene_symbol", "expression_value")]
        rows = original.select(fields).unique().join(
            pl.DataFrame({"gene_id": genes, "gene_index": list(range(120))}), how="cross")
        rows = rows.with_columns((pl.col("gene_index") % 7 + (10 if source == "tcga" else 1))
                                 .cast(pl.Float64).alias("expression_value"),
                                 pl.concat_str(pl.lit("G"), pl.col("gene_index")).alias("gene_symbol"),
                                 pl.lit("TPM").alias("expression_unit")).drop("gene_index")
        rows.write_parquet(path)
    for counts in bronze.glob("*/*/*.gene_sums.*.G026.gz"):
        with gzip.open(counts, "rt") as stream:
            headers = [stream.readline().rstrip("\n") for _ in range(3)]
        samples = headers[-1].split("\t")[1:]
        with gzip.open(counts, "wt") as stream:
            stream.write("\n".join(headers) + "\n")
            for i, gene in enumerate(genes):
                stream.write(gene + ".1\t" + "\t".join(str((i % 7 + 1) * 100)
                                                         for _ in samples) + "\n")
    prior = run_v1(v1_config, bronze, silver, output, private)
    shutil.copyfile(silver / "silver_expression_recount3_fixture_matched.parquet",
                    silver / "silver_expression_recount3_matched_processing_v1.parquet")
    config = tmp_path / "v2.yml"
    settings = asdict(Config(expected_matched_specimens=14, bootstrap_repeats=2,
                             tie_draws=4, bootstrap_tie_draws=3))
    settings["top_k"] = list(settings["top_k"])
    config.write_text(yaml.safe_dump(settings))
    result = run_v2(config, output / "fixture_matched", silver,
                    tmp_path / "private-v2", tmp_path / "output-v2")
    assert result["status"] == "completed" and len(result["topk"]) == 18
    assert all(row["bootstrap_replicates"] == 2 for row in result["topk"])
    prior_text = (output / "fixture_matched" / "report.json").read_text()
    assert run_v2(config, output / "fixture_matched", silver,
                  tmp_path / "private-v2", tmp_path / "output-v2")["outputs"] == result["outputs"]
    assert (output / "fixture_matched" / "report.json").read_text() == prior_text
    aggregate = (tmp_path / "output-v2" / "matched_processing_v2" / "report.json").read_text()
    assert "native-BRCA" not in aggregate and prior["matched_specimens"] == 14
