from __future__ import annotations

import math


def with_log2_expression(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for row in rows:
        expr = float(row["expression_value"])
        row_copy = dict(row)
        row_copy["log2_expression"] = f"{math.log2(expr + 1.0):.6f}"
        out.append(row_copy)
    return out
