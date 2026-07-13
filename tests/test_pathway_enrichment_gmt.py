"""Regression coverage for the Reactome GMT fetch contract and the
pathway-enrichment analytics layer when run against an official-format
Reactome GMT (col1 = pathway name, col2 = R-HSA-XXXXX id, col3+ = genes).

These tests do not hit the network. They exercise:
  * the parser against the exact official Reactome GMT layout
  * pathway-size filtering (MIN_PATHWAY_SIZE / MAX_PATHWAY_SIZE)
  * per-cancer BH-FDR independence
  * the idempotent skip logic of the fetch script (when a valid GMT is
    already on disk, the script must not re-download)
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import zipfile
from pathlib import Path

import polars as pl
import pytest
from scipy.stats import hypergeom

from src.analytics.pathway_enrichment import (
    MAX_PATHWAY_SIZE,
    MIN_PATHWAY_SIZE,
    build_pathway_enrichment,
    load_gmt_pathways,
)


REPO_ROOT = Path(__file__).resolve().parent.parent
FETCH_SCRIPT = REPO_ROOT / "scripts" / "fetch_reactome_gmt.sh"


def _write_official_reactome_gmt(path: Path) -> None:
    """Five-line synthetic GMT in the EXACT official Reactome layout:
        col1 = pathway name (human readable)
        col2 = R-HSA-XXXXX stable id
        col3+ = HGNC gene symbols
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                # 5 genes: passes MIN_PATHWAY_SIZE filter
                "Cell Cycle\tR-HSA-1640170\tTP53\tCDK1\tCCNB1\tMDM2\tCDKN1A",
                # 6 genes: passes filter; partially overlaps Cell Cycle
                "DNA Repair\tR-HSA-73854\tTP53\tBRCA1\tBRCA2\tXRCC1\tPARP1\tLIG3",
                # 3 genes: below MIN_PATHWAY_SIZE -> must be filtered out
                "Tiny Pathway\tR-HSA-9999991\tTP53\tCDK1\tCCNB1",
                # 501 genes from the BACKGROUND (BIGGENE1..BIGGENE501) so the
                # post-intersection size exceeds MAX_PATHWAY_SIZE (500) and the
                # pathway is excluded. (If we used non-background genes, the
                # post-intersection size would be 0 and the filter would be
                # trivially bypassed.)
                "Huge Pathway\tR-HSA-9999992\t" + "\t".join(f"BIGGENE{i}" for i in range(1, 502)),
                # 5 genes: passes filter, no overlap with candidates
                "Unrelated Pathway\tR-HSA-9999993\tZZZ1\tZZZ2\tZZZ3\tZZZ4\tZZZ5",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def _write_cached_provenance(gmt_path: Path, release: str = "97") -> None:
    payload = {
        "status": "downloaded",
        "source": "Reactome",
        "source_version": release,
        "gmt_sha256": hashlib.sha256(gmt_path.read_bytes()).hexdigest(),
        "archive_sha256": "synthetic-archive-checksum",
        "retrieved_at": "2026-07-14T00:00:00+00:00",
    }
    gmt_path.with_name("reactome_pathways.provenance.json").write_text(
        json.dumps(payload), encoding="utf-8"
    )


def _write_consensus_two_cancers(path: Path) -> None:
    """Consensus mart with two cancer types so per-cancer FDR can be tested.
    BRCA also carries 510 BIGGENE* symbols so the Huge Pathway's effective
    (post-intersection) size = 501, exercising MAX_PATHWAY_SIZE.
    """
    rows = []
    # TCGA-BRCA: 10 GENE* + 510 BIGGENE* + 10 real gene symbols.
    for i in range(1, 11):
        rows.append(
            {
                "cancer_type": "TCGA-BRCA",
                "gene_symbol": f"GENE{i}",
                "consensus_decision": "prioritized" if i <= 4 else "deprioritized",
                "publication_tier": "research_candidate" if i <= 3 else "exploratory",
            }
        )
    for i in range(1, 511):
        rows.append(
            {
                "cancer_type": "TCGA-BRCA",
                "gene_symbol": f"BIGGENE{i}",
                "consensus_decision": "deprioritized",
                "publication_tier": "exploratory",
            }
        )
    for gene in ["TP53", "CDK1", "CCNB1", "MDM2", "CDKN1A", "BRCA1", "BRCA2", "XRCC1", "PARP1", "LIG3"]:
        rows.append(
            {
                "cancer_type": "TCGA-BRCA",
                "gene_symbol": gene,
                "consensus_decision": "prioritized",
                "publication_tier": "research_candidate",
            }
        )
    # TCGA-LUAD: one valid pathway family, allowing an independent FDR check.
    luad_genes = ["TP53", "BRCA1", "BRCA2", "XRCC1", "PARP1"] + [
        f"LUAD{i}" for i in range(6, 11)
    ]
    for i, gene in enumerate(luad_genes, start=1):
        rows.append(
            {
                "cancer_type": "TCGA-LUAD",
                "gene_symbol": gene,
                "consensus_decision": "prioritized" if i <= 4 else "deprioritized",
                "publication_tier": "research_candidate" if i <= 2 else "exploratory",
            }
        )
    pl.DataFrame(rows).write_parquet(path)


# ---------------------------------------------------------------------------
# Parser tests against the official Reactome GMT layout
# ---------------------------------------------------------------------------


def test_load_gmt_pathways_handles_official_reactome_layout(tmp_path: Path) -> None:
    """The official Reactome GMT places the R-HSA-* id in column 2 (not col 1).
    The parser must still extract the correct id and keep col1 as pathway_name.
    """
    gmt = tmp_path / "reactome_pathways.gmt"
    _write_official_reactome_gmt(gmt)

    pathways = load_gmt_pathways(gmt, source="Reactome")

    assert len(pathways) == 5
    by_id = {p["pathway_id"]: p for p in pathways}

    # The R-HSA-* id must come from column 2.
    assert "R-HSA-1640170" in by_id
    assert "R-HSA-73854" in by_id
    assert "R-HSA-9999991" in by_id  # tiny pathway is still parsed (filtered later)
    assert "R-HSA-9999992" in by_id  # huge pathway is still parsed (filtered later)
    assert "R-HSA-9999993" in by_id

    # The human-readable name must come from column 1, not the id.
    assert by_id["R-HSA-1640170"]["pathway_name"] == "Cell Cycle"
    assert by_id["R-HSA-73854"]["pathway_name"] == "DNA Repair"
    assert by_id["R-HSA-9999993"]["pathway_name"] == "Unrelated Pathway"

    # Gene sets must be uppercased, deduped, and sorted.
    assert by_id["R-HSA-1640170"]["genes"] == ["CCNB1", "CDK1", "CDKN1A", "MDM2", "TP53"]
    assert by_id["R-HSA-73854"]["genes"] == [
        "BRCA1",
        "BRCA2",
        "LIG3",
        "PARP1",
        "TP53",
        "XRCC1",
    ]
    assert by_id["R-HSA-1640170"]["pathway_source"] == "Reactome"


# ---------------------------------------------------------------------------
# Pathway-size filtering tests
# ---------------------------------------------------------------------------


def test_build_pathway_enrichment_filters_pathways_outside_size_window(
    tmp_path: Path,
) -> None:
    """Pathways smaller than MIN_PATHWAY_SIZE or larger than MAX_PATHWAY_SIZE
    must never appear in the enrichment output.
    """
    consensus = tmp_path / "consensus.parquet"
    gmt = tmp_path / "reactome_pathways.gmt"
    output = tmp_path / "pathway.parquet"
    _write_consensus_two_cancers(consensus)
    _write_official_reactome_gmt(gmt)

    summary = build_pathway_enrichment(
        consensus_path=consensus,
        pathway_gmt_path=gmt,
        output_path=output,
        report_path=tmp_path / "report.json",
        min_overlap=2,
        min_pathway_size=MIN_PATHWAY_SIZE,
        max_pathway_size=MAX_PATHWAY_SIZE,
    )

    assert summary["status"] == "completed"
    assert summary["pathway_count"] == 5  # parser sees all 5
    result = pl.read_parquet(output)

    # The tiny (3-gene) and huge (501-gene) pathways must be absent.
    assert "R-HSA-9999991" not in result.get_column("pathway_id").to_list()
    assert "R-HSA-9999992" not in result.get_column("pathway_id").to_list()
    # The two valid pathways (Cell Cycle, DNA Repair) must be present for BRCA.
    brca_ids = {
        row["pathway_id"]
        for row in result.filter(pl.col("cancer_type") == "TCGA-BRCA").to_dicts()
    }
    assert "R-HSA-1640170" in brca_ids
    assert "R-HSA-73854" in brca_ids


# ---------------------------------------------------------------------------
# Per-cancer FDR independence test
# ---------------------------------------------------------------------------


def test_build_pathway_enrichment_computes_fdr_independently_per_cancer(
    tmp_path: Path,
) -> None:
    """BH-FDR must be applied within each (cancer_type, candidate_set) group,
    not across the whole result set.
    """
    consensus = tmp_path / "consensus.parquet"
    gmt = tmp_path / "reactome_pathways.gmt"
    output = tmp_path / "pathway.parquet"
    _write_consensus_two_cancers(consensus)
    _write_official_reactome_gmt(gmt)

    build_pathway_enrichment(
        consensus_path=consensus,
        pathway_gmt_path=gmt,
        output_path=output,
        report_path=tmp_path / "report.json",
        min_overlap=2,
    )
    result = pl.read_parquet(output)

    def bh_reference(p_values: list[float]) -> list[float]:
        order = sorted(range(len(p_values)), key=p_values.__getitem__)
        adjusted = [1.0] * len(p_values)
        running = 1.0
        for rank_index in range(len(order) - 1, -1, -1):
            original_index = order[rank_index]
            rank = rank_index + 1
            running = min(running, p_values[original_index] * len(order) / rank)
            adjusted[original_index] = min(running, 1.0)
        return adjusted

    prioritized = result.filter(pl.col("candidate_set") == "prioritized").sort(
        ["cancer_type", "pathway_id"]
    )
    assert set(prioritized.get_column("cancer_type")) == {"TCGA-BRCA", "TCGA-LUAD"}

    for cancer_type in ("TCGA-BRCA", "TCGA-LUAD"):
        family = prioritized.filter(pl.col("cancer_type") == cancer_type)
        expected = bh_reference(family.get_column("p_value").to_list())
        assert family.get_column("fdr_q_value").to_list() == pytest.approx(expected)

    global_expected = bh_reference(prioritized.get_column("p_value").to_list())
    actual = prioritized.get_column("fdr_q_value").to_list()
    assert any(abs(observed - global_value) > 1e-12 for observed, global_value in zip(actual, global_expected))


# ---------------------------------------------------------------------------
# Hypergeometric p-value sanity check (one row, by hand)
# ---------------------------------------------------------------------------


def test_build_pathway_enrichment_hypergeometric_p_value_matches_reference(
    tmp_path: Path,
) -> None:
    """For one tiny controlled scenario, verify the reported p_value equals
    scipy.stats.hypergeom.sf(k-1, M, K, n) with the same definitions of
    background (M), pathway size (K), candidate size (n), and overlap (k)
    used by the analytics layer.
    """
    # Background: GENE1..GENE10 (10 genes), pathway has 5 of them,
    # candidates are 4 of them, overlap is 3.
    consensus = tmp_path / "consensus.parquet"
    gmt = tmp_path / "reactome_pathways.gmt"
    output = tmp_path / "pathway.parquet"
    rows = []
    for i in range(1, 11):
        rows.append(
            {
                "cancer_type": "TCGA-BRCA",
                "gene_symbol": f"GENE{i}",
                "consensus_decision": "prioritized" if i <= 4 else "deprioritized",
                "publication_tier": "research_candidate" if i <= 3 else "exploratory",
            }
        )
    pl.DataFrame(rows).write_parquet(consensus)
    gmt.write_text(
        "Cell Cycle\tR-HSA-1640170\tGENE1\tGENE2\tGENE3\tGENE5\tGENE6\n",
        encoding="utf-8",
    )
    gmt.parent.mkdir(parents=True, exist_ok=True)

    build_pathway_enrichment(
        consensus_path=consensus,
        pathway_gmt_path=gmt,
        output_path=output,
        report_path=tmp_path / "report.json",
        min_overlap=2,
    )
    result = pl.read_parquet(output)
    row = result.filter(
        (pl.col("candidate_set") == "prioritized") & (pl.col("pathway_id") == "R-HSA-1640170")
    ).to_dicts()[0]

    # M = background_size = 10, K = pathway_size (intersect background) = 5,
    # n = candidate_size = 4, k = overlap = 3 (GENE1, GENE2, GENE3).
    expected_p = float(hypergeom.sf(3 - 1, 10, 5, 4))
    assert abs(row["p_value"] - expected_p) < 1e-12
    assert row["overlap_gene_count"] == 3
    assert row["pathway_gene_count"] == 5
    assert row["candidate_gene_count"] == 4
    assert row["background_gene_count"] == 10


# ---------------------------------------------------------------------------
# Fetch script idempotency test (no network)
# ---------------------------------------------------------------------------


def test_fetch_reactome_gmt_script_is_idempotent_when_valid_file_exists(
    tmp_path: Path,
) -> None:
    """When a structurally-valid GMT is already on disk, the fetch script must
    exit 0 WITHOUT touching the network. We assert this by pointing the script
    at a fake data/ dir under tmp_path and confirming the file is unchanged.
    """
    # Set up an isolated CWD with the expected layout.
    cwd = tmp_path / "repo"
    cwd.mkdir()
    # Copy the script in so we exercise the actual file under version control.
    scripts_dir = cwd / "scripts"
    scripts_dir.mkdir()
    shutil.copy(FETCH_SCRIPT, scripts_dir / "fetch_reactome_gmt.sh")
    os.chmod(scripts_dir / "fetch_reactome_gmt.sh", 0o755)

    gmt_dir = cwd / "data" / "bronze" / "reference" / "pathways"
    gmt_dir.mkdir(parents=True)
    gmt_path = gmt_dir / "reactome_pathways.gmt"
    _write_official_reactome_gmt(gmt_path)
    _write_cached_provenance(gmt_path)
    original_mtime = gmt_path.stat().st_mtime_ns

    # Block any network call by replacing curl with a sentinel that fails.
    # If the script tries to invoke curl, the test fails.
    bin_dir = cwd / ".bin"
    bin_dir.mkdir()
    curl_stub = bin_dir / "curl"
    curl_stub.write_text(
        "#!/usr/bin/env bash\n"
        "echo 'curl should NOT have been called' >&2\n"
        "exit 99\n",
        encoding="utf-8",
    )
    os.chmod(curl_stub, 0o755)

    env = dict(os.environ)
    env["PATH"] = f"{bin_dir}:{env.get('PATH', '')}"
    env["REACTOME_MIN_PATHWAYS"] = "1"

    result = subprocess.run(
        ["bash", "scripts/fetch_reactome_gmt.sh"],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        timeout=20,
    )

    assert result.returncode == 0, result.stderr
    assert "validated cached release 97" in result.stdout
    # File must be untouched.
    assert gmt_path.stat().st_mtime_ns == original_mtime

    report = json.loads(
        (cwd / "outputs" / "reports" / "reactome_gmt_acquisition_report.json").read_text(
            encoding="utf-8"
        )
    )
    assert report["status"] == "cached"
    assert report["source_version"] == "97"
    assert report["license"] == "CC0-1.0"
    assert report["pathway_count"] == 5
    assert len(report["gmt_sha256"]) == 64


def test_fetch_reactome_gmt_script_respects_skip_env(tmp_path: Path) -> None:
    """SKIP_GMT_FETCH=1 must short-circuit the script before any work."""
    cwd = tmp_path / "repo"
    cwd.mkdir()
    scripts_dir = cwd / "scripts"
    scripts_dir.mkdir()
    shutil.copy(FETCH_SCRIPT, scripts_dir / "fetch_reactome_gmt.sh")
    os.chmod(scripts_dir / "fetch_reactome_gmt.sh", 0o755)

    env = dict(os.environ)
    env["SKIP_GMT_FETCH"] = "1"

    result = subprocess.run(
        ["bash", "scripts/fetch_reactome_gmt.sh"],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        timeout=20,
    )

    assert result.returncode == 0, result.stderr
    assert "SKIP_GMT_FETCH=1" in result.stdout
    # The data directory must not even have been created.
    assert not (cwd / "data" / "bronze" / "reference" / "pathways").exists()


def test_fetch_reactome_gmt_rejects_truncated_unversioned_cache(tmp_path: Path) -> None:
    cwd = tmp_path / "repo"
    scripts_dir = cwd / "scripts"
    scripts_dir.mkdir(parents=True)
    shutil.copy(FETCH_SCRIPT, scripts_dir / "fetch_reactome_gmt.sh")

    gmt_dir = cwd / "data" / "bronze" / "reference" / "pathways"
    gmt_dir.mkdir(parents=True)
    gmt_path = gmt_dir / "reactome_pathways.gmt"
    gmt_path.write_text("Cell Cycle\tR-HSA-1640170\tTP53\n", encoding="utf-8")

    bin_dir = cwd / ".bin"
    bin_dir.mkdir()
    curl_stub = bin_dir / "curl"
    curl_stub.write_text("#!/usr/bin/env bash\nexit 99\n", encoding="utf-8")
    os.chmod(curl_stub, 0o755)

    env = dict(os.environ)
    env["PATH"] = f"{bin_dir}:{env.get('PATH', '')}"
    env["REACTOME_MIN_PATHWAYS"] = "5"
    result = subprocess.run(
        ["bash", "scripts/fetch_reactome_gmt.sh"],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        timeout=20,
    )

    assert result.returncode != 0
    assert "no validated cached GMT" in result.stderr


def test_fetch_reactome_gmt_failed_refresh_preserves_valid_cache(tmp_path: Path) -> None:
    cwd = tmp_path / "repo"
    scripts_dir = cwd / "scripts"
    scripts_dir.mkdir(parents=True)
    shutil.copy(FETCH_SCRIPT, scripts_dir / "fetch_reactome_gmt.sh")

    gmt_dir = cwd / "data" / "bronze" / "reference" / "pathways"
    gmt_dir.mkdir(parents=True)
    gmt_path = gmt_dir / "reactome_pathways.gmt"
    _write_official_reactome_gmt(gmt_path)
    _write_cached_provenance(gmt_path)
    original = gmt_path.read_bytes()

    bad_archive = cwd / "invalid-reactome.zip"
    with zipfile.ZipFile(bad_archive, "w") as archive:
        archive.writestr("ReactomePathways.gmt", "Invalid\tNOT-A-REACTOME-ID\tTP53\n")

    bin_dir = cwd / ".bin"
    bin_dir.mkdir()
    curl_stub = bin_dir / "curl"
    curl_stub.write_text(
        "#!/usr/bin/env bash\n"
        "destination=''\n"
        "while [[ $# -gt 0 ]]; do\n"
        "  if [[ $1 == '-o' ]]; then destination=$2; shift 2; else shift; fi\n"
        "done\n"
        "cp \"$FAKE_REACTOME_ARCHIVE\" \"$destination\"\n",
        encoding="utf-8",
    )
    os.chmod(curl_stub, 0o755)

    env = dict(os.environ)
    env["PATH"] = f"{bin_dir}:{env.get('PATH', '')}"
    env["FAKE_REACTOME_ARCHIVE"] = str(bad_archive)
    env["REFRESH_GMT"] = "1"
    env["REACTOME_MIN_PATHWAYS"] = "1"
    result = subprocess.run(
        ["bash", "scripts/fetch_reactome_gmt.sh"],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        timeout=20,
    )

    assert result.returncode == 0, result.stderr
    assert gmt_path.read_bytes() == original
    report = json.loads(
        (cwd / "outputs" / "reports" / "reactome_gmt_acquisition_report.json").read_text(
            encoding="utf-8"
        )
    )
    assert report["status"] == "cached_fallback"
    assert report["detail"] == "downloaded GMT failed structural validation"
