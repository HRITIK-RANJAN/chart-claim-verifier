"""Chart geometry from pixels: plot area, axis mappings, x ticks and legend colours.

Shared by ingest (axis span), the OCR+pixel tool, and the crop tool. Steps:
  1. plot area  -- black spines, or a uniform grey panel (ggplot-like styles)
  2. tick marks -- short dark marks just outside the left / bottom edge
  3. tick labels-- each label crop OCR'd on its own (much more reliable than
                   OCR-ing the whole chart, which misses single digits)
  4. y mapping  -- robust line fit pixel -> value over the y ticks
  5. legend     -- OCR'd text inside the plot area + the colour of its handle
"""
from __future__ import annotations

import functools
import itertools
import re
from dataclasses import dataclass, field

import cv2
import numpy as np
import pytesseract
from rapidfuzz import fuzz

from .chart_ocr import load_bgr, ocr_lines, upscale_factor

NUM_RE = re.compile(r"^[-−]?\d+(?:[.,]\d+)?%?$")


class ChartReadError(Exception):
    """Raised with a short error code; tools turn it into Reading(ok=False)."""


@dataclass
class PlotArea:
    left: int
    right: int
    top: int
    bottom: int


@dataclass
class YFit:
    a: float          # value = a * y_pixel + b
    b: float
    ticks: list[tuple[float, float]]

    def value(self, y: float) -> float:
        return self.a * y + self.b

    def pixel(self, v: float) -> float:
        return (v - self.b) / self.a


@dataclass
class Geometry:
    area: PlotArea
    yfit: YFit
    xticks: list[tuple[float, str]]                 # (x pixel, label)
    xfit: tuple[float, float] | None                # numeric x axis: pixel = a * value + b
    legend: dict[str, tuple[np.ndarray, tuple]]      # label -> (BGR colour, bbox)
    legend_box: tuple[int, int, int, int] | None
    font_px: int
    background: np.ndarray
    shape: tuple[int, int]
    notes: list[str] = field(default_factory=list)

    @property
    def y_span(self) -> float:
        return abs(self.yfit.value(self.area.top) - self.yfit.value(self.area.bottom))

    def x_for(self, label: str) -> float | None:
        """Pixel x of a category / numeric x value. None if the axis cannot be read reliably."""
        label = label.strip()
        num = _num(label)
        if self.xfit is not None:                              # numeric axis: use the checked line fit
            if num is None:
                return None
            a, b = self.xfit
            x = a * num + b
            return x if self.area.left - 2 <= x <= self.area.right + 2 else None
        if num is not None and sum(_num(t) is not None for _, t in self.xticks) >= len(self.xticks) / 2:
            return None                    # numeric axis we could not read reliably: do not guess
        best, score = None, 0.0
        for x, t in self.xticks:
            sc = fuzz.ratio(t.lower(), label.lower())
            if sc > score:
                best, score = x, sc
        return best if score >= 70 else None

    def tick_spacing(self) -> float:
        xs = sorted(x for x, _ in self.xticks)
        d = np.diff(xs)
        return float(np.min(d)) if len(d) else (self.area.right - self.area.left) / 2


def _num(text: str) -> float | None:
    t = text.strip().replace("−", "-").replace(",", ".").rstrip("%-—~:°' .").lstrip("~<>—'% ")
    try:
        return float(t)
    except ValueError:
        return None


# ----------------------------------------------------------------- plot area
def _dark(img: np.ndarray, thr: int = 110) -> np.ndarray:
    return img.max(axis=2) < thr


def find_plot_area(img: np.ndarray) -> PlotArea:
    h, w = img.shape[:2]
    dark = _dark(img, 140)           # thin spines turn grey after JPEG compression

    def longest_run(v: np.ndarray) -> int:
        best = cur = 0
        for x in v:
            cur = cur + 1 if x else 0
            best = max(best, cur)
        return best

    rows = [y for y in range(h) if dark[y].sum() > 0.3 * w and longest_run(dark[y]) > 0.3 * w]
    cols = [x for x in range(w) if dark[:, x].sum() > 0.3 * h and longest_run(dark[:, x]) > 0.3 * h]
    if rows and cols:
        bottom, top = max(rows), min(rows)
        left, right = min(cols), max(cols)
        if bottom - top > 0.3 * h and right - left > 0.3 * w:
            return PlotArea(left, right, top if top < bottom - 5 else 0, bottom)

    # grey panel (ggplot-like): rows / columns mostly covered by the panel colour
    g = img.astype(int)
    grey = (g.max(axis=2) - g.min(axis=2) < 6) & (g.max(axis=2) > 200) & (g.max(axis=2) < 245)
    if grey.sum() < 0.1 * h * w:
        raise ChartReadError("no_plot_area")
    vals, counts = np.unique(g[grey][:, 0], return_counts=True)
    panel = np.abs(g - int(vals[np.argmax(counts)])).max(axis=2) < 4
    # a row belongs to the panel if panel pixels stretch across it (bars may cover most of it)
    def stretched(m2d, axis, frac):
        out = []
        for i, line in enumerate(m2d if axis == 0 else m2d.T):
            idx = np.where(line)[0]
            if len(idx) > 0.1 * len(line) and idx[-1] - idx[0] > frac * len(line):
                out.append(i)
        return np.array(out)
    rows = stretched(panel, 0, 0.4)
    cols = stretched(panel, 1, 0.3)
    if len(rows) and len(cols):
        return PlotArea(int(cols.min()), int(cols.max()), int(rows.min()), int(rows.max()))
    raise ChartReadError("no_plot_area")


# ----------------------------------------------------------------- ticks
def _clusters(idx: list[int], gap: int = 2) -> list[float]:
    out, cur = [], []
    for i in idx:
        if cur and i - cur[-1] > gap:
            out.append(float(np.mean(cur)))
            cur = []
        cur.append(i)
    if cur:
        out.append(float(np.mean(cur)))
    return out


def tick_positions(img: np.ndarray, area: PlotArea, s: int = 1) -> tuple[list[float], list[float]]:
    """Tick marks just outside the bottom / left edge. `s` = how much the image was upscaled."""
    dark = _dark(img, 165)            # thin ticks in small / JPEG charts are light grey, not black
    h, w = img.shape[:2]
    # windows start right next to the axis line (where thin ticks are darkest) and grow with the upscale
    below = dark[min(h - 1, area.bottom + 2):min(h, area.bottom + 6 * s), area.left - 1:area.right + 2].any(axis=0)
    xt = [x + area.left - 1 for x in _clusters(list(np.where(below)[0]), gap=2 * s)]
    left = dark[area.top - 1:area.bottom + 2, max(0, area.left - 6 * s):max(1, area.left - 2)].any(axis=1)
    yt = [y + area.top - 1 for y in _clusters(list(np.where(left)[0]), gap=2 * s)]
    return xt, yt


def _ocr_crop(gray: np.ndarray, x0, y0, x1, y1, numeric: bool) -> str:
    h, w = gray.shape
    x0, y0, x1, y1 = max(0, int(x0)), max(0, int(y0)), min(w, int(x1)), min(h, int(y1))
    if x1 - x0 < 3 or y1 - y0 < 3:
        return ""
    crop = cv2.resize(gray[y0:y1, x0:x1], None, fx=4, fy=4, interpolation=cv2.INTER_CUBIC)
    # black text on white: helps with grey tick labels and grey panels
    _, crop = cv2.threshold(crop, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    if crop.mean() < 127:
        crop = 255 - crop
    crop = cv2.copyMakeBorder(crop, 20, 20, 20, 20, cv2.BORDER_CONSTANT, value=255)
    cfg = "--psm 7" + (" -c tessedit_char_whitelist=0123456789.-%" if numeric else "")
    return pytesseract.image_to_string(crop, config=cfg).strip()


def fit_x(ticks: list[tuple[float, str]], tol_px: float = 3.0) -> tuple[float, float] | None:
    """Numeric x axis: line fit pixel = a * value + b that most tick labels agree with.

    Returns None if the axis is not numeric or the labels disagree (OCR misreads).
    """
    pts = [(x, _num(t)) for x, t in ticks if _num(t) is not None]
    if len(pts) < max(2, 0.6 * len(ticks)):
        return None
    best, best_in = None, []
    for (x1, v1), (x2, v2) in itertools.combinations(pts, 2):
        if v1 == v2:
            continue
        a = (x1 - x2) / (v1 - v2)
        b = x1 - a * v1
        if a <= 0:
            continue
        inl = [(x, v) for x, v in pts if abs(a * v + b - x) < tol_px]
        if len(inl) > len(best_in):
            best, best_in = (a, b), inl
    if best is None or len(best_in) < max(2, 0.6 * len(ticks)):
        return None
    xs, vs = np.array([p[0] for p in best_in]), np.array([p[1] for p in best_in])
    a, b = np.polyfit(vs, xs, 1)
    return float(a), float(b)


def fit_y(ticks: list[tuple[float, float]], tol_px: float = 3.0) -> YFit:
    """Robust line fit: try every pair of ticks, keep the fit most ticks agree with."""
    if len(ticks) < 2:
        raise ChartReadError("too_few_y_ticks")
    best, best_in = None, []
    for (y1, v1), (y2, v2) in itertools.combinations(ticks, 2):
        if abs(y1 - y2) < 3 or v1 == v2:
            continue
        a = (v1 - v2) / (y1 - y2)
        if a >= 0:                                     # values must grow upwards
            continue
        b = v1 - a * y1
        inl = [(y, v) for y, v in ticks if abs((v - b) / a - y) < tol_px]
        if len(inl) > len(best_in):
            best, best_in = (a, b), inl
    # two misread ticks can agree by chance, three rarely do: if 3+ ticks were read, 3 must agree
    if best is None or len(best_in) < min(3, len(ticks)):
        raise ChartReadError("y_fit_failed")
    ys, vs = np.array([p[0] for p in best_in]), np.array([p[1] for p in best_in])
    a, b = np.polyfit(ys, vs, 1)
    return YFit(float(a), float(b), best_in)


# ----------------------------------------------------------------- colour
# Thin lines blend with the white background (anti-aliasing, JPEG), which washes out
# their saturation but keeps their hue. So series are matched by HUE, not by RGB.
HUE_TOL = 7          # OpenCV hue runs 0..180
MIN_SAT = 45


def _saturated(img: np.ndarray, min_sat: int = 80) -> np.ndarray:
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    return (hsv[..., 1] > min_sat) & (hsv[..., 2] > 60)


def hue_of(bgr) -> float:
    px = np.uint8([[np.clip(bgr, 0, 255)]])
    return float(cv2.cvtColor(px, cv2.COLOR_BGR2HSV)[0, 0, 0])


def hue_distance(h1: float, h2) -> np.ndarray:
    d = np.abs(np.asarray(h2, float) - h1)
    return np.minimum(d, 180 - d)


def hue_mask(img: np.ndarray, hue: float, tol: float = HUE_TOL, min_sat: int = MIN_SAT) -> np.ndarray:
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    return (hue_distance(hue, hsv[..., 0]) <= tol) & (hsv[..., 1] >= min_sat) & (hsv[..., 2] > 50)


def background_colour(img: np.ndarray, area) -> np.ndarray:
    """Most common colour inside the plot area (white, or the grey panel)."""
    region = img[area.top + 2:area.bottom - 1, area.left + 2:area.right - 1].reshape(-1, 3)
    vals, counts = np.unique(region // 4, axis=0, return_counts=True)
    return vals[np.argmax(counts)].astype(float) * 4 + 2


def mix_mask(img: np.ndarray, colour, bg, min_share: float = 0.35, max_resid: float = 28.0) -> np.ndarray:
    """Pixels that look like `colour` mixed with the background `bg`.

    A thin, blurred line pixel is roughly  share * colour + (1 - share) * background.
    We estimate `share` per pixel and keep pixels that (a) contain enough of the
    colour and (b) are explained well by that mix (small leftover difference).
    Orange stays distinct from red even when both are washed out.
    """
    d = np.asarray(colour, float) - bg
    p = img.astype(float) - bg
    share = (p @ d) / max(float(d @ d), 1e-6)
    resid = np.sqrt(((p - share[..., None] * d) ** 2).sum(axis=2))
    # a pixel containing `share` of a coloured series must itself look coloured
    # (otherwise grey gridlines pass as "a little pink mixed with white")
    chroma = img.max(axis=2).astype(float) - img.min(axis=2)
    want = 0.5 * share * (float(np.max(colour)) - float(np.min(colour)))
    return (share >= min_share) & (share <= 1.3) & (resid <= max_resid) & (chroma >= want)


def colours_confusable(c1, c2, bg, max_resid: float = 28.0) -> bool:
    """Would c2, at full strength, pass as a mix of c1 and the background (or vice versa)?"""
    a = mix_mask(np.array([[c2]], float), c1, bg, 0.35, max_resid)[0, 0]
    b = mix_mask(np.array([[c1]], float), c2, bg, 0.35, max_resid)[0, 0]
    return bool(a or b)


def core_colour(pixels: np.ndarray) -> np.ndarray:
    """Colour of a thin mark: the median of its MOST saturated pixels (the line centre)."""
    hsv = cv2.cvtColor(pixels.reshape(-1, 1, 3).astype(np.uint8), cv2.COLOR_BGR2HSV).reshape(-1, 3)
    keep = hsv[:, 1] >= np.percentile(hsv[:, 1], 70)
    return np.median(pixels.reshape(-1, 3)[keep], axis=0)


# ----------------------------------------------------------------- legend


def _legend_from_handles(img: np.ndarray, gray: np.ndarray, area: PlotArea, fpx: int):
    """Legend handles are small coloured marks stacked at the same x; the label is to their right."""
    a = area
    sat = _saturated(img[a.top + 2:a.bottom - 1, a.left + 2:a.right - 1], MIN_SAT).astype(np.uint8)
    n, _, stats, _ = cv2.connectedComponentsWithStats(sat, connectivity=8)
    cands = []
    for i in range(1, n):
        x, y, w, h, area_px = stats[i]
        if 0.8 * fpx <= w <= 4.5 * fpx and h <= 1.3 * fpx and area_px >= 6:
            cands.append((x + a.left + 2, y + a.top + 2, w, h, i))
    if not cands:
        return {}, None
    # handles of one legend share their left edge
    groups: dict[int, list] = {}
    for c in cands:
        key = next((k for k in groups if abs(k - c[0]) <= 3), c[0])
        groups.setdefault(key, []).append(c)
    best = sorted(max(groups.values(), key=len), key=lambda c: c[1])
    centres = [c[1] + c[3] / 2 for c in best]
    row = float(np.median(np.diff(centres))) if len(best) > 1 else 1.5 * fpx
    half = min(0.75 * fpx, 0.48 * row)               # never let a crop reach the next legend row
    entries, boxes = {}, []
    for x, y, w, h, _ in best:
        cy = y + h / 2
        tx0, tx1 = x + w + 2, min(a.right - 2, x + w + 12 * fpx)
        text = _ocr_crop(gray, tx0, cy - half, tx1, cy + half, False)
        text = re.sub(r"[^A-Za-z0-9\- .+]", "", text).strip(" .-")
        if len(re.sub(r"[^A-Za-z]", "", text)) < 2:
            continue
        patch = img[y:y + h, x:x + w]
        m = _saturated(patch, MIN_SAT)
        colour = core_colour(patch[m]) if m.any() else patch.reshape(-1, 3).mean(axis=0)
        width_px = 0.62 * fpx * len(text)               # rough text width, for the legend box
        box = (int(x), int(cy - 0.7 * fpx), int(min(a.right, tx0 + width_px)), int(cy + 0.7 * fpx))
        entries[text] = (colour, box)
        boxes.append(box)
    return entries, boxes


def _legend_from_text(img: np.ndarray, path: str, area: PlotArea):
    """Fallback: OCR text inside the plot area, then the colour just left of it."""
    sat = _saturated(img)
    entries, boxes = {}, []
    for ln in ocr_lines(path, (area.left, area.top, area.right, area.bottom)):
        letters = re.sub(r"[^A-Za-z]", "", ln.text)
        if len(letters) < 2 or NUM_RE.match(ln.text):
            continue
        hx0 = int(max(area.left, ln.x0 - 4.5 * ln.h))
        band_y = slice(int(ln.cy - 0.3 * ln.h), int(ln.cy + 0.3 * ln.h) + 1)
        band = sat[band_y, hx0:int(ln.x0)]
        if band.sum() < 3:
            continue
        ys, xs = np.where(band)
        colour = core_colour(img[band_y, hx0:int(ln.x0)][ys, xs])
        text = re.sub(r"^\S{1,4}\s+(?=\S)", lambda m: m.group() if re.search(r"[A-Za-z]{2}", m.group()) else "", ln.text)
        text = re.sub(r"^[^A-Za-z0-9]+\s*", "", text)
        box = (hx0, int(ln.y0), int(ln.x1), int(ln.y1))
        entries[text] = (colour, box)
        boxes.append(box)
    return entries, boxes


def find_legend(img: np.ndarray, gray: np.ndarray, path: str, area: PlotArea, fpx: int):
    entries, boxes = _legend_from_handles(img, gray, area, fpx)
    if not entries:
        entries, boxes = _legend_from_text(img, path, area)
    legend_box = None
    if boxes:
        pad = 6
        legend_box = (min(b[0] for b in boxes) - pad, min(b[1] for b in boxes) - pad,
                      max(b[2] for b in boxes) + pad, max(b[3] for b in boxes) + pad)
    return entries, legend_box


def n_colours(img: np.ndarray, area: PlotArea) -> int:
    """How many distinct series colours the plot area contains (by hue)."""
    region = img[area.top + 2:area.bottom - 1, area.left + 2:area.right - 1]
    hsv = cv2.cvtColor(region, cv2.COLOR_BGR2HSV)
    m = (hsv[..., 1] > 80) & (hsv[..., 2] > 60)
    if m.sum() < 20:
        return 0
    hist = np.bincount((hsv[..., 0][m] // 6).astype(int), minlength=30)
    return int((hist > 0.06 * m.sum()).sum())


# ----------------------------------------------------------------- main entry
@functools.lru_cache(maxsize=256)
def analyse(path: str) -> Geometry:
    img = load_bgr(path)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape
    fpx = max(10, round(0.032 * h))
    area = find_plot_area(img)
    xt, yt = tick_positions(img, area, upscale_factor(path))

    dark = _dark(img, 120)
    tick_len = 2
    if yt:                                    # how far the tick marks stick out, so crops skip them
        row = dark[int(round(yt[0])), :area.left][::-1]
        tick_len = int(np.argmin(row)) if not row.all() else 2
    gap = tick_len + 3

    yticks = []
    for y in yt:
        v = _num(_ocr_crop(gray, max(0, area.left - 7 * fpx), y - 0.8 * fpx, area.left - gap, y + 0.8 * fpx, True))
        if v is not None:
            yticks.append((y, v))
    yfit = fit_y(yticks)

    half = 0.48 * (min(np.diff(xt)) if len(xt) > 1 else 3 * fpx)
    boxes = [(x - half, area.bottom + gap, x + half, area.bottom + gap + 1.8 * fpx) for x in xt]
    raw = [(x, _ocr_crop(gray, *b, False).replace(" ", "")) for x, b in zip(xt, boxes)]
    xticks = [(x, t) for x, t in raw if t]
    wordy = sum(len(re.sub(r"[^A-Za-z]", "", t)) >= 2 for _, t in xticks)
    if xticks and wordy < len(xticks) / 2:
        # looks like a numeric axis: read again allowing digits only
        digits = [(x, _ocr_crop(gray, *b, True).replace(" ", "")) for x, b in zip(xt, boxes)]
        xticks = [(x, t) for x, t in digits if t]
    xfit = fit_x(xticks)
    legend, legend_box = find_legend(img, gray, path, area, fpx)
    return Geometry(area, yfit, xticks, xfit, legend, legend_box, fpx, background_colour(img, area), (h, w))


def series_colour(img: np.ndarray, geo: Geometry, series: str) -> np.ndarray:
    """The colour of a series: its legend handle, or the dominant colour if there is no legend."""
    if geo.legend:
        name, score = max(((n, fuzz.token_set_ratio(n.lower(), series.lower())) for n in geo.legend),
                          key=lambda p: p[1])
        if score < 70:
            raise ChartReadError("series_not_found")
        colour = geo.legend[name][0]
        bg = geo.background
        if any(colours_confusable(colour, c, bg) for n, (c, _) in geo.legend.items() if n != name):
            raise ChartReadError("colour_ambiguous")      # two series look alike: do not guess
        return colour
    if n_colours(img, geo.area) > 1:           # several series but no readable legend: don't guess
        raise ChartReadError("legend_not_found")
    a = geo.area
    region = img[a.top:a.bottom, a.left:a.right]
    sat = _saturated(region)
    if sat.sum() < 20:
        raise ChartReadError("no_series_colour")
    px = region[sat].astype(int)
    q = (px // 32) * 32
    vals, counts = np.unique(q, axis=0, return_counts=True)
    dominant = vals[np.argmax(counts)]
    near = px[np.abs(q - dominant).max(axis=1) == 0]
    return np.median(near, axis=0)
