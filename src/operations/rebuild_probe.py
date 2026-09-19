from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import polars as pl


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _one_row(frame: pl.DataFrame, description: str) -> dict[str, Any]:
    if frame.height != 1:
        raise RuntimeError(f"Rebuild probe requires exactly one {description} row")
    return frame.row(0, named=True)


def build_rebuild_probe(root_dir: str | Path = ".") -> dict[str, Any]:
    root = Path(root_dir).resolve()
    gold = root / "data/gold"
    inputs = {
        "cohort": gold / "gold_cohort_summary.parquet",
        "expression": gold / "gold_tumor_vs_normal_expression.parquet",
        "mutation": gold / "gold_mutation_frequency_by_gene.parquet",
    }
    missing = [str(path) for path in inputs.values() if not path.exists()]
    if missing:
        raise FileNotFoundError(f"Rebuild probe inputs are missing: {missing}")

    cohort = _one_row(pl.read_parquet(inputs["cohort"]), "cohort summary")
    expression = _one_row(
        pl.read_parquet(inputs["expression"]).filter(
            (pl.col("cancer_type") == "TCGA-BRCA")
            & (pl.col("gene_symbol") == "TP53")
        ),
        "BRCA TP53 expression",
    )
    mutation = _one_row(
        pl.read_parquet(inputs["mutation"]).filter(
            (pl.col("cancer_type") == "TCGA-LUAD")
            & (pl.col("gene_symbol") == "TP53")
        ),
        "LUAD TP53 mutation",
    )
    return {
        "schema_version": "1.0",
        "input_sha256": {
            name: _sha256(path) for name, path in sorted(inputs.items())
        },
        "reconstructed_results": {
            "cohort_summary": cohort,
            "brca_tp53_expression": expression,
            "luad_tp53_mutation": mutation,
        },
    }


def write_rebuild_probe(payload: dict[str, Any], output_path: str | Path) -> Path:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(
        payload,
        default=str,
        indent=2,
        sort_keys=True,
    ) + "\n"
    temporary = output.with_suffix(f"{output.suffix}.tmp")
    temporary.write_text(encoded, encoding="utf-8")
    temporary.replace(output)
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a deterministic comparative-evaluation probe")
    parser.add_argument("--root", default=".")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    write_rebuild_probe(build_rebuild_probe(args.root), args.output)


if __name__ == "__main__":
    main()
