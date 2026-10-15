"""Build the tool set named in the config."""
from __future__ import annotations

from .base import Tool
from .cache import ReadingCache
from .ocr_pixel import OcrPixelTool
from .simulated import SimPointTool, SimSampleTool, SimTableTool, TruthIndex


def build_tools(names: list[str], cache: ReadingCache | None = None, llm=None,
                truth: TruthIndex | None = None, deplot_model: str = "google/deplot",
                offline: bool = False) -> dict[str, Tool]:
    tools: dict[str, Tool] = {}
    for n in names:
        if n.startswith("vlm_crop@s"):              # E4: K samples of one model at T > 0
            from .vlm_crop import VlmCropTool
            tools[n] = VlmCropTool(_need(llm, n), cache, temperature=0.7, name=n)
        elif n.startswith("sim_vlm_crop@s"):
            tools[n] = SimSampleTool(n, _need(truth, n), cache)
        elif n == "ocr_pixel":
            tools[n] = OcrPixelTool(cache)
        elif n == "vlm_table":
            from .vlm_table import VlmTableTool
            tools[n] = VlmTableTool(_need(llm, n), cache)
        elif n == "vlm_crop":
            from .vlm_crop import VlmCropTool
            tools[n] = VlmCropTool(_need(llm, n), cache)
        elif n == "deplot":
            from .deplot import DePlotTool
            tools[n] = DePlotTool(cache, deplot_model, offline)
        elif n in ("sim_vlm_table", "sim_deplot"):
            tools[n] = SimTableTool(n, _need(truth, n), cache, cost=4.0 if "vlm" in n else 1.5)
        elif n == "sim_vlm_crop":
            tools[n] = SimPointTool(n, _need(truth, n), cache, cost=2.5)
        else:
            raise ValueError(f"unknown tool {n!r}")
    return tools


def _need(obj, tool: str):
    if obj is None:
        raise ValueError(f"tool {tool!r} needs a model / truth index that was not provided")
    return obj
