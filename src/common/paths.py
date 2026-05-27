from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_ROOT / "data"
OUTPUTS_DIR = REPO_ROOT / "outputs"


def ensure_base_dirs() -> None:
    paths = [
        DATA_DIR / "bronze" / "tcga" / "metadata",
        DATA_DIR / "bronze" / "gtex",
        DATA_DIR / "silver",
        DATA_DIR / "gold",
        OUTPUTS_DIR / "reports",
        OUTPUTS_DIR / "graph_exports",
        OUTPUTS_DIR / "sample_queries",
    ]
    for path in paths:
        path.mkdir(parents=True, exist_ok=True)
