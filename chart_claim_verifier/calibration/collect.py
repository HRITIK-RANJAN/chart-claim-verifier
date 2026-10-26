"""Read every data point of every calibration chart with every tool (implementation.md §8.3).

Produces
  * CalibrationItems for points AND derived quantities (differences, relative
    changes) built from the same point readings, so one table covers all claim types
  * per-point signed tool errors, for the correlation study (E4) and for the
    per-tool error table used by the calibration-informed policy (P1b)
"""
from __future__ import annotations

import random
from collections import defaultdict
from statistics import median

from ..generator.tables import ChartTable
from ..measure.aggregate import derived_value
from ..schemas import Figure, PointQuery
from ..tools.base import Tool
from .fit import CalibrationItem


def collect_figure(fig: Figure, table: ChartTable, tools: dict[str, Tool], rng: random.Random):
    from ..agent.situation import observe, x_on_tick
    span = fig.y_span or table.span
    situation = observe(fig)
    readings: dict[tuple[str, str], dict[str, float]] = {}
    errors = []
    for s in table.series:
        for x in table.x_values:
            vals, fails, lat = {}, {}, {}
            for name, tool in tools.items():
                r = tool.read(fig, PointQuery(series=s, x=x))
                lat[name] = r.latency_s
                if r.ok:
                    vals[name] = r.value
                else:
                    fails[name] = r.error
            readings[(s, x)] = vals
            # errors are fractions of the TRUE axis range, so tools are compared fairly
            errors.append({"chart_type": fig.chart_type, "figure": fig.image_path, "series": s, "x": x,
                           "_situation": situation.key,
                           "_fail": fails, "_latency": lat, "_on_tick": x_on_tick(fig, [x]),
                           **{t: (v - table.value(s, x)) / table.span for t, v in vals.items()}})

    items = [CalibrationItem(fig.chart_type, "point", table.value(s, x), vals, span, fig.figure_id)
             for (s, x), vals in readings.items()]

    def derived(ctype: str, a: tuple[str, str], b: tuple[str, str]):
        va, vb = readings[a], readings[b]
        tv = {}
        for t in set(va) & set(vb):
            d = derived_value(ctype, [va[t], vb[t]])
            if d is not None:
                tv[t] = d
        truth = derived_value(ctype, [table.value(*a), table.value(*b)])
        if truth is not None and len(tv) >= 2:
            items.append(CalibrationItem(fig.chart_type, ctype, truth, tv, span, fig.figure_id))

    names, xs = list(table.series), table.x_values
    n_pairs = max(1, len(readings) // 2)
    for _ in range(n_pairs):
        if len(names) > 1:
            x = rng.choice(xs)
            a, b = rng.sample(names, 2)
            derived("difference", (a, x), (b, x))
        elif len(xs) > 1:
            s = names[0]
            x1, x2 = rng.sample(xs, 2)
            derived("difference", (s, x1), (s, x2))
        if table.kind == "line" and table.percent and len(xs) > 1:
            s = rng.choice(names)
            i, j = sorted(rng.sample(range(len(xs)), 2))
            derived("relative_change", (s, xs[i]), (s, xs[j]))
    return items, errors


def tool_error_table(errors: list[dict], tools: list[str]) -> dict[str, dict[str, float]]:
    """Median |error| (fraction of axis span) per chart type per tool, plus '*' for all."""
    by: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    for e in errors:
        for t in tools:
            if t in e:
                by[e["chart_type"]][t].append(abs(e[t]))
                by["*"][t].append(abs(e[t]))
    return {ct: {t: float(median(v)) for t, v in d.items() if v} for ct, d in by.items()}


def success_rates(errors: list[dict], tools: list[str]) -> dict[str, float]:
    n = len(errors) or 1
    return {t: sum(t in e for e in errors) / n for t in tools}
