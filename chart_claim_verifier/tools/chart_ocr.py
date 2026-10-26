"""OCR of chart images with Tesseract: words and lines with pixel boxes."""
from __future__ import annotations

import functools
from dataclasses import dataclass

import cv2
import numpy as np
import pytesseract

UPSCALE = 4


@dataclass(frozen=True)
class OcrLine:
    text: str
    x0: float
    y0: float
    x1: float
    y1: float
    conf: float

    @property
    def cx(self) -> float:
        return (self.x0 + self.x1) / 2

    @property
    def cy(self) -> float:
        return (self.y0 + self.y1) / 2

    @property
    def h(self) -> float:
        return self.y1 - self.y0


@functools.lru_cache(maxsize=64)
def _load(path: str) -> np.ndarray:
    img = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if img is None:
        raise FileNotFoundError(path)
    if img.shape[1] < 700:          # small / low-dpi figures: work at 2x so thin lines and small text survive
        img = cv2.resize(img, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
    return img


def upscale_factor(path: str) -> int:
    img = cv2.imread(str(path), cv2.IMREAD_COLOR)
    return 2 if img is not None and img.shape[1] < 700 else 1


def load_bgr(path: str) -> np.ndarray:
    """The chart image every pixel tool works on (a copy; small images are upscaled 2x)."""
    return _load(str(path)).copy()


def _words(gray_up: np.ndarray, psm: int) -> list[dict]:
    d = pytesseract.image_to_data(gray_up, config=f"--psm {psm}", output_type=pytesseract.Output.DICT)
    out = []
    for i, text in enumerate(d["text"]):
        text = text.strip()
        if not text or float(d["conf"][i]) < 10:
            continue
        out.append({"text": text, "x0": d["left"][i] / UPSCALE, "y0": d["top"][i] / UPSCALE,
                    "x1": (d["left"][i] + d["width"][i]) / UPSCALE, "y1": (d["top"][i] + d["height"][i]) / UPSCALE,
                    "conf": float(d["conf"][i])})
    return out


def group_lines(words: list[dict], gap_factor: float = 0.9) -> list[OcrLine]:
    """Merge words that sit on the same baseline and are close together."""
    words = sorted(words, key=lambda w: (round((w["y0"] + w["y1"]) / 2 / 4), w["x0"]))
    lines: list[list[dict]] = []
    for w in words:
        h = w["y1"] - w["y0"]
        for ln in lines:
            last = ln[-1]
            same_row = abs((last["y0"] + last["y1"]) / 2 - (w["y0"] + w["y1"]) / 2) < 0.5 * max(h, last["y1"] - last["y0"])
            if same_row and 0 <= w["x0"] - last["x1"] < gap_factor * max(h, 6):
                ln.append(w)
                break
        else:
            lines.append([w])
    return [OcrLine(" ".join(w["text"] for w in ln), min(w["x0"] for w in ln), min(w["y0"] for w in ln),
                    max(w["x1"] for w in ln), max(w["y1"] for w in ln),
                    float(np.mean([w["conf"] for w in ln]))) for ln in lines]


@functools.lru_cache(maxsize=512)
def ocr_lines(path: str, region: tuple[int, int, int, int] | None = None) -> tuple[OcrLine, ...]:
    """Text lines in the chart, or in `region` = (x0, y0, x1, y1), in image pixels."""
    img = load_bgr(path)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    x0, y0 = 0, 0
    if region:
        x0, y0, x1, y1 = region
        gray = gray[y0:y1, x0:x1]
    up = cv2.resize(gray, None, fx=UPSCALE, fy=UPSCALE, interpolation=cv2.INTER_CUBIC)
    lines = group_lines(_words(up, psm=11))
    return tuple(OcrLine(l.text, l.x0 + x0, l.y0 + y0, l.x1 + x0, l.y1 + y0, l.conf) for l in lines)
