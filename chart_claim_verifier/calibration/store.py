"""Calibration tables: sorted error/disagreement ratios per group (implementation.md §8.3).

Groups are keyed "chart_type|claim_type|k<number of readings>", and, since U14, also
"chart_type|claim_type|<tool+tool>" for the exact set of tools that gave the readings.
A lookup that hits a group with too few ratios falls back to a coarser group:

    line|difference|ocr_pixel+deplot  ->  line|*|ocr_pixel+deplot  ->  *|*|ocr_pixel+deplot
        ->  line|difference|k2  ->  line|*|k2  ->  *|*|k2  ->  *|*|*

Why by tool set: the planner chooses WHICH tools to read, and two precise tools agree far more tightly than two
vision-language models; a margin learned from a mixture of pairs is too wide for the first and too narrow for the second.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from .pvalues import conformal_cutoff, p_value


def group_key(chart_type: str, claim_type: str, k: int | str) -> str:
    return f"{chart_type}|{claim_type}|k{k}" if k != "*" else f"{chart_type}|{claim_type}|*"


def tools_key(chart_type: str, claim_type: str, tools) -> str:
    return f"{chart_type}|{claim_type}|{'+'.join(sorted(tools))}"


def fallback_chain(chart_type: str, claim_type: str, k: int, tools=None) -> list[str]:
    by_tools = [tools_key(chart_type, claim_type, tools), tools_key(chart_type, "*", tools),
                tools_key("*", "*", tools)] if tools else []
    return by_tools + [
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
    charts: dict[str, int] = field(default_factory=dict)   # key -> distinct charts behind the group
    min_group_charts: int = 0                   # a group rests on its CHARTS, not its points (see lookup)

    def lookup(self, chart_type: str, claim_type: str, k: int, tools=None) -> tuple[str, list[float]]:
        for key in fallback_chain(chart_type, claim_type, k, tools):
            ratios = self.groups.get(key)
            # Points of one chart are not independent (one legend overlap, one misread axis hits many points), so a
            # group's real sample size is its number of charts. A 95% cut-off needs at least 19 independent units
            # to be anything but the maximum; groups on fewer charts fall back to a coarser group.
            if ratios and len(ratios) >= self.min_group_size and self.charts.get(key, self.min_group_charts) >= self.min_group_charts:
                return key, ratios
        key = "*|*|*"
        return key, self.groups.get(key, [])

    def cutoff(self, chart_type: str, claim_type: str, k: int, level: float, tools=None) -> tuple[str, float]:
        key, ratios = self.lookup(chart_type, claim_type, k, tools)
        return key, conformal_cutoff(ratios, level)

    def p_value(self, chart_type: str, claim_type: str, k: int, score: float, tools=None) -> float:
        _, ratios = self.lookup(chart_type, claim_type, k, tools)
        return p_value(score, ratios)

    # -- persistence -------------------------------------------------------
    def save(self, path: str | Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"meta": self.meta, "min_group_size": self.min_group_size,
                                    "min_group_charts": self.min_group_charts, "charts": self.charts,
                                    "groups": self.groups}))

    @classmethod
    def load(cls, path: str | Path) -> "CalibrationTable":
        d = json.loads(Path(path).read_text())
        return cls(groups={k: sorted(v) for k, v in d["groups"].items()},
                   min_group_size=d.get("min_group_size", 200), meta=d.get("meta", {}),
                   charts=d.get("charts", {}), min_group_charts=d.get("min_group_charts", 0))

    def summary(self) -> dict[str, dict]:
        out = {}
        for key, r in sorted(self.groups.items()):
            out[key] = {"n": len(r), "charts": self.charts.get(key), "q75": conformal_cutoff(r, 0.75), "q95": conformal_cutoff(r, 0.95)}
        return out


class ConstantTable(CalibrationTable):
    """Baseline B5 ("uncalibrated margin"): margin = raw disagreement x fixed factor.

    No calibration data, so no p-values; the batch check is skipped for B5.
    """

    def __init__(self, factor_flag: float = 1.0, factor_accept: float = 0.5):
        super().__init__(groups={}, min_group_size=0, meta={"constant": True})
        self.factors = {"flag": factor_flag, "accept": factor_accept}

    def cutoff(self, chart_type, claim_type, k, level, tools=None):
        return "constant", self.factors["flag"] if level >= 0.9 else self.factors["accept"]

    def p_value(self, chart_type, claim_type, k, score, tools=None):
        return float("nan")
