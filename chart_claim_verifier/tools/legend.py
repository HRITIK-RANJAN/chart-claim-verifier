"""Repair for `ocr_pixel` (U7): read the legend entries with the VLM.

`ocr_pixel` finds the legend handles (small coloured marks) without reading text, but it needs the NAME
next to each handle to know which colour is which series. Tesseract fails on small, compressed legends
("series_not_found"). The VLM reads that text reliably, so one call per figure gives the names; they are
paired with the handles by vertical order. If the counts differ the tool refuses ("legend_mismatch").
"""
from __future__ import annotations

from ..models.vlm import LLM, OfflineMiss, extract_json
from ..schemas import Figure
from .base import image_key
from .cache import ReadingCache

PROMPT = ("List the legend entries of this chart from top to bottom, exactly as written. "
          'Answer only with JSON: {"legend": ["first entry", "second entry"]}')


def read_legend(llm: LLM, fig: Figure, cache: ReadingCache | None = None) -> list[str] | None:
    """The legend entries top to bottom, or None. One VLM call per figure; the answer is cached."""
    key = ("legend", f"v1:{getattr(llm, 'base_name', llm.name)}", image_key(fig.image_path), "__legend__", "")
    hit = cache.get(key) if cache else None
    if hit is not None:
        return hit.get("names")
    try:
        data = extract_json(llm.generate(PROMPT, [fig.image_path], max_new_tokens=128)[0])
        names = [str(n).strip() for n in data["legend"] if str(n).strip()]
    except OfflineMiss:
        return None                                  # replay without the model: not a failure, not cached
    except (ValueError, KeyError, TypeError):
        names = []
    if cache:
        cache.put(key, {"names": names or None})
    return names or None
