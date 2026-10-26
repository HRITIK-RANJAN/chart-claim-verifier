"""Metrics (implementation.md §12.1).

Main:   wrong-flag rate, coverage, coverage at a target wrong-flag rate,
        catch rate by planted error size, detection limit (delta_50)
Checks: margin check (true value inside the flag margin), realised wrong-flag rate
Per capability: retrieval, parsing, tool calls, hand-offs, error attribution
"""
from __future__ import annotations

import math
import random
import re
from collections import Counter, defaultdict
from dataclasses import dataclass

from ..schemas import ClaimTrace

DECIDED = ("CONSISTENT", "MISMATCH", "NO_FIGURE")


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip().lower())


@dataclass
class Row:
    report_id: str
    sentence: str
    gold: str                   # correct | error | no_figure | skip | unknown
    kind: str
    delta: float | None
    claim_type: str | None
    chart_type: str
    verdict: str
    true_value: float | None
    estimate: float | None
    margin_flag: float | None
    figure_true: str | None
    figure_pred: str | None
    parse_ok: dict
    tool_calls: int
    trace: ClaimTrace


def gold_lookup(truths: list[dict]) -> dict[tuple[str, str], dict]:
    return {(t["report_id"], norm(c["sentence"])): c for t in truths for c in t["claims"]}


def join(traces: list[ClaimTrace], truths: list[dict]) -> list[Row]:
    gold = gold_lookup(truths)
    rows = []
    for t in traces:
        g = gold.get((t.report_id, norm(t.sentence)))
        if g is None:
            if t.decision.verdict == "SKIPPED":
                continue                         # e.g. "Figure 1 shows ..." lead-in sentences
            g = {"gold": "unknown", "kind": "unknown"}
        parse_ok = {}
        if t.claim and g.get("claim_type"):
            c = t.claim
            parse_ok = {
                "claim_type": c.claim_type == g["claim_type"],
                "series": norm(c.series) == norm(g["series"]),
                "x": norm(c.x) == norm(g["x"]),
                "value": c.claimed_value is not None and g.get("claimed_value") is not None
                and abs(c.claimed_value - g["claimed_value"]) < 1e-9,
                "tolerance": g.get("tolerance") is None or abs(c.tolerance - g["tolerance"]) < 1e-9,
            }
        rows.append(Row(t.report_id, t.sentence, g["gold"], g["kind"], g.get("delta"), g.get("claim_type"),
                        t.chart_type, t.decision.verdict, g.get("true_value"), t.decision.estimate,
                        t.decision.margin_flag, g.get("figure_id"), t.figure_id, parse_ok, t.tool_calls, t))
    return rows


def _rate(num: int, den: int) -> float:
    return num / den if den else float("nan")


def wrong_flag_rate(rows: list[Row]) -> float:
    flagged = [r for r in rows if r.verdict == "MISMATCH"]
    return _rate(sum(r.gold != "error" for r in flagged), len(flagged))


def coverage(rows: list[Row]) -> float:
    claims = [r for r in rows if r.gold in ("correct", "error", "no_figure")]
    return _rate(sum(r.verdict in DECIDED for r in claims), len(claims))


def catch_rates(rows: list[Row]) -> dict[float, float]:
    by = defaultdict(list)
    for r in rows:
        if r.gold == "error" and r.kind == "planted" and r.delta is not None:
            by[round(abs(r.delta), 4)].append(r.verdict == "MISMATCH")
    return {d: sum(v) / len(v) for d, v in sorted(by.items())}


def detection_limit(rates: dict[float, float], level: float = 0.5) -> float | None:
    """Smallest planted error size caught at least `level` of the time (and every larger one too)."""
    sizes = sorted(rates)
    for i, d in enumerate(sizes):
        if all(rates[s] >= level for s in sizes[i:]):
            return d
    return None


def attribution(r: Row) -> str:
    """First step that went wrong for a wrong decision."""
    if r.gold in ("correct", "error") and r.figure_true and r.figure_pred != r.figure_true:
        return "retrieval"
    if r.gold == "no_figure" and r.verdict != "NO_FIGURE":
        return "retrieval"
    if r.parse_ok and not all(r.parse_ok.values()):
        return "parse"
    if r.true_value is not None and r.estimate is not None and r.margin_flag is not None \
            and abs(r.true_value - r.estimate) > r.margin_flag:
        return "measure"
    return "decide"


def is_wrong(r: Row) -> bool:
    return (r.verdict == "MISMATCH" and r.gold != "error") or (r.verdict == "CONSISTENT" and r.gold != "correct") \
        or (r.verdict == "NO_FIGURE" and r.gold != "no_figure")


def summarize(rows: list[Row]) -> dict:
    claims = [r for r in rows if r.gold in ("correct", "error", "no_figure")]
    decided = [r for r in claims if r.verdict in DECIDED]
    real = [r for r in claims if r.gold in ("correct", "error")]
    in_margin = [abs(r.true_value - r.estimate) <= r.margin_flag for r in real
                 if r.true_value is not None and r.estimate is not None and r.margin_flag not in (None, math.inf)]
    parsed = [r for r in real if r.parse_ok]
    rates = catch_rates(rows)
    traces = [r.trace for r in claims]
    tool_ok, tool_n = Counter(), Counter()
    for t in traces:
        for rd in t.readings:
            tool_n[rd.tool] += 1
            tool_ok[rd.tool] += rd.ok
    recov_n = recov_ok = 0
    for t in traces:
        steps = t.controller_steps
        for i, s in enumerate(steps[:-1]):
            if str(s.get("result", "")).startswith("error"):
                recov_n += 1
                recov_ok += steps[i + 1]["action"].get("action") == "read"
    wrong = [r for r in rows if is_wrong(r)]
    return {
        "n_claims": len(claims),
        "n_flagged": sum(r.verdict == "MISMATCH" for r in rows),
        "wrong_flag_rate": wrong_flag_rate(rows),
        "coverage": coverage(rows),
        "accuracy_when_decided": _rate(sum(not is_wrong(r) for r in decided), len(decided)),
        "handoff_rate": _rate(sum(r.verdict == "NOT_SURE" for r in claims), len(claims)),
        "catch_rate_by_delta": rates,
        "detection_limit_delta50": detection_limit(rates),
        "missed_errors": _rate(sum(r.verdict == "CONSISTENT" for r in real if r.gold == "error"),
                               sum(r.gold == "error" for r in real)),
        "margin_check": _rate(sum(in_margin), len(in_margin)),
        "retrieval_top1": _rate(sum(r.figure_pred == r.figure_true for r in real), len(real)),
        "no_figure_accuracy": _rate(sum(r.verdict == "NO_FIGURE" for r in claims if r.gold == "no_figure"),
                                    sum(r.gold == "no_figure" for r in claims)),
        "finder_false_positives": sum(r.gold == "skip" and r.verdict != "SKIPPED" for r in rows),
        "flags_on_non_claims": sum(r.gold == "skip" and r.verdict == "MISMATCH" for r in rows),
        "parse_accuracy": {f: _rate(sum(r.parse_ok[f] for r in parsed), len(parsed))
                           for f in ("claim_type", "series", "x", "value", "tolerance")} if parsed else {},
        "tool_calls_per_claim": _rate(sum(r.tool_calls for r in real), len(real)),
        "tool_success_rate": {t: tool_ok[t] / tool_n[t] for t in sorted(tool_n)},
        "recovery_rate": _rate(recov_ok, recov_n),
        "error_attribution": dict(Counter(attribution(r) for r in wrong)),
        "blocked_action_attempts": sum(len(r.trace.blocked_actions) for r in rows),
        # agent decisions
        "parse_escalations_to_llm": sum(any(st.get("decision") == "escalate to LLM parser" for st in r.trace.stages)
                                        for r in rows),
        "reparse_after_no_figure": sum(any(st.get("decision") == "re-parse with LLM" for st in r.trace.stages)
                                       for r in rows),
        "policy_agrees_with_p3": _rate(sum(s["action"].get("agrees_with_p3") is True for r in claims
                                          for s in r.trace.controller_steps),
                                       sum("agrees_with_p3" in s["action"] for r in claims for s in r.trace.controller_steps)),
        "repairs": sum(s["action"].get("action") == "repair" for r in claims for s in r.trace.controller_steps),
        "early_handoffs": sum(r.trace.decision.reason.startswith("handed off") for r in claims),
        "handoff_reasons": dict(Counter(_reason(r.trace.decision.reason) for r in claims if r.verdict == "NOT_SURE")),
    }


def _reason(reason: str) -> str:
    for key in ("handed off", "ambiguous figure", "readings too spread", "between the two margins",
                "did not survive", "only", "could not parse"):
        if reason.startswith(key) or key in reason:
            return key
    return reason[:40]


def bootstrap(rows: list[Row], stat, n: int = 500, seed: int = 0) -> tuple[float, float]:
    """95% interval, resampling REPORTS (claims in one report are related)."""
    by = defaultdict(list)
    for r in rows:
        by[r.report_id].append(r)
    ids = list(by)
    rng = random.Random(seed)
    vals = []
    for _ in range(n):
        sample = [r for i in (rng.choice(ids) for _ in ids) for r in by[i]]
        v = stat(sample)
        if v == v:
            vals.append(v)
    if not vals:
        return float("nan"), float("nan")
    vals.sort()
    return vals[int(0.025 * len(vals))], vals[int(0.975 * len(vals)) - 1]
