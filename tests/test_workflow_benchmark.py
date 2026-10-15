from pathlib import Path

import polars as pl
import pytest

from src.operations.workflow_benchmark import compare_expression, docker_command, select_specimens


def specimens():
    return pl.DataFrame([{"source": "TCGA", "cohort": "BRCA", "tissue_site": "",
                          "recount_sample_id": f"sample{i}", "unit_id": f"case{i//2}"}
                         for i in range(80)])


def test_nested_specimen_selection_is_repeatable_and_unit_unique():
    a = select_specimens(specimens())
    b = select_specimens(specimens().reverse())
    assert a.equals(b)
    assert a.height == a["unit_id"].n_unique() == 30
    assert set(a.head(10)["recount_sample_id"]) <= set(a.head(20)["recount_sample_id"])
    with pytest.raises(ValueError, match="distinct"):
        select_specimens(specimens().head(4))


def test_export_comparison_checks_keys_units_and_finite_values(tmp_path):
    left, right = tmp_path / "a.tsv", tmp_path / "b.tsv"
    frame = pl.DataFrame({"gene_id": ["ENSG1", "ENSG2"], "sampleA": [1., 2.], "sampleB": [3., 4.]})
    frame.write_csv(left, separator="\t")
    frame.write_csv(right, separator="\t")
    assert compare_expression(left, right)["comparable"]
    frame.reverse().write_csv(right, separator="\t")
    assert not compare_expression(left, right)["comparable"]
    frame.with_columns(pl.lit(float("inf")).alias("sampleA")).write_csv(right, separator="\t")
    assert not compare_expression(left, right)["comparable"]


def test_benchmark_enforces_same_architecture_and_limits():
    command = docker_command("image-sha", ["Rscript", "worker.R"])
    assert command[command.index("--platform") + 1] == "linux/amd64"
    assert command[command.index("--cpus") + 1] == "4"
    assert command[command.index("--memory") + 1] == "12g"
    assert command[command.index("--network") + 1] == "none"
