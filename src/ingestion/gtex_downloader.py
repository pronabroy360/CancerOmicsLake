from __future__ import annotations

from src.common.config import AppConfig


def gtex_metadata_stub(config: AppConfig) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for tissue in config.gtex.tissues:
        rows.append(
            {
                "gtex_sample_id": f"GTEX-{tissue[:3].upper()}-0001",
                "donor_id": "OPEN-ACCESS",
                "tissue_site": tissue,
                "tissue_detail": tissue,
                "gene_id": "ENSG00000141510",
                "gene_symbol": "TP53",
                "expression_value": "0.0",
                "expression_unit": "TPM",
                "source_version": config.gtex.version,
            }
        )
    return rows
