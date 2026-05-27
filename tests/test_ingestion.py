from src.common.config import load_config
from src.ingestion.gdc_client import query_tcga_metadata_stub


def test_tcga_stub_metadata_has_open_access() -> None:
    config = load_config("configs/project_config.yml")
    rows = query_tcga_metadata_stub(config)
    assert rows
    assert all(row.access == "open" for row in rows)
