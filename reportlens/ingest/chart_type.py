"""Guess bar / grouped_bar / line from pixels: bars are large solid rectangles."""
from __future__ import annotations

import cv2
import numpy as np

from ..tools.axis import ChartReadError, find_plot_area
from ..tools.chart_ocr import load_bgr


def detect_chart_type(path: str) -> str:
    img = load_bgr(path)
    try:
        a = find_plot_area(img)
        region = img[a.top + 2:a.bottom - 1, a.left + 2:a.right - 1]
    except ChartReadError:
        region = img
    hsv = cv2.cvtColor(region, cv2.COLOR_BGR2HSV)
    sat = ((hsv[..., 1] > 80) & (hsv[..., 2] > 60)).astype(np.uint8)
    if sat.sum() < 50:
        return "unknown"
    n, labels, stats, _ = cv2.connectedComponentsWithStats(sat, connectivity=4)
    min_area = 0.002 * region.shape[0] * region.shape[1]
    bars, hues = 0, set()
    for i in range(1, n):
        x, y, w, h, area = stats[i]
        if area >= min_area and area / (w * h) > 0.85 and h > 8 and w > 6:
            bars += 1
            hues.add(int(np.median(hsv[..., 0][labels == i])) // 12)
    if bars >= 2:
        return "grouped_bar" if len(hues) > 1 else "bar"
    return "line"
