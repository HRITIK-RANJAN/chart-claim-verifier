"""SIMULATED tools for running the pipeline on a laptop (week-1 "stub tools").

They read the ground truth and add noise. NEVER report results from them:
they exist so the agent, calibration, metrics and tests can be built and
checked before the GPU tools are ready.

The noise model is deliberately not independent: tools in the same "family"
(vlm_crop and vlm_table share a model) share part of their error, so the
calibration and the correlation analysis (E4) have something real to find.
"""
from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass

from ..generator.tables import ChartTable
from ..schemas import Figure, PointQuery
from .base import Table, TableTool, Tool, ToolError, image_key, match_name


@dataclass
class NoiseModel:
    sd: float              # own noise, fraction of axis span
    fail_rate: float       # returns an error
    gross_rate: float      # reads a neighbouring series / point instead
    family: str            # tools in one family share an error term
    shared_sd: float       # sd of the shared term, fraction of axis span


NOISE = {
    "sim_vlm_crop":  NoiseModel(sd=0.010, fail_rate=0.03, gross_rate=0.02, family="vlm", shared_sd=0.012),
    "sim_vlm_table": NoiseModel(sd=0.014, fail_rate=0.05, gross_rate=0.03, family="vlm", shared_sd=0.012),
    "sim_deplot":    NoiseModel(sd=0.018, fail_rate=0.08, gross_rate=0.04, family="deplot", shared_sd=0.008),
}


def _rng(*parts) -> random.Random:
    return random.Random(int(hashlib.sha1("|".join(map(str, parts)).encode()).hexdigest()[:12], 16))


class TruthIndex:
    """image path -> ground-truth table (only the simulated tools may use this)."""

    def __init__(self):
        self.tables: dict[str, ChartTable] = {}

    def add(self, image_path: str, table: ChartTable) -> None:
        self.tables[image_path] = table

    def get(self, image_path: str) -> ChartTable:
        if image_path not in self.tables:
            raise ToolError("no_truth")
        return self.tables[image_path]


def simulate(name: str, nm: NoiseModel, t: ChartTable, fig_key: str, series: str, x: str) -> float:
    r = _rng(name, fig_key, series, x)
    if r.random() < nm.fail_rate:
        raise ToolError("sim_failure")
    labels = (t.meta.get("style") or {}).get("value_labels", False) and t.kind != "line"
    scale = 0.25 if labels else 1.0                     # printed values are much easier to read
    v = t.value(series, x)
    if r.random() < nm.gross_rate:                       # misread: neighbour series / point
        names = list(t.series)
        if len(names) > 1:
            v = t.value(r.choice([n for n in names if n != series]), x)
        else:
            i = t.x_values.index(x)
            v = t.value(series, t.x_values[i - 1 if i else 1])
    shared = _rng(nm.family, fig_key, series, x).gauss(0, nm.shared_sd * scale)
    return v + (shared + r.gauss(0, nm.sd * scale)) * t.span


class SimPointTool(Tool):
    scope = "point"
    kind = "simulated"

    def __init__(self, name: str, truth: TruthIndex, cache=None, cost: float = 2.5):
        super().__init__(cache)
        self.name, self.truth, self.nm, self.cost = name, truth, NOISE[name], cost
        self.version = "sim-v1"

    def _read(self, fig: Figure, q: PointQuery) -> float:
        t = self.truth.get(fig.image_path)
        s = _match(t, q.series)
        x = _match_x(t, q.x)
        return simulate(self.name, self.nm, t, image_key(fig.image_path), s, x)


class SimSampleTool(SimPointTool):
    """'sim_vlm_crop@sK': the K-th sample of the SAME simulated model (for E4).

    Samples repeat the base model's mistake and only add a little noise of their own,
    which is what repeated sampling of one VLM tends to look like.
    """

    def __init__(self, name: str, truth: TruthIndex, cache=None, cost: float = 2.5, own_sd: float = 0.004):
        base = name.split("@")[0]
        Tool.__init__(self, cache)
        self.name, self.base, self.truth, self.nm, self.cost, self.own_sd = name, base, truth, NOISE[base], cost, own_sd
        self.version = "sim-v1"

    def _read(self, fig: Figure, q: PointQuery) -> float:
        t = self.truth.get(fig.image_path)
        s, x = _match(t, q.series), _match_x(t, q.x)
        r = _rng(self.name, image_key(fig.image_path), s, x)
        if r.random() < self.nm.fail_rate:
            raise ToolError("sim_failure")
        nm = NoiseModel(self.nm.sd, 0.0, self.nm.gross_rate, self.nm.family, self.nm.shared_sd)
        return simulate(self.base, nm, t, image_key(fig.image_path), s, x) + r.gauss(0, self.own_sd) * t.span


class SimTableTool(TableTool):
    kind = "simulated"

    def __init__(self, name: str, truth: TruthIndex, cache=None, cost: float = 4.0):
        super().__init__(cache)
        self.name, self.truth, self.nm, self.cost = name, truth, NOISE[name], cost
        self.version = "sim-v1"

    def extract_table(self, fig: Figure) -> Table:
        t = self.truth.get(fig.image_path)
        out: Table = {}
        for s in t.series:
            row = {}
            for x in t.x_values:
                try:
                    row[x] = simulate(self.name, self.nm, t, image_key(fig.image_path), s, x)
                except ToolError:
                    pass
            out[s] = row
        return out


def _match(t: ChartTable, series: str) -> str:
    m = match_name(series, list(t.series))
    if m:
        return m
    if len(t.series) == 1:
        return next(iter(t.series))
    raise ToolError("series_not_found")


def _match_x(t: ChartTable, x: str) -> str:
    if x in t.x_values:
        return x
    m = match_name(x, t.x_values, 85)
    if m:
        return m
    for xx in t.x_values:
        try:
            if float(xx) == float(x):
                return xx
        except ValueError:
            pass
    raise ToolError("x_not_found")
