"""Tool interface (implementation.md §6.5).

Two kinds of tools:
  * point tools read one (series, x) value per call (vlm_crop, ocr_pixel)
  * table tools turn the whole figure into a table once; every later lookup on
    that figure is free (vlm_table, deplot)

Every tool returns a Reading and never raises: failures come back as
ok=False with a short error code, and the controller decides how to recover.
"""
from __future__ import annotations

import functools
import hashlib
import time
from abc import ABC, abstractmethod
from typing import Literal

from rapidfuzz import fuzz, process

from ..models.vlm import OfflineMiss
from ..schemas import Figure, PointQuery, Reading
from .cache import ReadingCache

Table = dict[str, dict[str, float]]          # series -> x -> value


@functools.lru_cache(maxsize=4096)
def image_key(path: str) -> str:
    """Content hash of a figure image: the same chart gets the same cached readings
    wherever it was extracted to (e.g. a report and its clean twin)."""
    try:
        return hashlib.sha1(open(path, "rb").read()).hexdigest()
    except OSError:
        return path


class Tool(ABC):
    name: str = "tool"
    scope: Literal["point", "figure"] = "point"
    cost: float = 1.0                         # seconds per uncached call, measured on the pilot
    version: str = "v1"                       # bump when behaviour changes -> invalidates the cache
    kind: str = "neural"                      # "neural" | "classical" | "simulated"

    def __init__(self, cache: ReadingCache | None = None):
        self.cache = cache

    # -- what subclasses implement -------------------------------------------
    @abstractmethod
    def _read(self, fig: Figure, q: PointQuery) -> float:
        """Return the value or raise ToolError(code)."""

    # -- what callers use -------------------------------------------------------
    def read(self, fig: Figure, q: PointQuery) -> Reading:
        key = (self.name, self.version, image_key(fig.image_path), q.series, q.x)
        if self.cache is not None:
            hit = self.cache.get(key)
            if hit is not None:
                return Reading(**{**hit, "cached": True, "query": q})
        t0 = time.perf_counter()
        try:
            value, ok, err = float(self._read(fig, q)), True, None
        except ToolError as e:
            value, ok, err = None, False, e.code
        except OfflineMiss:                   # replay without the model: not a real failure, never cached
            return Reading(tool=self.name, value=None, ok=False, error="offline_miss",
                           latency_s=0.0, cached=False, query=q)
        except Exception as e:                # a tool bug must not crash the agent
            value, ok, err = None, False, f"exception:{type(e).__name__}"
        r = Reading(tool=self.name, value=value, ok=ok, error=err,
                    latency_s=time.perf_counter() - t0, cached=False, query=q)
        if self.cache is not None:
            self.cache.put(key, r.model_dump(exclude={"query", "cached"}))
        return r


class ToolError(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


class TableTool(Tool):
    """Extract the figure's table once (cached), then look values up by fuzzy name."""
    scope = "figure"

    def __init__(self, cache: ReadingCache | None = None):
        super().__init__(cache)
        self._tables: dict[str, Table | ToolError] = {}

    @abstractmethod
    def extract_table(self, fig: Figure) -> Table:
        ...

    def table(self, fig: Figure) -> Table:
        key = (self.name, self.version, image_key(fig.image_path), "__table__", "")
        if fig.image_path not in self._tables:
            hit = self.cache.get(key) if self.cache else None
            if hit is not None:
                self._tables[fig.image_path] = hit.get("table") or ToolError(hit.get("error", "no_table"))
            else:
                try:
                    tab = self.extract_table(fig)
                    if not tab:
                        raise ToolError("empty_table")
                    self._tables[fig.image_path] = tab
                    if self.cache:
                        self.cache.put(key, {"table": tab})
                except ToolError as e:
                    self._tables[fig.image_path] = e
                    if self.cache:
                        self.cache.put(key, {"table": None, "error": e.code})
        tab = self._tables[fig.image_path]
        if isinstance(tab, ToolError):
            raise tab
        return tab

    def has_table(self, fig: Figure) -> bool:
        return fig.image_path in self._tables

    def _read(self, fig: Figure, q: PointQuery) -> float:
        return lookup(self.table(fig), q.series, q.x)


def match_name(name: str, options: list[str], cutoff: float = 70) -> str | None:
    if not options:
        return None
    hit = process.extractOne(name, options, scorer=fuzz.token_set_ratio, processor=str.lower)
    return hit[0] if hit and hit[1] >= cutoff else None


def lookup(table: Table, series: str, x: str) -> float:
    s = match_name(series, list(table))
    if s is None:
        if len(table) == 1:                    # single-series chart: the only series
            s = next(iter(table))
        else:
            raise ToolError("series_not_found")
    row = table[s]
    xx = x if x in row else match_name(x, list(row), cutoff=85)
    if xx is None:
        try:                                   # numeric x ("10" vs "10.0")
            xx = next(k for k in row if _float(k) is not None and _float(k) == _float(x))
        except StopIteration:
            raise ToolError("x_not_found") from None
    return float(row[xx])


def _float(s: str) -> float | None:
    try:
        return float(s)
    except (TypeError, ValueError):
        return None
