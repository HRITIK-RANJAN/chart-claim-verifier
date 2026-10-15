"""The claim loop (implementation.md §5.2, §7.1).

    Measure -> Combine -> Decide -> (clear: stop) / (unclear: controller picks next tool)

At least `min_readings` readings before any decision; at most `max_tool_calls`
logical tool calls per claim. A table tool costs one call per figure per
report (later lookups come from memory); a point tool costs one call per value.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from ..calibration.store import CalibrationTable
from ..decide.rule import RuleConfig, decide
from ..measure.aggregate import derived_value
from ..schemas import ClaimSpec, Decision, Figure, PointQuery, Reading
from ..tools.base import TableTool, Tool
from .memory import ReportMemory
from .policies import Policy


@dataclass
class ClaimResult:
    status: str
    decision: Decision
    tool_values: dict[str, float] = field(default_factory=dict)
    readings: list[Reading] = field(default_factory=list)
    steps: list[dict] = field(default_factory=list)
    calls: int = 0
    blocked: list[str] = field(default_factory=list)


class ClaimController:
    def __init__(self, tools: dict[str, Tool], policy: Policy, table: CalibrationTable, rc: RuleConfig,
                 max_tool_calls: int = 8, profile: dict | None = None):
        self.tools, self.policy, self.table, self.rc, self.max_calls = tools, policy, table, rc, max_tool_calls
        self.profile = profile            # measured tool performance (evaluation/tool_profile.py)

    def _seconds(self, name: str, n_operands: int) -> float:
        """Measured cost of one call (falls back to the tool's own estimate)."""
        c = (self.profile or {}).get("cost", {}).get(name) or {}
        if isinstance(self.tools[name], TableTool):
            return c.get("seconds_per_figure") or self.tools[name].cost
        return (c.get("seconds_per_read") or self.tools[name].cost) * n_operands

    def _state(self, claim: ClaimSpec, fig: Figure, res: ClaimResult, mem: ReportMemory, tried: set[str],
               last: Decision | None, situation=None) -> dict:
        series = [s for s, _ in claim.operands()]
        scopes = (self.profile or {}).get("failure_scope") or {}
        blocked = {t: c for t in self.tools if t not in tried
                   and (c := mem.blocked(t, fig.figure_id, series, scopes.get(t) or {})) is not None}
        available = [t for t in self.tools if t not in tried and t not in blocked]
        free = [t for t in available if (t, fig.figure_id) in mem.tables_used]
        n_ops = len(claim.operands())
        # a table tool is paid once per figure: share its cost among the claims still waiting on this figure
        waiting = max(1, mem.pending.get(fig.figure_id, 1))
        shared = {t: waiting for t in available if isinstance(self.tools[t], TableTool) and t not in free and waiting > 1}
        state = {
            "claim": claim.sentence, "chart_type": fig.chart_type,
            "readings": [{"tool": t, "value": round(v, 4)} for t, v in res.tool_values.items()],
            "failed_here": sorted({t for (t, f, _, _) in mem.failures if f == fig.figure_id}),
            "blocked": blocked, "shared_by": shared,
            "available": available, "all_tools": list(self.tools), "cached_for_free": free,
            "costs": {t: (0.0 if t in free else round(self._seconds(t, n_ops) / shared.get(t, 1), 2)) for t in available},
            "calls_left": self.max_calls - res.calls,
        }
        from .situation import x_on_tick
        state["x_on_tick"] = x_on_tick(fig, [x for _, x in claim.operands()])
        if situation is not None:
            state["situation"] = situation.key
            state["situation_text"] = situation.describe()
            if self.profile:
                sit = self.profile["situations"].get(situation.key) or self.profile["situations"].get("*", {})
                state["evidence"] = {t: {k: (round(v, 4) if isinstance(v, float) else v)
                                         for k, v in (sit.get(t) or {}).items() if k != "top_failures"}
                                     for t in available}
        if last is not None and last.gap is not None:
            state["gap_vs_margins"] = (f"{last.verdict.lower()} (gap {last.gap:.3g}, rounding {claim.tolerance:.3g}, "
                                       f"accept <= {claim.tolerance + last.margin_accept:.3g}, "
                                       f"flag > {claim.tolerance + last.margin_flag:.3g})")
        return state

    def _cost(self, name: str, fig: Figure, n_operands: int, mem: ReportMemory) -> int:
        tool = self.tools[name]
        if isinstance(tool, TableTool):
            return 0 if (name, fig.figure_id) in mem.tables_used else 1
        return n_operands

    def run(self, claim: ClaimSpec, fig: Figure, mem: ReportMemory) -> ClaimResult:
        from .situation import observe
        res = ClaimResult(status="TOO_FEW", decision=Decision(verdict="NOT_SURE", reason="no readings"))
        tried: set[str] = set()
        span = fig.y_span or 1.0
        last: Decision | None = None
        ops = claim.operands()
        situation = observe(fig)

        while True:
            state = self._state(claim, fig, res, mem, tried, last, situation)
            if not state["available"]:
                break
            action = self.policy.next_action(state)
            step = {"available": state["available"], "readings_so_far": len(res.tool_values), "action": action}
            res.steps.append(step)
            if action.get("forbidden"):
                res.blocked.append(action["forbidden"])
            if action["action"] != "read":
                if action.get("why"):
                    res.decision.reason = "handed off: " + action["why"]
                break
            name = action["tool"]
            cost = self._cost(name, fig, len(ops), mem)
            if res.calls + cost > self.max_calls:
                step["skipped"] = "over budget"
                break
            tried.add(name)
            tool = self.tools[name]
            reads = [tool.read(fig, PointQuery(series=s, x=x)) for s, x in ops]
            res.readings.extend(reads)
            res.calls += cost
            mem.calls[name] += cost
            if isinstance(tool, TableTool):
                if (name, fig.figure_id) in mem.tables_used:
                    mem.calls_saved += 1
                mem.tables_used.add((name, fig.figure_id))
            bad = [r for r in reads if not r.ok]
            if bad:
                for r in bad:
                    mem.note_failure(name, fig.figure_id, r.query.series if r.query else "", r.error or "error")
                step["result"] = f"error: {bad[0].error}"
                continue
            v = derived_value(claim.claim_type, [r.value for r in reads])
            if v is None:
                step["result"] = "error: derived value undefined"
                continue
            res.tool_values[name] = v
            step["result"] = round(v, 4)
            if len(res.tool_values) >= self.rc.min_readings:
                res.status, last = decide(claim, res.tool_values, fig.chart_type, span, self.table, self.rc)
                res.decision = last
                step["status"] = res.status
                if self.policy.stops_early and res.status in ("CONSISTENT", "MISMATCH_CANDIDATE"):
                    break

        if not self.policy.stops_early and len(res.tool_values) >= self.rc.min_readings:
            res.status, res.decision = decide(claim, res.tool_values, fig.chart_type, span, self.table, self.rc)
        if res.status in ("UNCLEAR", "TOO_FEW"):
            res.decision.verdict = "NOT_SURE"
            if res.status == "TOO_FEW" and not res.decision.reason.startswith("handed off"):
                res.decision.reason = f"only {len(res.tool_values)} successful reading(s)"
        return res
