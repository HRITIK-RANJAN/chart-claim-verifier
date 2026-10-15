"""What does this chart look like? Cheap observations made BEFORE measuring.

The agent bases its decisions on these observations plus the measured tool
profile (evaluation/tool_profile.py), instead of trial and error.

Observations (no model calls; they reuse the geometry analysis already done
during ingest):
  chart_type     bar / grouped_bar / line
  small_image    the original image is small or low-resolution (< 700 px wide)
  n_series       legend entries found (0 if no readable legend)
  value_labels   numbers printed inside the plot area (bars with labels)
  axis_readable  the y-axis could be read (tick labels + line fit)

They are summarised into a situation key used to look up the tool profile:
    "<line|bar>|<easy|hard>"   hard = small image, >= 4 series, or unreadable axis
"""
from __future__ import annotations

import functools
import re
from dataclasses import asdict, dataclass

from ..schemas import Figure
from ..tools.axis import ChartReadError, analyse
from ..tools.chart_ocr import ocr_lines, upscale_factor


@dataclass(frozen=True)
class Situation:
    chart_type: str
    small_image: bool
    n_series: int
    value_labels: bool
    axis_readable: bool

    @property
    def hard(self) -> bool:
        return self.small_image or self.n_series >= 4 or not self.axis_readable

    @property
    def key(self) -> str:
        family = "line" if self.chart_type == "line" else "bar"
        return f"{family}|{'hard' if self.hard else 'easy'}"

    def describe(self) -> str:
        bits = [self.chart_type.replace("_", " ") + " chart"]
        if self.small_image:
            bits.append("small/low-resolution image")
        bits.append(f"{self.n_series} series in legend" if self.n_series else "no readable legend")
        if self.value_labels:
            bits.append("values printed on bars")
        if not self.axis_readable:
            bits.append("y-axis not readable")
        return ", ".join(bits)

    def to_dict(self) -> dict:
        return {**asdict(self), "key": self.key, "hard": self.hard}


@functools.lru_cache(maxsize=1024)
def _observe(image_path: str, chart_type: str) -> Situation:
    try:
        geo = analyse(image_path)
        axis_ok, n_series = True, len(geo.legend)
        a = geo.area
        inside = ocr_lines(image_path, (a.left, a.top, a.right, a.bottom))
        labels = sum(bool(re.fullmatch(r"\d+(?:\.\d+)?", ln.text.strip())) for ln in inside) >= 2
    except ChartReadError:
        axis_ok, n_series, labels = False, 0, False
    return Situation(chart_type, upscale_factor(image_path) > 1, n_series, labels, axis_ok)


def observe(fig: Figure) -> Situation:
    return _observe(fig.image_path, fig.chart_type)


@functools.lru_cache(maxsize=1024)
def _tick_labels(image_path: str) -> tuple[str, ...] | None:
    try:
        return tuple(t for _, t in analyse(image_path).xticks)
    except ChartReadError:
        return None


def _same(a: str, b: str) -> bool:
    try:
        return float(a) == float(b)
    except ValueError:
        return a.strip().lower() == b.strip().lower()


def x_on_tick(fig: Figure, xs: list[str]) -> bool | None:
    """Do all these x values have their own tick label? None if the x axis could not be read.

    Measured on the calibration charts: table tools (DePlot, VLM table) return only
    labelled x values, so an unlabelled epoch makes them fail with x_not_found.
    """
    labels = _tick_labels(fig.image_path)
    if not labels:
        return None
    return all(any(_same(x, t) for t in labels) for x in xs)
