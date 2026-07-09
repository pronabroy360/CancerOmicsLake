from pathlib import Path

import yaml


def test_dbt_profile_duckdb_path_is_repo_relative() -> None:
    profile = yaml.safe_load(Path("dbt/profiles.yml").read_text(encoding="utf-8"))
    path = profile["canceromicslake"]["outputs"]["dev"]["path"]

    assert path == "outputs/canceromicslake.duckdb"
    assert not path.startswith("../")
    assert not path.startswith("/")
