"""Pure, unit-safe diagnostics for the frozen matched-processing follow-up."""
from __future__ import annotations

import numpy as np
from scipy.stats import kendalltau

from src.analytics.controlled_reference_study import rank_biserial


def informative_genes(matrices: dict[str, tuple[np.ndarray, np.ndarray]],
                      prevalence: float) -> np.ndarray:
    """Detection must clear the threshold in every group in both pipelines."""
    first = next(iter(matrices.values()))[0]
    keep = np.ones(first.shape[0], dtype=bool)
    for tumor, normal in matrices.values():
        keep &= (tumor > 0).mean(axis=1) >= prevalence
        keep &= (normal > 0).mean(axis=1) >= prevalence
    return keep


def concordance(native: np.ndarray, recount: np.ndarray, threshold: float) -> dict:
    if native.shape != recount.shape or not np.isfinite(native).all() or not np.isfinite(recount).all():
        raise ValueError("Effect arrays must be finite and share a gene universe")
    tau = kendalltau(native, recount, variant="b").statistic if native.size >= 2 else np.nan
    selected = (np.abs(native) >= threshold) & (np.abs(recount) >= threshold)
    n = int(selected.sum())
    return {"kendall_tau_b": float(tau) if np.isfinite(tau) else None,
            "direction_denominator": n,
            "direction_agreement": float((np.sign(native[selected]) ==
                                          np.sign(recount[selected])).mean()) if n else None}


def effect_distribution(values: np.ndarray) -> dict:
    return {"zero_effect_genes": int((values == 0).sum()),
            "saturated_effect_genes": int(np.isclose(np.abs(values), 1., atol=1e-12).sum()),
            "median_absolute_effect": float(np.median(np.abs(values))),
            "q25_absolute_effect": float(np.quantile(np.abs(values), .25)),
            "q75_absolute_effect": float(np.quantile(np.abs(values), .75))}


def _top_tie_sets(genes: np.ndarray, effects: np.ndarray, k: int) -> tuple[set[str], np.ndarray, int, int]:
    if k > genes.size or k < 1:
        raise ValueError("Top-k exceeds eligible gene universe")
    scores = np.abs(effects)
    boundary = np.partition(scores, -k)[-k]
    forced = set(genes[scores > boundary].tolist())
    tied = np.asarray(sorted(genes[scores == boundary].tolist()))
    return forced, tied, k - len(forced), int(tied.size)


def tie_overlap(genes: np.ndarray, native: np.ndarray, recount: np.ndarray,
                k: int, draws: int, rng: np.random.Generator) -> dict:
    if draws < 1:
        raise ValueError("At least one tie draw is required")
    left, left_tied, left_slots, left_count = _top_tie_sets(genes, native, k)
    right, right_tied, right_slots, right_count = _top_tie_sets(genes, recount, k)
    values = np.empty(draws, dtype=float)
    for i in range(draws):
        a = left | set(rng.choice(left_tied, left_slots, replace=False).tolist())
        b = right | set(rng.choice(right_tied, right_slots, replace=False).tolist())
        values[i] = len(a & b) / len(a | b)
    # This exact-ID rule reproduces v1's deterministic top-k choice.
    a = left | set(left_tied[:left_slots].tolist())
    b = right | set(right_tied[:right_slots].tolist())
    return {"deterministic_jaccard": len(a & b) / len(a | b),
            "tie_mean_jaccard": float(values.mean()),
            "tie_q025_jaccard": float(np.quantile(values, .025)),
            "tie_q975_jaccard": float(np.quantile(values, .975)),
            "native_boundary_ties": left_count, "recount_boundary_ties": right_count,
            "native_boundary_slots": left_slots, "recount_boundary_slots": right_slots}


def bootstrap_indices(unit_ids: list[str], rng: np.random.Generator) -> np.ndarray:
    groups: dict[str, list[int]] = {}
    for i, unit in enumerate(unit_ids):
        groups.setdefault(unit, []).append(i)
    ordered = sorted(groups)
    picked = rng.integers(0, len(ordered), len(ordered))
    return np.concatenate([groups[ordered[i]] for i in picked]).astype(np.int32)


def chunked_effects(tumor: np.ndarray, normal: np.ndarray,
                    tumor_indices: np.ndarray, normal_indices: np.ndarray,
                    chunk_size: int) -> np.ndarray:
    if chunk_size < 1:
        raise ValueError("Gene chunk size must be positive")
    result = np.empty(tumor.shape[0], dtype=np.float64)
    for start in range(0, tumor.shape[0], chunk_size):
        stop = min(start + chunk_size, tumor.shape[0])
        result[start:stop] = rank_biserial(tumor[start:stop, tumor_indices],
                                            normal[start:stop, normal_indices])
    return result
