"""Calibration tables: sorted error/disagreement ratios per group (implementation.md §8.3).

Groups are keyed "chart_type|claim_type|k<number of readings>". A lookup that
hits a group with too few ratios falls back to a coarser group:

    line|difference|k3  ->  line|*|k3  ->  *|*|k3  ->  *|*|*
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from .pvalues import conformal_cutoff, p_value


def group_key(chart_type: str, claim_type: str, k: int | str) -> str:
    return f"{chart_type}|{claim_type}|k{k}" if k != "*" else f"{chart_type}|{claim_type}|*"


def fallback_chain(chart_type: str, claim_type: str, k: int) -> list[str]:
    return [
        group_key(chart_type, claim_type, k),
        group_key(chart_type, "*", k),
        group_key("*", "*", k),
        "*|*|*",
    ]


@dataclass
class CalibrationTable:
    groups: dict[str, list[float]]              # key -> ratios sorted ascending
    min_group_size: int = 200
    meta: dict = field(default_factory=dict)    # tools, model versions, eps, order, ...

    def lookup(self, chart_type: str, claim_type: str, k: int) -> tuple[str, list[float]]:
        for key in fallback_chain(chart_type, claim_type, k):
            ratios = self.groups.get(key)
            if ratios and len(ratios) >= self.min_group_size:
                return key, ratios
        key = "*|*|*"
        return key, self.groups.get(key, [])

    def cutoff(self, chart_type: str, claim_type: str, k: int, level: float) -> tuple[str, float]:
        key, ratios = self.lookup(chart_type, claim_type, k)
        return key, conformal_cutoff(ratios, level)

    def p_value(self, chart_type: str, claim_type: str, k: int, score: float) -> float:
        _, ratios = self.lookup(chart_type, claim_type, k)
        return p_value(score, ratios)

    # -- persistence -------------------------------------------------------
    def save(self, path: str | Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"meta": self.meta, "min_group_size": self.min_group_size,
                                    "groups": self.groups}))

    @classmethod
    def load(cls, path: str | Path) -> "CalibrationTable":
        d = json.loads(Path(path).read_text())
        return cls(groups={k: sorted(v) for k, v in d["groups"].items()},
                   min_group_size=d.get("min_group_size", 200), meta=d.get("meta", {}))

    def summary(self) -> dict[str, dict]:
        out = {}
        for key, r in sorted(self.groups.items()):
            out[key] = {"n": len(r), "q75": conformal_cutoff(r, 0.75), "q95": conformal_cutoff(r, 0.95)}
        return out


class ConstantTable(CalibrationTable):
    """Baseline B5 ("uncalibrated margin"): margin = raw disagreement x fixed factor.

    No calibration data, so no p-values; the batch check is skipped for B5.
    """

    def __init__(self, factor_flag: float = 1.0, factor_accept: float = 0.5):
        super().__init__(groups={}, min_group_size=0, meta={"constant": True})
        self.factors = {"flag": factor_flag, "accept": factor_accept}

    def cutoff(self, chart_type, claim_type, k, level):
        return "constant", self.factors["flag"] if level >= 0.9 else self.factors["accept"]

    def p_value(self, chart_type, claim_type, k, score):
        return float("nan")
