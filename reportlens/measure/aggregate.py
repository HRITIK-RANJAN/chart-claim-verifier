"""Combine readings (implementation.md §6.6).

The disagreement never moves the estimate; it only sets how wide the margin is.
"""
from __future__ import annotations

from statistics import median


def estimate(values: list[float]) -> float:
    return float(median(values))


def disagreement(values: list[float]) -> float:
    """Median absolute deviation. With two readings this is |v1 - v2| / 2."""
    m = estimate(values)
    return float(median(abs(v - m) for v in values))


def derived_value(claim_type: str, operands: list[float]) -> float | None:
    """Python arithmetic for derived claims, applied to ONE tool's readings.

    Each tool's operand readings are turned into that tool's value for the
    claim; only then are tools combined. So one calibration covers all types.
    """
    if claim_type == "point":
        return operands[0]
    if claim_type == "difference":
        return operands[0] - operands[1]
    if claim_type == "relative_change":
        a, b = operands
        if abs(a) < 1e-9:
            return None
        return (b - a) / abs(a) * 100.0
    raise ValueError(f"unknown claim type {claim_type!r}")
