"""Where does the OCR+pixel tool go wrong? Step-by-step check against the ground truth.

For each chart it checks the intermediate results, not only the final value:
  axis      y mapping vs the true y-axis limits
  legend    detected entries vs true series, and detected colour vs true colour
  reading   ok / refused / silent error (> 2% of the axis range), with the first wrong step

    python scripts/diagnose_ocr_pixel.py --n 30 --hard
"""
import argparse
import random
import tempfile
from collections import Counter
from pathlib import Path

import numpy as np
from rapidfuzz import fuzz

from reportlens.generator.plot import render, sample_style
from reportlens.generator.tables import make_table
from reportlens.schemas import Figure, PointQuery
from reportlens.tools.axis import ChartReadError, analyse
from reportlens.tools.chart_ocr import load_bgr
from reportlens.tools.ocr_pixel import OcrPixelTool


def hex_bgr(h):
    h = h.lstrip("#")
    return np.array([int(h[4:6], 16), int(h[2:4], 16), int(h[0:2], 16)], float)


ap = argparse.ArgumentParser()
ap.add_argument("--n", type=int, default=30)
ap.add_argument("--hard", action="store_true")
ap.add_argument("--held-out", action="store_true")
ap.add_argument("--kind", default=None)
args = ap.parse_args()

out = Path(tempfile.mkdtemp())
tool = OcrPixelTool()
charts = Counter()
reads = Counter()
for i in range(args.n):
    rng = random.Random(f"bench-{i}")
    t = make_table(rng, f"b{i}", kind=args.kind, hard=args.hard)
    p = out / f"b{i}.png"
    render(t, sample_style(rng, args.held_out, args.hard), p)
    charts["charts"] += 1
    try:
        g = analyse(str(p))
    except ChartReadError as e:
        charts[f"geometry failed: {e}"] += 1
        reads["refused: geometry " + str(e)] += sum(len(v) for v in t.series.values())
        continue
    lo, hi = t.ylim
    a = g.area
    y_err = max(abs(g.yfit.value(a.bottom) - lo), abs(g.yfit.value(a.top) - hi)) / t.span
    charts["axis ok (<1%)" if y_err < 0.01 else "axis WRONG"] += 1

    # legend: which true series were found, and with the right colour?
    found = {}
    for name in t.series:
        best = max(g.legend, key=lambda n: fuzz.token_set_ratio(n.lower(), name.lower()), default=None)
        if best and fuzz.token_set_ratio(best.lower(), name.lower()) >= 70:
            dist = np.sqrt(((g.legend[best][0] - hex_bgr(t.meta["colors"][name])) ** 2).sum())
            found[name] = dist
    n_true = len(t.series)
    charts["series in legend (found/true)"] += 0
    charts[f"legend found {len(found)}/{n_true}"] += 1
    charts["legend colour wrong (>60)"] += sum(d > 60 for d in found.values())

    fig = Figure(figure_id="f", report_id="r", image_path=str(p), chart_type=t.kind)
    for s in t.series:
        for x in t.x_values:
            r = tool.read(fig, PointQuery(series=s, x=x))
            if not r.ok:
                reads[f"refused: {r.error}"] += 1
                continue
            err = abs(r.value - t.value(s, x)) / t.span
            if err <= 0.02:
                reads["ok"] += 1
                continue
            if y_err >= 0.01:
                cause = "axis mapping wrong"
            elif s in found and found[s] > 60:
                cause = "legend colour wrong"
            elif g.xfit is not None and t.kind == "line":
                true_x = float(x)
                cause = "x position / other line"
            else:
                cause = "other"
            reads[f"SILENT ERROR: {cause}"] += 1

print("charts:")
for k, v in sorted(charts.items()):
    if v:
        print(f"  {k:40s} {v}")
total = sum(reads.values())
print(f"reads ({total}):")
for k, v in reads.most_common():
    print(f"  {k:40s} {v:5d}  {v / total:.0%}")
