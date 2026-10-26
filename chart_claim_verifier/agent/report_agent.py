"""The report agent / planner (implementation.md §7.1).

    ingest -> memory -> find number sentences -> parse -> locate figure
    -> order claims so ones sharing a figure run together -> claim loop each

The batch check (BH across a whole assignment) and posting to the LMS happen
afterwards, in `finalize`, because BH needs every report of the batch.
"""
from __future__ import annotations

import re
from collections import Counter
from pathlib import Path
from typing import Callable, Literal

from ..claims.finder import is_candidate, strip_figure_refs
from ..claims.parser import ParseError
from ..claims.tolerance import find_numbers
from ..decide.rule import batch_check
from ..ingest.pdf_parser import parse_pdf
from ..lms.guard import ActionGuard
from ..retrieval.figure_index import FigureIndex
from ..schemas import ClaimTrace, Decision, Report
from .controller import ClaimController
from .memory import ReportMemory

RetrievalMode = Literal["ours", "nearest", "oracle"]
AMBIGUOUS_RULES = ("either", "top", "both", "never")


def ambiguous_accepts(rule: str, verdicts: list[str]) -> bool:
    """Two figures fit the sentence: may the claim be accepted? (Never flagged: one of the figures is the wrong one.)

    verdicts: the claim's verdict on each candidate figure, best-ranked first.
      either  accept if the claim matches either figure
      top     accept only if it matches the best-ranked figure
      both    accept only if it matches both
      never   always hand to the TA
    """
    ok = [v == "CONSISTENT" for v in verdicts]
    return {"either": any(ok), "top": bool(ok) and ok[0], "both": bool(ok) and all(ok), "never": False}[rule]


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip().lower())


class ReportAgent:
    """Runs every stage for one report and records WHY each decision was taken.

    Parse:   the rule parser first (cheap, exact); the LLM parser only when there is
             evidence the rules are not enough -- no known phrasing, or the parsed
             names appear in no figure (possible mis-parse).
    Figure:  explicit "Figure N", else best text match that really shows the series;
             two close candidates -> check both, never flag.
    Measure: the controller + policy (P3 decides from the measured tool profile).
    Decide:  the fixed rule.
    """

    def __init__(self, parser, controller: ClaimController, retrieval: RetrievalMode = "ours",
                 oracle: Callable[[str, str], str | None] | None = None, ref_bonus: float = 10.0,
                 vocab_match: int = 80, llm_parser=None, ambiguous_rule: str = "either"):
        if ambiguous_rule not in AMBIGUOUS_RULES:
            raise ValueError(f"unknown ambiguous_rule {ambiguous_rule!r}")
        self.ambiguous_rule = ambiguous_rule
        self.parser, self.controller, self.retrieval = parser, controller, retrieval
        self.llm_parser = llm_parser    # escalation target; None = rules only
        self.oracle = oracle            # (report_id, sentence) -> true figure_id; ablation only
        self.ref_bonus, self.vocab_match = ref_bonus, vocab_match

    def ingest(self, pdf_path: str | Path, work_dir: str | Path, report_id: str | None = None) -> Report:
        return parse_pdf(pdf_path, work_dir, report_id)

    # ------------------------------------------------------------------ planning
    def plan(self, mem: ReportMemory) -> dict:
        """Look at every figure once and decide which tools are worth using on it."""
        from .situation import observe
        policy = self.controller.policy
        for f in mem.report.figures:
            sit = observe(f)
            entry = {"situation": sit.key, "looks_like": sit.describe()}
            if hasattr(policy, "assess"):
                a = policy.assess(sit.key, list(self.controller.tools))
                entry["callable_tools"] = a["callable"]
                entry["skipped_tools"] = {t: (None if r is None else round(r, 2)) for t, r in a["skipped"].items()}
                entry["cross_check_pairs"] = a["good_pairs"]
            mem.plan[f.figure_id] = entry
        return mem.plan

    # ------------------------------------------------------------------ parse stage
    def _parse(self, sent, context: str, stages: list) -> tuple[object, str]:
        """Returns (claim | None | 'error', parser name)."""
        claim = self.parser.parse(sent.text, sent.sentence_id, context)
        if claim is not None:
            stages.append({"stage": "parse", "decision": "rule parser",
                           "why": f"sentence matches a known '{claim.claim_type}' phrasing"})
            return claim, "rule"
        if self.llm_parser is None:
            stages.append({"stage": "parse", "decision": "not a chart claim",
                           "why": "no known phrasing and no LLM parser available"})
            return None, "rule"
        stages.append({"stage": "parse", "decision": "escalate to LLM parser",
                       "why": "the sentence has a result-like number but no phrasing the rules know"})
        try:
            return self.llm_parser.parse(sent.text, sent.sentence_id, context), "llm"
        except ParseError:
            return "error", "llm"

    # ------------------------------------------------------------------ main loop
    def run(self, report: Report) -> tuple[list[ClaimTrace], ReportMemory]:
        mem = ReportMemory(report, FigureIndex(report.figures, self.ref_bonus, self.vocab_match))
        self.plan(mem)
        context = mem.context()
        planned, traces = [], []
        for sent in report.sentences:
            if not find_numbers(strip_figure_refs(sent.text)):
                continue                                   # no number: nothing to check
            base = dict(report_id=report.report_id, sentence_id=sent.sentence_id, sentence=sent.text,
                        policy=self.controller.policy.name)
            if not is_candidate(sent.text):
                traces.append(ClaimTrace(**base, decision=Decision(verdict="SKIPPED", reason="not a result claim")))
                continue
            stages: list[dict] = []
            claim, used = self._parse(sent, context, stages)
            if claim == "error":
                traces.append(ClaimTrace(**base, stages=stages,
                                         decision=Decision(verdict="NOT_SURE", reason="could not parse")))
                continue
            if claim is None:
                traces.append(ClaimTrace(**base, stages=stages,
                                         decision=Decision(verdict="SKIPPED", reason="parser: not a chart claim")))
                continue
            figs, cands = self._locate(claim, sent, mem)
            if not figs and used == "rule" and self.llm_parser is not None and self.retrieval == "ours":
                stages.append({"stage": "figure", "decision": "re-parse with LLM",
                               "why": f"no figure shows '{claim.series}' at '{claim.x}': possibly a mis-parse"})
                try:
                    again = self.llm_parser.parse(sent.text, sent.sentence_id, context)
                except ParseError:
                    again = None
                if again is not None:
                    figs2, cands2 = self._locate(again, sent, mem)
                    if figs2:
                        claim, figs, cands = again, figs2, cands2
            if not figs:
                stages.append({"stage": "figure", "decision": "NO_FIGURE",
                               "why": f"no figure shows series '{claim.series}' at x '{claim.x}'"})
                traces.append(ClaimTrace(**base, claim=claim, figure_candidates=cands, stages=stages,
                                         decision=Decision(verdict="NO_FIGURE", reason="no figure shows this series / x")))
                continue
            stages.append(self._figure_note(claim, figs, cands, mem))
            planned.append((figs[0].figure_id, len(planned), base, claim, figs, cands, stages))

        mem.pending = Counter(p[0] for p in planned)       # claims waiting on each figure: shares a table tool's cost
        for fid0, _, base, claim, figs, cands, stages in sorted(planned, key=lambda p: (p[0], p[1])):
            key = _norm(claim.sentence)
            if key in mem.checked:                         # duplicate sentence: same answer, no calls
                old = mem.checked[key]
                traces.append(old.model_copy(update={"sentence_id": base["sentence_id"], "tool_calls": 0}))
                mem.pending[fid0] -= 1
                continue
            runs = [(f, self.controller.run(claim, f, mem)) for f in figs]
            mem.pending[fid0] -= 1
            fig, r = runs[0]
            figure_runs = {}
            if len(runs) > 1:
                # Two figures fit the sentence. Never flag; accept by the configured rule (agent.ambiguous_rule).
                figure_runs = {f.figure_id: {"verdict": x.decision.verdict, "estimate": x.decision.estimate,
                                             "gap": x.decision.gap, "margin_flag": x.decision.margin_flag}
                               for f, x in runs}
                if ambiguous_accepts(self.ambiguous_rule, [x.decision.verdict for _, x in runs]):
                    fig, r = next((f, x) for f, x in runs if x.decision.verdict == "CONSISTENT")
                else:
                    r.decision.verdict = "NOT_SURE"
                    r.decision.reason = "ambiguous figure: " + ", ".join(f.figure_id for f, _ in runs)
                r.calls = sum(x.calls for _, x in runs)
            stages = stages + [{"stage": "measure",
                                "decision": (f"repair {s['action']['tool']} ({s['action']['repair']})"
                                             if s["action"]["action"] == "repair"
                                             else s["action"].get("tool") or s["action"]["action"]),
                                "why": s["action"].get("why", ""), "result": s.get("result")} for s in r.steps]
            stages.append({"stage": "decide", "decision": r.decision.verdict, "why": r.decision.reason})
            tr = ClaimTrace(**base, claim=claim, figure_id=fig.figure_id, figure_candidates=cands,
                            chart_type=fig.chart_type, y_span=fig.y_span, tool_values=r.tool_values,
                            readings=r.readings, controller_steps=r.steps, decision=r.decision,
                            blocked_actions=r.blocked, tool_calls=r.calls, stages=stages, figure_runs=figure_runs)
            mem.checked[key] = tr
            traces.append(tr)
        order = {s.sentence_id: i for i, s in enumerate(report.sentences)}
        return sorted(traces, key=lambda t: order.get(t.sentence_id, 0)), mem

    @staticmethod
    def _figure_note(claim, figs, cands, mem) -> dict:
        if len(figs) > 1:
            return {"stage": "figure", "decision": "check both " + " and ".join(f.figure_id for f in figs),
                    "why": "two figures show this series with similar text-match scores"}
        f = figs[0]
        if claim.figure_hint is not None and f.number == claim.figure_hint:
            why = f"the sentence names Figure {claim.figure_hint}"
        else:
            why = f"best text match that shows '{claim.series}' (scores {cands[:3]})"
        plan = mem.plan.get(f.figure_id, {})
        if plan:
            why += f"; chart looks like: {plan.get('looks_like')}"
        return {"stage": "figure", "decision": f.figure_id, "why": why}

    def _locate(self, claim, sent, mem: ReportMemory):
        if self.retrieval == "oracle" and self.oracle:
            fid = self.oracle(sent.report_id, sent.text)
            return ([mem.figure(fid)] if fid else []), []
        if self.retrieval == "nearest":
            f = mem.figure(sent.nearest_figure_id) if sent.nearest_figure_id else None
            return ([f] if f else []), []
        return mem.index.locate(claim)


def finalize(traces: list[ClaimTrace], guard: ActionGuard | None, alpha: float = 0.10,
             use_batch_check: bool = True) -> list[ClaimTrace]:
    """Batch check across the assignment, then post MISMATCH / NOT_SURE to the TA review list."""
    out = batch_check(traces, alpha) if use_batch_check else traces
    if guard is not None:
        for t in out:
            for forbidden in t.blocked_actions:              # LLM attempts are routed through the guard
                guard.execute(forbidden, caller="llm_controller", report_id=t.report_id)
            if t.decision.verdict in ("MISMATCH", "NOT_SURE"):
                guard.execute("post_flag", caller="decision_rule", report_id=t.report_id,
                              claim_id=t.sentence_id, verdict=t.decision.verdict, evidence=evidence_card(t))
    return out


def evidence_card(t: ClaimTrace) -> dict:
    """What the TA sees next to a flag."""
    d = t.decision
    return {"sentence": t.sentence, "figure": t.figure_id,
            "claimed": t.claim.claimed_value if t.claim else None,
            "allowed_rounding": t.claim.tolerance if t.claim else None,
            "readings": {k: round(v, 4) for k, v in t.tool_values.items()},
            "estimate": d.estimate, "error_margin": d.margin_flag, "p_value": d.p_value, "why": d.reason}
