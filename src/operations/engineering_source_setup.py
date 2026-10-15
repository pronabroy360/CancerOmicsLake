"""Fetch only the pinned software script required by the external integration check."""
from __future__ import annotations

import hashlib
from pathlib import Path
from urllib.request import urlopen

SOURCE_URL = "https://raw.githubusercontent.com/QuackenbushLab/tcga-data-nf/1069eb9c01b97640fd532ffac8551096d2a2790a/bin/r/prepare_expression_recount.R"
SOURCE_SHA256 = "ee052b647386a4d2769bef4b533504e08d0166ed844d6a3fbfd20a25390f6fdc"
TARGET = Path("data/research/engineering_sources/tcga-data-nf/prepare_expression_recount.R")


def install_source(target: Path = TARGET) -> None:
    if target.exists():
        if hashlib.sha256(target.read_bytes()).hexdigest() != SOURCE_SHA256:
            raise ValueError("Cached external software source drift; do not silently replace it")
        return
    with urlopen(SOURCE_URL, timeout=60) as response:
        content = response.read()
    if hashlib.sha256(content).hexdigest() != SOURCE_SHA256:
        raise ValueError("Downloaded external source does not match the pinned checksum")
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(".R.partial")
    temporary.write_bytes(content)
    temporary.replace(target)


if __name__ == "__main__":
    install_source()
    print("Pinned external software source verified; no biomedical data downloaded.")
