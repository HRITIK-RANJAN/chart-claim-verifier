"""Render result tables as bar / line charts in varied styles (implementation.md §9.1).

`held_out=True` uses a plotting style never seen in calibration or fine-tuning
(grey background, white grid) for the style-shift test set.
"""
from __future__ import annotations

import random
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from .tables import ChartTable  # noqa: E402

# Saturated colours only (no greys): the pixel tool finds series by colour.
PALETTES = [
    ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd", "#17becf"],
    ["#e41a1c", "#377eb8", "#4daf4a", "#984ea3", "#ff7f00", "#a65628"],
    ["#0072b2", "#d55e00", "#009e73", "#cc79a7", "#e69f00", "#56b4e9"],
    ["#1b9e77", "#d95f02", "#7570b3", "#e7298a", "#66a61e", "#e6ab02"],
]
MARKERS = ["o", "s", "^", "D", "v"]


def sample_style(rng: random.Random, held_out: bool = False, hard: bool = False) -> dict:
    if hard:   # small, low-resolution, compressed, no reading aids
        return {
            "palette": rng.choice(PALETTES), "value_labels": False, "grid": rng.random() < 0.3,
            "markers": False, "legend_loc": rng.choice(["best", "lower right", "upper left"]),
            "font_size": rng.choice([8, 9]), "figsize": (round(rng.uniform(4.2, 5.2), 1), round(rng.uniform(2.8, 3.4), 1)),
            "dpi": rng.choice([72, 80, 90]), "held_out": held_out, "line_width": 1.2,
            "jpeg_quality": rng.choice([35, 50, 70]),
        }
    return {
        "palette": rng.choice(PALETTES),
        "value_labels": rng.random() < 0.4,
        "grid": rng.random() < 0.5,
        "markers": rng.random() < 0.7,
        "legend_loc": rng.choice(["best", "lower right", "upper left", "center right"]),
        "font_size": rng.choice([9, 10, 11, 12]),
        "figsize": (round(rng.uniform(5.0, 6.5), 1), round(rng.uniform(3.4, 4.4), 1)),
        "dpi": rng.choice([100, 120, 150]),
        "held_out": held_out,
    }


def render(table: ChartTable, style: dict, path: str | Path) -> ChartTable:
    """Draw the chart to `path` and record the actual y-axis limits on the table."""
    ctx = plt.style.context("ggplot") if style.get("held_out") else plt.style.context("default")
    with ctx:
        plt.rcParams.update({"font.size": style["font_size"], "font.family": "DejaVu Sans"})
        fig, ax = plt.subplots(figsize=style["figsize"], dpi=style["dpi"])
        colors = style["palette"]
        names = list(table.series)
        if table.kind == "line":
            xs = [float(x) for x in table.x_values]
            for i, name in enumerate(names):
                ax.plot(xs, table.series[name], color=colors[i % len(colors)], linewidth=style.get("line_width", 1.8),
                        marker=MARKERS[i] if style["markers"] else None, markersize=4, label=name)
            every = 1 if len(xs) <= 10 else (2 if len(xs) <= 16 else 4)     # long runs: ticks every few epochs
            ax.set_xticks(xs[::every])
            ax.set_xticklabels(table.x_values[::every])
        else:
            pos = np.arange(len(table.x_values))
            width = 0.8 / len(names)
            for i, name in enumerate(names):
                offs = pos - 0.4 + width * (i + 0.5)
                bars = ax.bar(offs, table.series[name], width=width * 0.92, color=colors[i % len(colors)],
                              label=name)
                if style["value_labels"]:
                    ax.bar_label(bars, fmt=f"%.{table.decimals}f", fontsize=style["font_size"] - 3, padding=1)
            ax.set_xticks(pos)
            ax.set_xticklabels(table.x_values)
            top = max(max(v) for v in table.series.values())
            ax.set_ylim(0, min(100.0, top * 1.15) if table.percent else top * 1.15)
        ax.set_xlabel(table.x_label)
        ax.set_ylabel(table.y_label)
        ax.set_title(table.title)
        if style["grid"] and not style.get("held_out"):
            ax.grid(True, alpha=0.3)
        if len(names) > 1 or table.kind == "line":
            ax.legend(loc=style["legend_loc"], fontsize=style["font_size"] - 1, framealpha=0.9)
        fig.tight_layout()
        table.ylim = tuple(float(v) for v in ax.get_ylim())
        table.meta["style"] = {k: v for k, v in style.items() if k != "palette"}
        table.meta["colors"] = {n: colors[i % len(colors)] for i, n in enumerate(names)}
        fig.savefig(path)
        plt.close(fig)
    if style.get("jpeg_quality"):          # like a screenshot pasted into a report
        from PIL import Image
        import io
        im = Image.open(path).convert("RGB")
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=style["jpeg_quality"])
        Image.open(buf).save(path)
    return table
