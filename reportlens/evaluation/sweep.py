"""Re-decide from stored readings, without calling any tool (design principle 3).

Valid for traces whose readings do not depend on the threshold, i.e. the
all-tools policy (P0). Used for the coverage-vs-wrong-flag curve and for
"coverage at a 10% wrong-flag rate" (E1), and for baseline B5.
"""
from __future__ import annotations

from ..calibration.store import CalibrationTable, ConstantTable
from ..decide.rule import RuleConfig, batch_check, decide
from ..schemas import ClaimTrace, Decision
from .metrics import coverage, join, wrong_flag_rate


def redecide(traces: list[ClaimTrace], table: CalibrationTable, rc: RuleConfig,
             use_batch: bool = False) -> list[ClaimTrace]:
    out = []
    for t in traces:
        if t.claim is None or t.decision.verdict in ("NO_FIGURE", "SKIPPED") or not t.tool_values:
            out.append(t)
            continue
        if len(t.tool_values) < rc.min_readings:
            out.append(t.model_copy(update={"decision": Decision(verdict="NOT_SURE", reason="too few readings")}))
            continue
        status, d = decide(t.claim, t.tool_values, t.chart_type, t.y_span or 1.0, table, rc)
        if status == "UNCLEAR":
            d.verdict = "NOT_SURE"
        out.append(t.model_copy(update={"decision": d}))
    return batch_check(out, rc.alpha) if use_batch else out


def curve(traces: list[ClaimTrace], truths: list[dict], settings: list[tuple[str, CalibrationTable, RuleConfig, bool]]):
    """One point (wrong-flag rate, coverage) per setting."""
    pts = []
    for label, table, rc, use_batch in settings:
        rows = join(redecide(traces, table, rc, use_batch), truths)
        pts.append({"setting": label, "wrong_flag_rate": wrong_flag_rate(rows), "coverage": coverage(rows),
                    "n_flagged": sum(r.verdict == "MISMATCH" for r in rows)})
    return pts


def coverage_at(points: list[dict], target: float = 0.10) -> dict | None:
    """Highest coverage among settings whose wrong-flag rate is at or below the target."""
    ok = [p for p in points if p["wrong_flag_rate"] == p["wrong_flag_rate"] and p["wrong_flag_rate"] <= target]
    return max(ok, key=lambda p: p["coverage"]) if ok else None


def ours_settings(table: CalibrationTable, base: RuleConfig, levels=(0.5, 0.6, 0.7, 0.8, 0.9, 0.95, 0.975, 0.99)):
    out = []
    for lv in levels:
        rc = RuleConfig(lv, min(base.level_accept, lv), base.eps, base.min_readings, base.alpha, base.max_accept_margin)
        out.append((f"ours level={lv}", table, rc, False))
    for a in (0.05, 0.10, 0.20):
        rc = RuleConfig(base.level_flag, base.level_accept, base.eps, base.min_readings, a, base.max_accept_margin)
        out.append((f"ours+BH alpha={a}", table, rc, True))
    return out


def b5_settings(base: RuleConfig, factors=(0.5, 1, 2, 3, 5, 8, 12)):
    return [(f"B5 factor={f}", ConstantTable(f, f / 2), base, False) for f in factors]
