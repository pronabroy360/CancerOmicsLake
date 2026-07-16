from pathlib import Path

import polars as pl
import pytest

from src.operations.fair_release import build_fair_release


def _write_graph(gold: Path) -> None:
    pl.DataFrame(
        {
            "node_id": ["GENE:TP53", "CANCER:TCGA-LUAD", "SAMPLE:private"],
            "node_label": ["Gene", "CancerType", "Sample"],
            "name": ["TP53", "TCGA-LUAD", "private"],
        }
    ).write_parquet(gold / "gold_graph_nodes.parquet")
    pl.DataFrame(
        {
            "edge_id": ["safe", "unsafe"],
            "source_node_id": ["GENE:TP53", "SAMPLE:private"],
            "target_node_id": ["CANCER:TCGA-LUAD", "GENE:TP53"],
            "edge_type": ["MUTATED_IN_CANCER", "MUTATED_IN"],
        }
    ).write_parquet(gold / "gold_graph_edges.parquet")


def test_build_fair_release_writes_checksummed_public_bundle(tmp_path: Path) -> None:
    gold = tmp_path / "gold"
    gold.mkdir()
    pl.DataFrame(
        {"cancer_type": ["TCGA-LUAD"], "gene_symbol": ["TP53"], "score": [0.9]}
    ).write_parquet(gold / "aggregate.parquet")
    _write_graph(gold)

    payload = build_fair_release(
        "0.1.0",
        gold_dir=gold,
        output_root=tmp_path / "releases",
        required_files=("aggregate.parquet",),
    )

    release = Path(payload["release_directory"])
    assert payload["resource_count"] == 3
    assert payload["identifier_safety"]["status"] == "passed"
    assert payload["graph_publication_audit"]["excluded_nodes"] == 1
    assert pl.read_parquet(release / "data/public_graph_nodes.parquet").height == 2
    assert "SAMPLE:private" not in (release / "checksums.sha256").read_text(encoding="utf-8")
    assert all(len(resource["sha256"]) == 64 for resource in payload["resources"])
    assert (release / "manifest.json").exists()
    assert (release / "datapackage.json").exists()
    assert (release / "README.md").exists()


def test_build_fair_release_fails_on_identifier_column(tmp_path: Path) -> None:
    gold = tmp_path / "gold"
    gold.mkdir()
    pl.DataFrame({"sample_id": ["TCGA-01-0001-01A"], "score": [1.0]}).write_parquet(
        gold / "unsafe.parquet"
    )

    with pytest.raises(RuntimeError, match="forbidden identifier columns"):
        build_fair_release(
            "0.1.0",
            gold_dir=gold,
            output_root=tmp_path / "releases",
            required_files=("unsafe.parquet",),
        )
    assert not (tmp_path / "releases/v0.1.0").exists()


def test_build_fair_release_fails_on_identifier_value(tmp_path: Path) -> None:
    gold = tmp_path / "gold"
    gold.mkdir()
    pl.DataFrame({"entity": ["PATIENT:private"], "score": [1.0]}).write_parquet(
        gold / "unsafe.parquet"
    )

    with pytest.raises(RuntimeError, match="individual-like values"):
        build_fair_release(
            "0.1.0",
            gold_dir=gold,
            output_root=tmp_path / "releases",
            required_files=("unsafe.parquet",),
        )


def test_build_fair_release_requires_semver_and_complete_inputs(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="semantic versioning"):
        build_fair_release("draft", gold_dir=tmp_path)
    with pytest.raises(RuntimeError, match="missing required gold resources"):
        build_fair_release(
            "0.1.0", gold_dir=tmp_path, required_files=("missing.parquet",)
        )


def test_strict_fair_release_requires_graph_resources(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    gold = tmp_path / "gold"
    gold.mkdir()
    pl.DataFrame({"count": [1]}).write_parquet(gold / "aggregate.parquet")
    monkeypatch.setattr(
        "src.operations.fair_release.PUBLIC_AGGREGATE_FILES", ("aggregate.parquet",)
    )

    with pytest.raises(RuntimeError, match="requires both gold graph"):
        build_fair_release("0.1.0", gold_dir=gold, output_root=tmp_path / "releases")
