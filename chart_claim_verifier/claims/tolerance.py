"""Allowed rounding, computed from how a number is written (implementation.md §6.4).

The tolerance is never left to the LLM: it is a deterministic function of the
text, and the data generator labels claims with this same function.

    0.82                  -> ±0.005  (half of the last digit)
    82.4%                 -> ±0.05
    82%                   -> ±0.5
    about 80% / ~80%      -> ±5      (hedged, ends in 0)
    about 82%             -> ±1      (hedged: one unit of the last digit)
    over 80% / above 80%  -> one-sided, true value must be > 80
"""
from __future__ import annotations

import re
from dataclasses import dataclass

HEDGES = ("approximately", "roughly", "around", "about", "nearly", "almost", "close to", "~", "≈")
GREATER = ("more than", "greater than", "at least", "over", "above", "exceeds", "exceeding")
LESS = ("less than", "fewer than", "at most", "under", "below")

# The look-behind skips digits that belong to names: "ResNet-50", "CIFAR-10", "F1".
NUMBER_RE = re.compile(r"(?<![\w.\-])(?P<num>-?\d+(?:\.\d+)?)(?![\w\-])\s*(?P<pct>%|percent\b)?")


@dataclass(frozen=True)
class NumberPhrase:
    value: float
    tolerance: float
    percent: bool
    relation: str          # "approx" | "greater" | "less"
    decimals: int
    hedged: bool
    start: int             # character span of the number in the sentence
    end: int


def rounding_tolerance(num_str: str, hedged: bool) -> float:
    decimals = len(num_str.split(".")[1]) if "." in num_str else 0
    unit = 10.0 ** -decimals
    if not hedged:
        return 0.5 * unit
    integer = abs(int(float(num_str)))
    if decimals == 0 and integer >= 10 and integer % 10 == 0:
        return 5.0
    return 1.0 * unit


def _context_before(text: str, start: int, n_words: int = 3) -> str:
    words = text[:start].lower().replace("~", " ~ ").replace("≈", " ≈ ").split()
    return " " + " ".join(words[-n_words:]) + " "


def phrase_at(text: str, match: re.Match) -> NumberPhrase:
    num = match.group("num")
    before = _context_before(text, match.start())
    hedged = any(f" {h} " in before for h in HEDGES)
    if any(f" {g} " in before for g in GREATER):
        relation = "greater"
    elif any(f" {l} " in before for l in LESS):
        relation = "less"
    else:
        relation = "approx"
    tol = 0.0 if relation != "approx" else rounding_tolerance(num, hedged)
    return NumberPhrase(
        value=float(num),
        tolerance=tol,
        percent=bool(match.group("pct")),
        relation=relation,
        decimals=len(num.split(".")[1]) if "." in num else 0,
        hedged=hedged,
        start=match.start(),
        end=match.end(),
    )


def find_numbers(text: str) -> list[NumberPhrase]:
    return [phrase_at(text, m) for m in NUMBER_RE.finditer(text)]


def is_within(claimed: float, true: float, tolerance: float, relation: str) -> bool:
    """Ground-truth check: is the claim correct given its allowed rounding?"""
    if relation == "greater":
        return true > claimed
    if relation == "less":
        return true < claimed
    return abs(claimed - true) <= tolerance + 1e-9
