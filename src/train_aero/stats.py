"""Aggregation rules used in the report.  Pure Python, no framework dependency.

Integrated quantities: the benchmark engine reports |pred - true| / |true|, which explodes
where the truth crosses zero (side force and roll moment at yaw 0).  Side force, lift and
roll moment are therefore reported as |pred - true| / span, span = max - min of the TRUTH
over the yaw sweep of the same geometry.  Drag never approaches zero and keeps the engine's
relative error.
"""
from __future__ import annotations

import math
import statistics as st
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence

SIGN_MIN_FRACTION_OF_SPAN = 0.1   # sign agreement only counted where |truth| > 10 % of span


def group_by_geometry(rows: Iterable[Mapping]) -> dict[str, list[Mapping]]:
    groups: dict[str, list[Mapping]] = defaultdict(list)
    for r in rows:
        groups[r["case_id"].rsplit("_yaw", 1)[0]].append(r["metrics"])
    return groups


def error_over_span(rows: Sequence[Mapping], metric: str) -> tuple[float, float]:
    """(mean |pred - true| / span, sign-agreement rate) of `<metric>_pred/_true` over cases."""
    errs: list[float] = []
    sign: list[bool] = []
    for g in group_by_geometry(rows).values():
        truth = [x[f"{metric}_true"] for x in g]
        span = max(truth) - min(truth)
        errs += [abs(x[f"{metric}_pred"] - x[f"{metric}_true"]) / span for x in g]
        sign += [x[f"{metric}_pred"] * x[f"{metric}_true"] > 0
                 for x in g if abs(x[f"{metric}_true"]) > SIGN_MIN_FRACTION_OF_SPAN * span]
    return st.mean(errs), (sum(sign) / len(sign) if sign else math.nan)


def paired_difference(a: Sequence[float], b: Sequence[float]) -> dict[str, float]:
    """Fold-paired comparison of model a against model b (positive = a worse)."""
    d = [x - y for x, y in zip(a, b, strict=True)]
    if len(d) < 2:
        raise ValueError("need at least two paired folds")
    sd = st.stdev(d)
    t = st.mean(d) / (sd / len(d) ** 0.5) if sd > 0 else math.nan
    return {"n": len(d), "mean": st.mean(d), "sd": sd, "t": t, "a_worse": sum(x > 0 for x in d)}
