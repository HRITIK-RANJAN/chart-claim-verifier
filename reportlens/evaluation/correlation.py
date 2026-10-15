"""Do the tools make different mistakes? (RQ4 / E4)

From per-point signed errors on the calibration charts:
  * Pearson correlation of errors for every pair of tools
  * joint failure: how often two tools are BOTH off by more than `big` of the
    axis span, compared with what independence would predict
  * average correlation and the "effective number of independent tools",
    K / (1 + (K-1) * mean correlation)
"""
from __future__ import annotations

import itertools

import numpy as np


def error_correlation(errors: list[dict], tools: list[str], big: float = 0.02) -> dict:
    pairs = {}
    for a, b in itertools.combinations(tools, 2):
        rows = [(e[a], e[b]) for e in errors if a in e and b in e]
        if len(rows) < 10:
            continue
        x, y = np.array(rows).T
        r = float(np.corrcoef(x, y)[0, 1]) if x.std() > 0 and y.std() > 0 else float("nan")
        fa, fb = np.abs(x) > big, np.abs(y) > big
        joint = float((fa & fb).mean())
        indep = float(fa.mean() * fb.mean())
        pairs[f"{a}~{b}"] = {"n": len(rows), "corr": r, "both_big_error": joint,
                             "if_independent": indep, "ratio": joint / indep if indep > 0 else float("nan")}
    corrs = [p["corr"] for p in pairs.values() if p["corr"] == p["corr"]]
    k = len(tools)
    mean_r = float(np.mean(corrs)) if corrs else float("nan")
    return {"pairs": pairs, "mean_corr": mean_r,
            "effective_tools": k / (1 + (k - 1) * mean_r) if corrs and mean_r > -1 / (k - 1) else float("nan")}
