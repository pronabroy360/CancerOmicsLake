from src.common.config import load_config


def test_load_config_public_mode() -> None:
    config = load_config("configs/project_config.yml")
    assert config.project.name == "CancerOmicsLake"
    assert config.project.mode == "open_access"
    assert config.tcga.projects == ["TCGA-BRCA", "TCGA-LUAD", "TCGA-COAD"]
