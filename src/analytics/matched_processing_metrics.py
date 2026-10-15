"""Unit-safe descriptive metrics for native versus recount3 matched specimens."""
from __future__ import annotations

from pathlib import Path
import xml.sax.saxutils as xml

import numpy as np
import polars as pl
from scipy.stats import spearmanr

from src.analytics.controlled_reference_study import rank_biserial


def _spearman(left: np.ndarray, right: np.ndarray) -> float | None:
    if left.size < 3 or np.ptp(left) == 0 or np.ptp(right) == 0:
        return None
    value = float(spearmanr(left, right).statistic)
    return value if np.isfinite(value) else None


def _top_ids(genes: np.ndarray, values: np.ndarray, k: int) -> set[str]:
    order = np.lexsort((genes, -values))[:k]
    return set(genes[order].tolist())


def specimen_metrics(frame: pl.DataFrame, native_gene_count: int, recount_gene_count: int,
                     minimum_common_genes: int) -> dict:
    if frame.select("gene_id").is_duplicated().any():
        raise ValueError("Duplicate gene in a matched specimen")
    if frame.height < minimum_common_genes:
        raise ValueError("Too few common genes for specimen-level processing comparison")
    genes = frame["gene_id"].to_numpy()
    native, recount = frame["native_value"].to_numpy(), frame["recount_value"].to_numpy()
    if not np.isfinite(native).all() or not np.isfinite(recount).all():
        raise ValueError("Nonfinite expression value in matched processing comparison")
    if (native < 0).any() or (recount < 0).any():
        raise ValueError("Negative expression value in matched processing comparison")
    both = (native > 0) & (recount > 0)
    k = min(100, frame.height)
    left_top, right_top = _top_ids(genes, native, k), _top_ids(genes, recount, k)
    return {"common_gene_count": frame.height, "native_gene_count": native_gene_count,
            "recount_gene_count": recount_gene_count, "jointly_detected_gene_count": int(both.sum()),
            "spearman_all_common": _spearman(native, recount),
            "spearman_jointly_detected": _spearman(native[both], recount[both]),
            "top100_jaccard": len(left_top & right_top) / len(left_top | right_top)}


def paired_expression(manifest: pl.DataFrame, native_path: Path, recount_path: Path,
                      source: str) -> pl.DataFrame:
    native_col = "sample_id" if source == "TCGA" else "gtex_sample_id"
    native_ids, recount_ids = (manifest["native_sample_id"].to_list(),
                               manifest["recount_sample_id"].to_list())
    native = (pl.scan_parquet(native_path).filter(pl.col(native_col).is_in(native_ids))
              .select(pl.col(native_col).alias("native_sample_id"), "gene_id",
                      pl.col("expression_value").alias("native_value")).collect())
    recount = (pl.scan_parquet(recount_path).filter((pl.col("source") == source) &
                                                  pl.col("sample_id").is_in(recount_ids))
               .select(pl.col("sample_id").alias("recount_sample_id"), "gene_id",
                       pl.col("expression_value").alias("recount_value")).collect())
    if native["native_sample_id"].n_unique() != manifest.height or recount["recount_sample_id"].n_unique() != manifest.height:
        raise ValueError("Matched specimen missing from a pipeline expression table")
    if native.select("native_sample_id", "gene_id").is_duplicated().any():
        raise ValueError("Duplicate native specimen-gene measurement")
    if recount.select("recount_sample_id", "gene_id").is_duplicated().any():
        raise ValueError("Duplicate recount3 specimen-gene measurement")
    joined = (manifest.select("native_sample_id", "recount_sample_id")
              .join(native, on="native_sample_id", how="inner")
              .join(recount, on=["recount_sample_id", "gene_id"], how="inner"))
    counts_native = native.group_by("native_sample_id").len().rename({"len": "native_gene_count"})
    counts_recount = recount.group_by("recount_sample_id").len().rename({"len": "recount_gene_count"})
    return (joined.join(counts_native, on="native_sample_id")
            .join(counts_recount, on="recount_sample_id"))


def _bootstrap_median(values: np.ndarray, units: list[str], repeats: int,
                      seed: int) -> tuple[float, float]:
    groups = {}
    for value, unit in zip(values, units, strict=True):
        groups.setdefault(unit, []).append(value)
    ordered = sorted(groups)
    rng = np.random.default_rng(seed)
    medians = []
    for _ in range(repeats):
        sample = rng.choice(ordered, size=len(ordered), replace=True)
        medians.append(float(np.median([v for unit in sample for v in groups[unit]])))
    low, high = np.quantile(medians, [0.025, 0.975])
    return float(low), float(high)


def summarize_specimens(private_metrics: pl.DataFrame, bootstrap_repeats: int, seed: int) -> pl.DataFrame:
    rows = []
    for index, block in enumerate(private_metrics.partition_by("source", "cohort", "tissue_site", maintain_order=True)):
        row = {key: block[key][0] for key in ("source", "cohort", "tissue_site")}
        row.update({"matched_specimens": block.height, "biological_units": block["unit_id"].n_unique(),
                    "median_common_genes": float(block["common_gene_count"].median())})
        for metric in ("spearman_all_common", "spearman_jointly_detected", "top100_jaccard"):
            valid = block.filter(pl.col(metric).is_not_null())
            values = valid[metric].to_numpy()
            row[f"{metric}_median"] = float(np.median(values)) if len(values) else None
            row[f"{metric}_q25"] = float(np.quantile(values, .25)) if len(values) else None
            row[f"{metric}_q75"] = float(np.quantile(values, .75)) if len(values) else None
            low, high = (_bootstrap_median(values, valid["unit_id"].to_list(),
                                           bootstrap_repeats, seed + index * 11)
                         if len(values) else (None, None))
            row[f"{metric}_ci_low"], row[f"{metric}_ci_high"] = low, high
        rows.append(row)
    return pl.DataFrame(rows).sort("source", "cohort", "tissue_site")


def _effect_matrix(frame: pl.DataFrame, sample_ids: list[str], field: str,
                   genes: list[str]) -> np.ndarray:
    pivot = frame.select("gene_id", "recount_sample_id", field).pivot(
        index="gene_id", on="recount_sample_id", values=field)
    ordered = pl.DataFrame({"gene_id": genes}).join(pivot, on="gene_id", how="left")
    array = ordered.select(sample_ids).to_numpy()
    if not np.isfinite(array).all():
        raise ValueError("Incomplete matched gene universe for effect comparison")
    return array


def effect_rank_rows(tumor: pl.DataFrame, normal: pl.DataFrame, cancer: str,
                     tissue: str, top_ks: tuple[int, ...], minimum_common_genes: int) -> list[dict]:
    all_pairs = pl.concat([tumor, normal], how="vertical")
    n_tumor, n_normal = tumor["recount_sample_id"].n_unique(), normal["recount_sample_id"].n_unique()
    all_n = n_tumor + n_normal
    genes = (all_pairs.group_by("gene_id").agg(pl.col("recount_sample_id").n_unique().alias("n"))
             .filter(pl.col("n") == all_n).sort("gene_id")["gene_id"].to_list())
    if len(genes) < max(minimum_common_genes, max(top_ks)):
        raise ValueError(f"Too few complete genes in matched {cancer} effect comparison")
    tumor_ids = sorted(tumor["recount_sample_id"].unique().to_list())
    normal_ids = sorted(normal["recount_sample_id"].unique().to_list())
    values = {}
    for field in ("native_value", "recount_value"):
        t = _effect_matrix(tumor, tumor_ids, field, genes)
        n = _effect_matrix(normal, normal_ids, field, genes)
        values[field] = rank_biserial(t, n)
    symbols = np.asarray(genes)
    native_score, recount_score = np.abs(values["native_value"]), np.abs(values["recount_value"])
    rows = []
    for k in top_ks:
        a, b = _top_ids(symbols, native_score, k), _top_ids(symbols, recount_score, k)
        shared = a & b
        index = {g: i for i, g in enumerate(genes)}
        direction = (sum(np.sign(values["native_value"][index[g]]) ==
                         np.sign(values["recount_value"][index[g]]) for g in shared) / len(shared)
                     if shared else None)
        rows.append({"cancer_type": cancer, "normal_tissue": tissue,
                     "matched_tumor_specimens": n_tumor, "matched_normal_specimens": n_normal,
                     "complete_common_genes": len(genes), "top_k": k,
                     "top_k_jaccard": len(shared) / len(a | b), "shared_top_genes": len(shared),
                     "direction_agreement_shared_top": direction,
                     "native_boundary_tie_count": int((native_score == np.sort(native_score)[-k]).sum()),
                     "recount_boundary_tie_count": int((recount_score == np.sort(recount_score)[-k]).sum())})
    return rows


def write_summary_figure(summary: pl.DataFrame, destination: Path) -> None:
    width, height = 1000, 100 + 58 * summary.height
    content = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
               '<rect width="100%" height="100%" fill="#f7f7f2"/>',
               '<text x="32" y="38" font-family="sans-serif" font-size="20" fill="#173329">Matched specimen rank agreement</text>',
               '<text x="32" y="61" font-family="sans-serif" font-size="12" fill="#52635a">Spearman median and paired unit bootstrap 95% interval; descriptive</text>']
    for i, row in enumerate(summary.iter_rows(named=True)):
        y = 98 + i * 58
        label = f"{row['source']} {row['cohort']} {row['tissue_site']} (n={row['matched_specimens']})"
        x0, x1 = 450, 950
        low, high, median = (row[f"spearman_all_common_{name}"] for name in ("ci_low", "ci_high", "median"))
        if median is None:
            continue
        to_x = lambda value: x0 + (float(value) + 1) * (x1 - x0) / 2
        content += [f'<text x="32" y="{y + 5}" font-family="sans-serif" font-size="13" fill="#173329">{xml.escape(label)}</text>',
                    f'<line x1="{x0}" x2="{x1}" y1="{y}" y2="{y}" stroke="#cad7cd"/>',
                    f'<line x1="{to_x(low):.1f}" x2="{to_x(high):.1f}" y1="{y}" y2="{y}" stroke="#197e71" stroke-width="5"/>',
                    f'<circle cx="{to_x(median):.1f}" cy="{y}" r="7" fill="#e96d3a"/>']
    content.append('</svg>')
    destination.write_text("\n".join(content) + "\n", encoding="utf-8")


def write_effect_figure(effects: pl.DataFrame, destination: Path) -> None:
    chosen = effects.filter(pl.col("top_k") == 50).sort("cancer_type")
    content = ['<svg xmlns="http://www.w3.org/2000/svg" width="800" height="320" viewBox="0 0 800 320">',
               '<rect width="100%" height="100%" fill="#f7f7f2"/>',
               '<text x="32" y="38" font-family="sans-serif" font-size="20" fill="#173329">Top-50 effect-rank overlap</text>',
               '<text x="32" y="61" font-family="sans-serif" font-size="12" fill="#52635a">Same specimens in both pipelines; native TPM versus recount3 coverage</text>']
    for i, row in enumerate(chosen.iter_rows(named=True)):
        y = 110 + i * 68
        content += [f'<text x="32" y="{y + 18}" font-family="sans-serif" font-size="14">{xml.escape(row["cancer_type"])}</text>',
                    f'<rect x="190" y="{y}" width="500" height="23" fill="#cad7cd"/>',
                    f'<rect x="190" y="{y}" width="{500 * row["top_k_jaccard"]:.1f}" height="23" fill="#197e71"/>',
                    f'<text x="705" y="{y + 18}" font-family="sans-serif" font-size="14">{row["top_k_jaccard"]:.3f}</text>']
    content.append('</svg>')
    destination.write_text("\n".join(content) + "\n", encoding="utf-8")
