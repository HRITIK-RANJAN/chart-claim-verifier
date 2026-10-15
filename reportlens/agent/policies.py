"""Which tool next? (implementation.md §7.2)

    P0  AllToolsPolicy             all tools in a fixed order, decide once at the end
    P1  FixedOrderPolicy           cheapest first, stop as soon as the rule is clear
    P1b CalibrationInformedPolicy  order by calibrated error x cost for this chart type
    P2  LLMPolicy                  the LLM picks from a fixed menu; stops when the rule is clear

A policy only ever returns {"action": "read", "tool": t} or {"action": "handoff"}.
It cannot return a verdict.
"""
from __future__ import annotations

import json

from ..models.vlm import LLM, extract_json


class Policy:
    name = "policy"
    stops_early = True

    def next_action(self, state: dict) -> dict:
        raise NotImplementedError


class FixedOrderPolicy(Policy):
    name = "fixed_order"

    def __init__(self, order: list[str]):
        self.order = order

    def next_action(self, state):
        for t in self.order:
            if t in state["available"]:
                return {"action": "read", "tool": t}
        return {"action": "handoff", "reason": "no tools left"}


class AllToolsPolicy(FixedOrderPolicy):
    name = "all_tools"
    stops_early = False


class CalibrationInformedPolicy(Policy):
    """Free (already-paid) tools first, then lowest calibrated error x cost for the chart type."""
    name = "calibration_informed"

    def __init__(self, tool_error: dict[str, dict[str, float]], costs: dict[str, float]):
        self.tool_error, self.costs = tool_error, costs

    def next_action(self, state):
        avail = state["available"]
        if not avail:
            return {"action": "handoff", "reason": "no tools left"}
        errs = self.tool_error.get(state["chart_type"]) or self.tool_error.get("*", {})
        free = [t for t in avail if t in state["cached_for_free"]]
        pool = free or avail
        best = min(pool, key=lambda t: errs.get(t, 1.0) * (0.1 if t in free else self.costs.get(t, 1.0)))
        return {"action": "read", "tool": best}


CONTROLLER_PROMPT = """You control the measurement step of a chart-claim checker. Measurements come from tools;
a fixed rule (not you) decides whether the claim matches the chart. Your only job is to choose the next
measurement, or to hand the claim to the TA if more measurements will not help.

Measurement tools you may use: {tools}
Other tools that exist in this environment (the grading system uses them; you may NOT): {lms}

Current state. "situation" describes this chart. "evidence" is what was MEASURED for each tool on
charts like this one: success = share of reads that return a value, median_error = typical error as a
fraction of the axis range, big_error = share of returned values that are off by more than 5% of the
axis (silent mistakes). Base your choice on this evidence and on the costs (seconds), and prefer a
tool that is likely to make different mistakes from the readings you already have.
{state}

Reply with JSON only, one of:
  {{"action": "read", "tool": "<one of the available tools>"}}
  {{"action": "handoff", "reason": "<short reason>"}}"""


class LLMPolicy(Policy):
    name = "llm"

    def __init__(self, llm: LLM, tool_descriptions: dict[str, str], lms_catalog: dict[str, str],
                 fallback: Policy):
        self.llm, self.tool_descriptions, self.lms_catalog, self.fallback = llm, tool_descriptions, lms_catalog, fallback
        self.invalid = 0

    def next_action(self, state):
        tools = ", ".join(f"{t} ({self.tool_descriptions.get(t, '')}, cost {state['costs'].get(t, '?')})"
                          for t in state["available"])
        lms = ", ".join(f"{k} ({v})" for k, v in self.lms_catalog.items())
        prompt = CONTROLLER_PROMPT.format(tools=tools or "none", lms=lms, state=json.dumps(state, indent=1))
        raw = self.llm.generate(prompt, max_new_tokens=80)[0]
        try:
            a = extract_json(raw)
            if a.get("action") == "handoff":
                return {"action": "handoff", "reason": str(a.get("reason", ""))[:200], "raw": raw}
            if a.get("action") == "read" and a.get("tool") in state["available"]:
                return {"action": "read", "tool": a["tool"], "raw": raw}
            # anything else: a forbidden LMS tool, an unknown tool, a verdict ...
            out = self.fallback.next_action(state)
            out.update({"invalid": a, "raw": raw})
            if a.get("tool") in self.lms_catalog or a.get("action") in self.lms_catalog:
                out["forbidden"] = a.get("tool") or a.get("action")
            self.invalid += 1
            return out
        except (ValueError, AttributeError):
            self.invalid += 1
            out = self.fallback.next_action(state)
            out.update({"invalid": "unparseable", "raw": raw})
            return out


TOOL_DESCRIPTIONS = {
    "ocr_pixel": "OCR of axis labels + pixel measurement; classical, no model",
    "deplot": "DePlot chart-to-table model",
    "vlm_table": "vision-language model converts the chart to a table",
    "vlm_crop": "vision-language model reads one value from a zoomed crop",
    "sim_deplot": "simulated chart-to-table tool",
    "sim_vlm_table": "simulated VLM table tool",
    "sim_vlm_crop": "simulated VLM crop reader",
}
