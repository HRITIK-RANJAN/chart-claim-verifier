"""P3 -- the informed measurement policy: decide from MEASURED tool performance.

Before choosing a tool the agent looks at
  * the situation of this chart (agent/situation.py): e.g. "line|hard"
  * whether the claim's x value has its own tick label (table tools only
    return labelled x values)
  * the tool profile measured on the calibration charts for that situation
    (evaluation/tool_profile.py)

Measurements (each one comes with the number of points AND charts behind it):

  answers(t)  = measured share of reads where t returned a value, for this kind of
                x value. A refusal costs time but cannot mislead.
  trust(t)    = 1 - big_error(t): share of t's returned values that were right.
  wrong_when_agree(a, b)
              = share of calibration points where a and b agreed but were both
                wrong. This is what can produce a wrong verdict: the rule only
                accepts or flags when readings agree, so a tool that is often
                wrong ALONE is still a useful second opinion as long as its
                mistakes are not the same as the first tool's.

Rules (each one cites its numbers in the trace):
  * a tool that answers less than min_answer of the time here is not called
  * a tool whose agreement with a tool already read is wrong more than
    max_wrong_agree of the time is not used as a cross-check for it
  * if no pair of callable tools can cross-check each other, the claim goes to
    the TA straight away (no model time spent)
  * before the first reading, choose the best PAIR (a reading is only worth paying
    for if a trustworthy partner can still be read), and read first the member
    that is most likely to fail per second spent, so a failure shows up before
    the expensive tool has been paid for
  * with one reading in hand, pick the partner with the highest
    answers * trust * (1 - wrong-agreement) / (1 + cost/10)
  * if the decision is still unclear and no usable tool is left: hand off
Numbers measured on fewer than min_figures charts are replaced by the pooled
numbers: points on one chart share their mistakes.
"""
from __future__ import annotations

import itertools
from dataclasses import dataclass, fields

from .policies import Policy


@dataclass(frozen=True)
class Thresholds:
    """Defaults mirror configs/default.yaml (agent.informed); the reason for each is there."""
    min_answer: float = 0.10
    max_wrong_agree: float = 0.05
    min_points: int = 10
    min_figures: int = 5
    min_pair_agreements: int = 20

    @classmethod
    def from_cfg(cls, cfg: dict) -> "Thresholds":
        d = (cfg.get("agent") or {}).get("informed") or {}
        return cls(**{f.name: d[f.name] for f in fields(cls) if f.name in d})


TH = Thresholds()


def _enough(d: dict, th: Thresholds) -> bool:
    return d.get("n", 0) >= th.min_points and d.get("n_figures", th.min_figures) >= th.min_figures


def _stats(profile: dict, situation: str, tool: str, th: Thresholds = TH) -> dict | None:
    d = (profile["situations"].get(situation) or {}).get(tool)
    if d is None or not _enough(d, th):
        d = (profile["situations"].get("*") or {}).get(tool)
    return d


def answers(profile: dict, situation: str, tool: str, on_tick: bool | None = None, th: Thresholds = TH) -> float | None:
    d = _stats(profile, situation, tool, th)
    if d is None:
        return None
    split = {True: d.get("success_on_tick"), False: d.get("success_off_tick")}.get(on_tick)
    return d["success"] if split is None else split


def trust(profile: dict, situation: str, tool: str, th: Thresholds = TH) -> float | None:
    d = _stats(profile, situation, tool, th)
    if d is None or d.get("big_error") is None:
        return None
    return 1.0 - d["big_error"]


def pair_info(profile: dict, situation: str, a: str, b: str, th: Thresholds = TH) -> dict | None:
    """The pair's measured wrong-agreement and how much evidence is behind it (None = not measured enough)."""
    pairs = profile.get("pairs") or {}
    for key in (situation, "*"):
        p = (pairs.get(key) or {})
        p = p.get(f"{a}~{b}") or p.get(f"{b}~{a}")
        if p and p["agree"] >= th.min_pair_agreements and p.get("figures", th.min_figures) >= th.min_figures:
            return p
    return None


def wrong_when_agree(profile: dict, situation: str, a: str, b: str, th: Thresholds = TH) -> float | None:
    p = pair_info(profile, situation, a, b, th)
    return None if p is None else p["wrong_when_agree"]


def pair_note(profile: dict, situation: str, a: str, b: str, th: Thresholds = TH) -> str:
    p = pair_info(profile, situation, a, b, th)
    if p is None:
        return f"{a}+{b} wrong-agreement not measured enough"
    return (f"{a}+{b} wrong when agreeing {p['wrong_when_agree']:.1%} "
            f"({p['agree_wrong']} of {p['agree']} agreements, on {p.get('figures_wrong', '?')} of "
            f"{p.get('figures', '?')} charts)")


class InformedPolicy(Policy):
    name = "informed"

    def __init__(self, profile: dict, th: Thresholds | None = None):
        self.profile, self.th = profile, th or TH
        self.min_answer, self.max_wrong = self.th.min_answer, self.th.max_wrong_agree

    # ------------------------------------------------------------------ what the agent knows
    def assess(self, situation: str, tools: list[str], on_tick: bool | None = None) -> dict:
        """Which tools would answer here, and which pairs of them can cross-check each other."""
        ans = {t: answers(self.profile, situation, t, on_tick, self.th) for t in tools}
        callable_ = [t for t, a in ans.items() if a is None or a >= self.min_answer]
        pairs = {}
        for a, b in itertools.combinations(callable_, 2):
            pairs[f"{a}~{b}"] = wrong_when_agree(self.profile, situation, a, b, self.th)
        good = [k for k, r in pairs.items() if r is None or r <= self.max_wrong]
        return {"answers": ans, "callable": callable_, "pairs": pairs, "good_pairs": good,
                "skipped": {t: a for t, a in ans.items() if t not in callable_}}

    def _ans(self, sit: str, t: str, on_tick) -> float:
        a = answers(self.profile, sit, t, on_tick, self.th)
        return 0.5 if a is None else a

    # ------------------------------------------------------------------ what the agent does
    def next_action(self, state: dict) -> dict:
        sit = state.get("situation", "*")
        used = [r["tool"] for r in state["readings"]]
        on_tick = state.get("x_on_tick")
        plan = self.assess(sit, state.get("all_tools", state["available"]), on_tick)
        where = {True: ", x has a tick label", False: ", x has NO tick label"}.get(on_tick, "")
        blocked = state.get("blocked") or {}
        why_blocked = ("; not called: " + ", ".join(f"{t} ({c} earlier on this figure)" for t, c in blocked.items())
                       if blocked else "")

        if not plan["good_pairs"]:
            return {"action": "handoff",
                    "why": f"no two tools can cross-check each other on '{sit}' charts{where} "
                           f"(answer rates: {self._fmt(plan['answers'])}; "
                           f"wrong when agreeing: {self._fmt(plan['pairs'], 1)})"}
        if not used:
            return self._first_read(state, sit, on_tick, where, plan, why_blocked)

        scored, excluded = [], {}
        for t in state["available"]:
            if t not in plan["callable"]:
                continue
            risks = {u: wrong_when_agree(self.profile, sit, t, u, self.th) for u in used}
            bad = {u: r for u, r in risks.items() if r is not None and r > self.max_wrong}
            if bad:
                excluded[t] = bad
                continue
            a = self._ans(sit, t, on_tick)
            tr = trust(self.profile, sit, t, self.th)
            tr = 0.5 if tr is None else tr
            worst = max((r for r in risks.values() if r is not None), default=0.0)
            cost = state["costs"].get(t, 1.0)
            scored.append((a * tr * (1 - worst) / (1 + cost / 10), t, a, tr, worst, cost))

        if not scored:
            why = "decision still unclear and no usable tool left"
            if excluded:
                why += " (" + "; ".join(f"{t} agrees wrongly with {', '.join(f'{u} {r:.1%}' for u, r in b.items())}"
                                        for t, b in excluded.items()) + " of the time)"
            return {"action": "handoff", "why": why + why_blocked}

        scored.sort(reverse=True)
        score, best, a, tr, worst, cost = scored[0]
        shared = (state.get("shared_by") or {}).get(best, 1)
        why = (f"'{sit}' chart{where}: {best} answers {a:.0%}, its answers are right {tr:.0%}, cost {cost:.1f}s"
               + (f" (a figure's table is shared by {shared} claims)" if shared > 1 else "")
               + (f", wrong-agreement with {', '.join(used)} {worst:.1%}" if used else "")
               + (f"; next best {scored[1][1]} ({scored[1][0]:.3f} vs {score:.3f})" if len(scored) > 1 else ""))
        skipped = {t: r for t, r in plan["skipped"].items() if t in state["available"]}
        if skipped:
            why += f"; not calling {self._fmt(skipped)} (would almost surely refuse here)"
        if excluded:
            why += "; not a cross-check: " + ", ".join(
                f"{t} (wrong-agreement {max(b.values()):.1%})" for t, b in excluded.items())
        return {"action": "read", "tool": best, "why": why + why_blocked}

    def _first_read(self, state, sit, on_tick, where, plan, why_blocked) -> dict:
        """No reading yet: choose the best trustworthy PAIR, then read first the member most likely to fail."""
        costs = state["costs"]
        cands = [t for t in state["available"] if t in plan["callable"]]
        best = None
        for a, b in itertools.combinations(cands, 2):
            r = wrong_when_agree(self.profile, sit, a, b, self.th)
            if r is not None and r > self.max_wrong:
                continue
            value = (self._ans(sit, a, on_tick) * self._ans(sit, b, on_tick) * (1 - (r or 0))
                     / (1 + (costs.get(a, 1.0) + costs.get(b, 1.0)) / 10))
            if best is None or value > best[0]:
                best = (value, a, b)
        if best is None:
            return {"action": "handoff",
                    "why": "no trustworthy pair among the tools still available on this figure" + why_blocked}
        _, a, b = best
        first = max((a, b), key=lambda t: ((1 - self._ans(sit, t, on_tick)) / (costs.get(t, 1.0) + 0.1), t == a))
        other = b if first == a else a
        fail = 1 - self._ans(sit, first, on_tick)
        shared = (state.get("shared_by") or {}).get(first, 1)
        why = (f"'{sit}' chart{where}: best pair {a}+{b} ({pair_note(self.profile, sit, a, b, self.th)}); "
               f"{first} first: it fails {fail:.0%} of the time here and costs {costs.get(first, 1.0):.1f}s"
               + (f" (a figure's table is shared by {shared} claims)" if shared > 1 else "")
               + f", so a failure shows up before {other} is paid for")
        skipped = {t: r for t, r in plan["skipped"].items() if t in state["available"]}
        if skipped:
            why += f"; not calling {self._fmt(skipped)} (would almost surely refuse here)"
        return {"action": "read", "tool": first, "why": why + why_blocked}

    @staticmethod
    def _fmt(d: dict, digits: int = 0) -> str:
        return ", ".join(f"{k} {v:.{digits}%}" if v is not None else f"{k} n/a" for k, v in d.items())
