"""Tool 1: crop around the target x position, upscale, ask the VLM for one number.

The crop keeps the y-axis labels (stitched to the left of the cut-out) so the
model can read the scale; the series colour from the legend goes in the prompt.
"""
from __future__ import annotations

import numpy as np
from PIL import Image

from ..models.vlm import LLM, extract_json
from ..schemas import Figure, PointQuery
from .axis import ChartReadError, analyse, series_colour
from .base import Tool, ToolError
from .chart_ocr import load_bgr

PROMPT = ("This is a zoomed part of a chart; the y-axis labels are on the left. "
          "What is the value of the series \"{series}\"{colour} at x = \"{x}\"? "
          "Read it against the y-axis as precisely as you can. "
          'Answer only with JSON: {{"value": <number>}}')


def make_crop(fig: Figure, q: PointQuery) -> tuple[Image.Image, str]:
    """Return (crop, colour hint). Falls back to the full chart if geometry fails."""
    img = load_bgr(fig.image_path)
    try:
        geo = analyse(fig.image_path)
        xc = geo.x_for(q.x)
        if xc is None:
            raise ChartReadError("x_not_found")
        s = 1.5 * geo.tick_spacing()
        a = geo.area
        top, bottom = max(0, a.top - 5), min(img.shape[0], a.bottom + 3 * geo.font_px)
        axis_strip = img[top:bottom, 0:a.left + 2]
        window = img[top:bottom, int(max(a.left, xc - s)):int(min(a.right, xc + s))]
        crop = np.hstack([axis_strip, np.full((bottom - top, 4, 3), 255, np.uint8), window])
        hint = ""
        try:
            b, g, r = (int(v) for v in series_colour(img, geo, q.series))
            hint = f" (drawn in colour #{r:02x}{g:02x}{b:02x})"
        except ChartReadError:
            pass
    except ChartReadError:
        crop, hint = img, ""
    pil = Image.fromarray(crop[..., ::-1])
    return pil.resize((pil.width * 2, pil.height * 2), Image.LANCZOS), hint


class VlmCropTool(Tool):
    name = "vlm_crop"
    scope = "point"
    cost = 2.5
    kind = "neural"

    def __init__(self, llm: LLM, cache=None, temperature: float = 0.0, name: str = "vlm_crop"):
        super().__init__(cache)
        self.llm, self.temperature, self.name = llm, temperature, name   # "vlm_crop@s2" = sample 2 (E4)
        self.version = f"v1:{llm.name}:t{temperature}:{name}"

    def _read(self, fig: Figure, q: PointQuery) -> float:
        crop, hint = make_crop(fig, q)
        answer = self.llm.generate(PROMPT.format(series=q.series, x=q.x, colour=hint), [crop],
                                   temperature=self.temperature, max_new_tokens=32)[0]
        try:
            return float(str(extract_json(answer)["value"]).rstrip("%"))
        except (ValueError, KeyError, TypeError):
            raise ToolError("bad_json") from None
