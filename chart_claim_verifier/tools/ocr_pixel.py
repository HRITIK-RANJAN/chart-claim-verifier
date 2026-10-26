"""Tool 4: OCR + pixel measurement (implementation.md §6.5).

Classical, shares no weights with the VLM, so it should fail differently:
  plot area -> OCR tick labels -> robust pixel-to-value fit -> find the series
  by its legend colour -> bar top / line point at the x tick -> convert.
"""
from __future__ import annotations

import hashlib

import numpy as np

from ..schemas import Figure, PointQuery
from .axis import ChartReadError, Geometry, analyse, background_colour, mix_mask, series_colour
from .base import Tool, ToolError, image_key
from .chart_ocr import load_bgr

def _mask(img: np.ndarray, colour: np.ndarray, geo: Geometry, x0: int | None = None,
          x1: int | None = None) -> np.ndarray:
    """Series pixels inside the plot area, computed only for columns x0..x1 (speed)."""
    a = geo.area
    x0 = max(a.left + 1, int(x0) if x0 is not None else a.left + 1)
    x1 = min(a.right, int(x1) if x1 is not None else a.right)
    out = np.zeros(img.shape[:2], bool)
    if x1 <= x0:
        return out
    out[a.top + 1:a.bottom, x0:x1] = mix_mask(img[a.top + 1:a.bottom, x0:x1], colour, geo.background)
    if geo.legend_box:                         # legend handles share the series colours
        lx0, ly0, lx1, ly1 = geo.legend_box
        out[max(0, ly0):max(0, ly1), max(0, lx0):max(0, lx1)] = False
    return out


def _in_legend(geo: Geometry, y: float, x0: float, x1: float) -> bool:
    if not geo.legend_box:
        return False
    lx0, ly0, lx1, ly1 = geo.legend_box
    return ly0 - 3 <= y <= ly1 + 3 and x1 >= lx0 and x0 <= lx1


def read_bar(img, geo: Geometry, colour, xc: float) -> float:
    half = 0.5 * geo.tick_spacing() if len(geo.xticks) > 1 else 0.25 * (geo.area.right - geo.area.left)
    x0, x1 = int(max(geo.area.left, xc - half)), int(min(geo.area.right, xc + half))
    m = _mask(img, colour, geo, x0, x1)
    cols = [x for x in range(x0, x1) if m[:, x].sum() >= 3]
    if not cols:
        raise ToolError("bar_not_found")
    # the bar is the longest run of matching columns; keep its middle 60%
    runs, cur = [], [cols[0]]
    for c in cols[1:]:
        if c - cur[-1] <= 1:
            cur.append(c)
        else:
            runs.append(cur)
            cur = [c]
    runs.append(cur)
    run = max(runs, key=len)
    k = max(1, int(len(run) * 0.2))
    mid = run[k:-k] or run
    tops = [int(np.argmax(m[:, x])) for x in mid]
    top = float(np.median(tops))
    # our legend box is estimated from handles + text and can be a few pixels smaller than the frame
    if geo.legend_box and mid[-1] >= geo.legend_box[0] and mid[0] <= geo.legend_box[2] \
            and geo.legend_box[3] - 3 <= top <= geo.legend_box[3] + 14:
        raise ToolError("occluded_by_legend")      # bar top hidden behind the legend
    return geo.yfit.value(top)


def _line_y(m: np.ndarray, xc: float, w: int) -> tuple[float | None, str | None]:
    """y pixel of the line at column xc, or (None, reason)."""
    ys, _ = np.where(m[:, int(xc - w):int(xc + w + 1)])
    if len(ys) < 2:
        return None, None
    ys = np.sort(ys)
    groups = sorted(np.split(ys, np.where(np.diff(ys) > 3)[0] + 1), key=len, reverse=True)
    if len(groups) > 1 and len(groups[1]) >= 0.4 * len(groups[0]):
        return None, "two_lines_at_x"                 # another line of a similar colour is here
    return float(np.median(groups[0])), None


def read_line(img, geo: Geometry, colour, xc: float) -> float:
    reach = 7 + max(4, int(0.25 * geo.font_px)) + 3
    m = _mask(img, colour, geo, xc - reach, xc + reach + 1)
    for w in (2, 4, 7):
        y, why = _line_y(m, xc, w)
        if why:
            raise ToolError(why)
        if y is not None:
            # continuity check: the same line a few pixels left and right must be close by
            step = max(4, int(0.25 * geo.font_px))
            near = [_line_y(m, xc + d, 2)[0] for d in (-step, step)]
            near = [v for v in near if v is not None]
            if near and min(abs(v - y) for v in near) > 2.5 * step:
                raise ToolError("line_not_continuous")
            return geo.yfit.value(y)
    if geo.legend_box and geo.legend_box[0] <= xc <= geo.legend_box[2]:
        raise ToolError("occluded_by_legend")
    raise ToolError("line_not_found_at_x")


class OcrPixelTool(Tool):
    name = "ocr_pixel"
    scope = "point"
    cost = 0.8
    kind = "classical"
    version = "v1"          # unchanged by the legend hint: without a hint the behaviour is identical

    def __init__(self, cache=None):
        super().__init__(cache)
        self.legend_hint: dict[str, list[str]] = {}      # image hash -> legend names read by the repair step (U7)

    def cache_key(self, fig: Figure, q: PointQuery) -> tuple:
        key = super().cache_key(fig, q)
        hint = self.legend_hint.get(key[2])
        if hint:                                          # a hinted reading is a different measurement
            key = key[:4] + (q.x + "|legend=" + hashlib.sha1("|".join(hint).encode()).hexdigest()[:8],)
        return key

    def _read(self, fig: Figure, q: PointQuery) -> float:
        try:
            geo = analyse(fig.image_path)
            img = load_bgr(fig.image_path)
            colour = series_colour(img, geo, q.series, self.legend_hint.get(image_key(fig.image_path)))
        except ChartReadError as e:
            raise ToolError(str(e)) from None
        xc = geo.x_for(q.x)
        if xc is None:
            raise ToolError("x_not_found")
        if fig.chart_type == "line" or (fig.chart_type == "unknown" and _looks_numeric(geo)):
            return read_line(img, geo, colour, xc)
        return read_bar(img, geo, colour, xc)


def _looks_numeric(geo: Geometry) -> bool:
    nums = 0
    for _, t in geo.xticks:
        try:
            float(t)
            nums += 1
        except ValueError:
            pass
    return nums >= max(2, len(geo.xticks) // 2)
