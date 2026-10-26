"""Conformal cut-offs, conformal p-values and Benjamini–Hochberg (implementation.md §8.2).

None of this is our contribution: it is standard machinery (Vovk et al. 2005;
Jin & Candès 2023; Benjamini & Hochberg 1995). What is ours is the calibrated
reading error we feed into it.
"""
from __future__ import annotations

import bisect
import math
from typing import Sequence


def conformal_cutoff(sorted_ratios: Sequence[float], level: float) -> float:
    """The ceil((n+1)*level)-th smallest ratio.

    The small adjustment over a plain percentile is what makes the cut-off hold
    on *new* charts (assuming they resemble the calibration charts).
    `sorted_ratios` must be sorted ascending.
    """
    n = len(sorted_ratios)
    k = math.ceil((n + 1) * level)
    if n == 0 or k > n:
        return float("inf")
    return float(sorted_ratios[k - 1])


def p_value(score: float, sorted_ratios: Sequence[float]) -> float:
    """(1 + #calibration ratios >= score) / (n + 1).

    `score` = how far the claim falls outside its allowed rounding, divided by
    the tools' disagreement (same scale as the calibration ratios).
    """
    n = len(sorted_ratios)
    at_least = n - bisect.bisect_left(sorted_ratios, score)
    return (1 + at_least) / (n + 1)


def benjamini_hochberg(pvals: Sequence[float], alpha: float = 0.10) -> set[int]:
    """Indices that are kept as discoveries (flags) at level alpha."""
    m = len(pvals)
    if m == 0:
        return set()
    order = sorted(range(m), key=lambda i: pvals[i])
    k = 0
    for rank, i in enumerate(order, start=1):
        if pvals[i] <= alpha * rank / m:
            k = rank
    return set(order[:k])
