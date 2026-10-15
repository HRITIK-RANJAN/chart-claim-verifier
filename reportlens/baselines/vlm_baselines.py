"""Baselines B1–B4 (implementation.md §6.9). All use the same VLM as our system.

To compare only the *decision*, every baseline starts from our traces: the same
sentence, the same parsed claim and the same located figure. B5 (uncalibrated
margin) needs no model and lives in evaluation/sweep.py.

    B1 direct          figure + sentence -> SUPPORTED / REFUTED
    B2 direct + conf   same, abstain if stated confidence < tau (tau swept for matched coverage)
    B3 majority vote   n samples at T>0; abstain unless at least `agree` of them agree
    B4 tools, no rule  the model sees the SAME tool readings our rule sees, and decides itself
"""
from __future__ import annotations

import json
from collections import Counter

from ..models.vlm import LLM, extract_json
from ..schemas import ClaimTrace, Decision, Report

DIRECT = """Here is a chart from a student's lab report and a sentence from the same report.

Sentence: "{sentence}"

Does the chart support the number in the sentence? Allow for normal rounding.
Answer only with JSON: {{"verdict": "SUPPORTED" or "REFUTED", "confidence": <0-100>}}"""

WITH_TOOLS = """A sentence from a student's lab report makes a claim about a chart.

Sentence: "{sentence}"
Claimed value: {claimed} (allowed rounding: {tol})
Values measured from the chart by different tools: {readings}

Is the claim correct? Answer only with JSON: {{"verdict": "SUPPORTED" or "REFUTED"}}"""


def _verdict(raw: str) -> tuple[str | None, float]:
    try:
        d = extract_json(raw)
        v = str(d.get("verdict", "")).upper()
        conf = float(d.get("confidence", 100))
    except (ValueError, AttributeError, TypeError):
        return None, 0.0
    if v.startswith("SUPPORT"):
        return "CONSISTENT", conf
    if v.startswith("REFUT"):
        return "MISMATCH", conf
    return None, 0.0


def _figure_path(report: Report, figure_id: str | None) -> str | None:
    f = next((f for f in report.figures if f.figure_id == figure_id), None)
    return f.image_path if f else None


def _decidable(t: ClaimTrace) -> bool:
    return t.claim is not None and t.figure_id is not None and t.decision.verdict not in ("NO_FIGURE", "SKIPPED")


def _with(t: ClaimTrace, verdict: str, reason: str, conf: float | None = None) -> ClaimTrace:
    d = Decision(verdict=verdict, reason=reason, p_value=None if conf is None else 1 - conf / 100)
    return t.model_copy(update={"decision": d, "tool_values": {}, "controller_steps": []})


def b1_direct(traces, reports: dict[str, Report], llm: LLM) -> list[ClaimTrace]:
    out = []
    for t in traces:
        if not _decidable(t):
            out.append(t)
            continue
        img = _figure_path(reports[t.report_id], t.figure_id)
        v, conf = _verdict(llm.generate(DIRECT.format(sentence=t.sentence), [img], max_new_tokens=40)[0])
        out.append(_with(t, v or "CONSISTENT", "B1 direct" + ("" if v else " (unparseable -> default)"), conf))
    return out


def b2_threshold(b1_traces: list[ClaimTrace], tau: float) -> list[ClaimTrace]:
    """Abstain when the stated confidence is below tau. Re-uses B1 answers: no new model calls."""
    out = []
    for t in b1_traces:
        if t.decision.reason.startswith("B1") and t.decision.p_value is not None and (1 - t.decision.p_value) * 100 < tau:
            out.append(t.model_copy(update={"decision": Decision(verdict="NOT_SURE", reason=f"B2 conf<{tau}")}))
        else:
            out.append(t)
    return out


def b3_majority(traces, reports: dict[str, Report], llm: LLM, n: int = 5, agree: int = 5,
                temperature: float = 0.7) -> list[ClaimTrace]:
    out = []
    for t in traces:
        if not _decidable(t):
            out.append(t)
            continue
        img = _figure_path(reports[t.report_id], t.figure_id)
        votes = [_verdict(r)[0] for r in llm.generate(DIRECT.format(sentence=t.sentence), [img],
                                                      temperature=temperature, max_new_tokens=40, n=n)]
        (top, k), = Counter(v for v in votes if v).most_common(1) or [(None, 0)]
        out.append(_with(t, top if top and k >= agree else "NOT_SURE", f"B3 votes={dict(Counter(votes))}"))
    return out


def b4_tools_no_rule(all_tools_traces, llm: LLM) -> list[ClaimTrace]:
    """Needs traces from the all-tools policy (P0), so it sees exactly our readings."""
    out = []
    for t in all_tools_traces:
        if not _decidable(t) or not t.tool_values:
            out.append(t)
            continue
        prompt = WITH_TOOLS.format(sentence=t.sentence, claimed=t.claim.claimed_value, tol=t.claim.tolerance,
                                   readings=json.dumps({k: round(v, 4) for k, v in t.tool_values.items()}))
        v, _ = _verdict(llm.generate(prompt, max_new_tokens=30)[0])
        out.append(t.model_copy(update={"decision": Decision(verdict=v or "CONSISTENT", reason="B4 tools, no rule")}))
    return out
