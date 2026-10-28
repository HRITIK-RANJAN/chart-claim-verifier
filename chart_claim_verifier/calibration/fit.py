"""Fit calibration tables from charts with known values (implementation.md §8.1, §8.3).

For every calibration item (a chart point, or a derived quantity such as a
difference) we have the true value and every tool's reading. For each number
of readings k we take ONE subset of k tools per item -- the first k in the
policy's order if one is given, else a seeded random subset -- and record

    ratio = |true - estimate| / (disagreement + eps * axis span)

Using one subset per item and per group keeps the n honest: the conformal adjustment assumes one ratio per
exchangeable item. The k-groups take one subset per item; each tool-set group takes that exact set, once per item.
"""
from __future__ import annotations

import itertools
import random
from dataclasses import dataclass

from ..measure.aggregate import disagreement, estimate
from .store import CalibrationTable, group_key, tools_key


@dataclass
class CalibrationItem:
    chart_type: str
    claim_type: str
    truth: float
    tool_values: dict[str, float]     # tool -> derived value (failed tools left out)
    span: float                       # axis span of the figure
    figure_id: str = ""


def ratio(truth: float, values: list[float], eps_abs: float) -> float:
    return abs(truth - estimate(values)) / (disagreement(values) + eps_abs)


def _subset(tools: list[str], k: int, order: list[str] | None, rng: random.Random) -> list[str]:
    if order:
        ranked = [t for t in order if t in tools] + sorted(t for t in tools if t not in order)
        return ranked[:k]
    return rng.sample(sorted(tools), k)


def fit_table(items: list[CalibrationItem], eps: float, min_group_size: int = 200,
              order: list[str] | None = None, max_k: int = 4, seed: int = 0,
              meta: dict | None = None, min_group_charts: int = 0) -> CalibrationTable:
    rng = random.Random(seed)
    groups: dict[str, list[float]] = {}
    charts: dict[str, set] = {}

    def add(key: str, r: float, chart: str) -> None:
        groups.setdefault(key, []).append(r)
        charts.setdefault(key, set()).add(chart)

    for it in items:
        tools = list(it.tool_values)
        for k in range(2, min(max_k, len(tools)) + 1):
            chosen = _subset(tools, k, order, rng)
            r = ratio(it.truth, [it.tool_values[t] for t in chosen], eps * it.span)
            # Store at every pooling level so lookups can fall back.
            for key in {group_key(it.chart_type, it.claim_type, k), group_key(it.chart_type, "*", k),
                        group_key("*", "*", k), "*|*|*"}:
                add(key, r, it.figure_id)
        # U14: one ratio per item for EVERY set of tools that answered, so the margin fits the pair the planner uses
        for k in range(2, min(max_k, len(tools)) + 1):
            for sub in itertools.combinations(sorted(tools), k):
                r = ratio(it.truth, [it.tool_values[t] for t in sub], eps * it.span)
                for key in (tools_key(it.chart_type, it.claim_type, sub), tools_key(it.chart_type, "*", sub),
                            tools_key("*", "*", sub)):
                    add(key, r, it.figure_id)

    groups = {k: sorted(v) for k, v in groups.items()}
    m = {"eps": eps, "order": order, "n_items": len(items), "seed": seed}
    m.update(meta or {})
    return CalibrationTable(groups=groups, min_group_size=min_group_size, meta=m,
                            charts={k: len(v) for k, v in charts.items()}, min_group_charts=min_group_charts)
