"""Quick accuracy check of the OCR+pixel tool on freshly generated charts.

    python scripts/bench_ocr_pixel.py --n 40 [--held-out]
"""
import argparse
import random
import tempfile
from collections import defaultdict
from pathlib import Path

import numpy as np

from reportlens.generator.plot import render, sample_style
from reportlens.generator.tables import make_table
from reportlens.schemas import Figure, PointQuery
from reportlens.tools.ocr_pixel import OcrPixelTool

ap = argparse.ArgumentParser()
ap.add_argument("--n", type=int, default=40)
ap.add_argument("--held-out", action="store_true")
ap.add_argument("--hard", action="store_true")
args = ap.parse_args()

tool, out = OcrPixelTool(), Path(tempfile.mkdtemp())
errs, fails = defaultdict(list), defaultdict(lambda: defaultdict(int))
for i in range(args.n):
    rng = random.Random(f"bench-{i}")
    t = make_table(rng, f"b{i}", hard=args.hard)
    render(t, sample_style(rng, args.held_out, args.hard), out / f"b{i}.png")
    fig = Figure(figure_id="f", report_id="r", image_path=str(out / f"b{i}.png"), chart_type=t.kind)
    for s in t.series:
        for x in t.x_values:
            r = tool.read(fig, PointQuery(series=s, x=x))
            if r.ok:
                errs[t.kind].append(abs(r.value - t.value(s, x)) / t.span)
            else:
                fails[t.kind][r.error] += 1
for k in sorted(set(errs) | set(fails)):
    e = np.array(errs[k] or [np.nan]) * 100
    n_fail = sum(fails[k].values())
    n_ok = len(errs[k])
    print(f"{k:12s} n={n_ok + n_fail:4d} ok={n_ok / (n_ok + n_fail):.0%}  "
          f"median err={np.nanmedian(e):.2f}%  p90={np.nanpercentile(e, 90):.2f}%  max={np.nanmax(e):.1f}% of span  "
          f"fails={dict(fails[k])}")
