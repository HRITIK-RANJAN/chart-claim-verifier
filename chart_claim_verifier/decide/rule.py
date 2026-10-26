"""The decision rule (implementation.md §8.2, §8.4).

"The LLM proposes, the rule decides": this is the only place a claim can
become CONSISTENT or MISMATCH. No model calls, fully unit-tested.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from ..calibration.pvalues import benjamini_hochberg
from ..calibration.store import CalibrationTable
from ..measure.aggregate import disagreement, estimate
from ..schemas import ClaimSpec, ClaimTrace, Decision

Status = Literal["CONSISTENT", "MISMATCH_CANDIDATE", "UNCLEAR", "TOO_FEW"]


@dataclass
class RuleConfig:
    level_flag: float = 0.95
    level_accept: float = 0.75
    eps: float = 0.005
    min_readings: int = 2
    alpha: float = 0.10
    max_accept_margin: float = 0.03   # fraction of axis span; wider margin -> cannot tell, measure again

    @classmethod
    def from_cfg(cls, cfg: dict) -> "RuleConfig":
        d = cfg["decision"]
        return cls(d["level_flag"], d["level_accept"], d["eps"], d["min_readings"], d["alpha"],
                   d.get("max_accept_margin", 0.03))


def claim_gap(claimed: float, est: float, relation: str) -> float:
    """How far the claim is from the estimate, in the claim's own direction."""
    if relation == "greater":          # claim: true value > claimed
        return max(0.0, claimed - est)
    if relation == "less":             # claim: true value < claimed
        return max(0.0, est - claimed)
    return abs(claimed - est)


def decide(claim: ClaimSpec, tool_values: dict[str, float], chart_type: str, span: float,
           table: CalibrationTable, rc: RuleConfig) -> tuple[Status, Decision]:
    values = list(tool_values.values())
    k = len(values)
    if k < rc.min_readings:
        return "TOO_FEW", Decision(verdict="NOT_SURE", n_readings=k, reason="too few readings")

    est, dis = estimate(values), disagreement(values)
    scale = dis + rc.eps * span                     # disagreement with a floor
    group, q_flag = table.cutoff(chart_type, claim.claim_type, k, rc.level_flag)
    _, q_acc = table.cutoff(chart_type, claim.claim_type, k, rc.level_accept)
    m_flag, m_acc = q_flag * scale, q_acc * scale
    gap = claim_gap(claim.claimed_value, est, claim.relation)
    tol = claim.tolerance

    score = max(gap - tol, 0.0) / scale             # same scale as the calibration ratios
    p = table.p_value(chart_type, claim.claim_type, k, score)

    common = dict(estimate=est, disagreement=dis, gap=gap, margin_flag=m_flag, margin_accept=m_acc,
                  p_value=p, n_readings=k, calibration_group=group)
    if gap > tol + m_flag:
        return "MISMATCH_CANDIDATE", Decision(verdict="MISMATCH", reason="gap > rounding + flag margin", **common)
    if gap <= tol + m_acc:
        if m_acc <= rc.max_accept_margin * span:
            return "CONSISTENT", Decision(verdict="CONSISTENT", reason="gap <= rounding + accept margin", **common)
        # The readings are so spread out that a real error would also fit inside the margin.
        return "UNCLEAR", Decision(verdict="NOT_SURE", reason="readings too spread out to accept", **common)
    return "UNCLEAR", Decision(verdict="NOT_SURE", reason="between the two margins", **common)


def batch_check(traces: list[ClaimTrace], alpha: float = 0.10) -> list[ClaimTrace]:
    """Benjamini–Hochberg over all MISMATCH candidates in a batch (one assignment).

    Candidates that do not survive become NOT_SURE. Claims in one report share
    figures, so p-values are positively dependent; BH tolerates that, but the
    realised wrong-flag rate is still checked empirically (E2).
    """
    idx = [i for i, t in enumerate(traces)
           if t.decision.verdict == "MISMATCH" and t.decision.p_value is not None
           and t.decision.p_value == t.decision.p_value]          # skip NaN (B5)
    keep = benjamini_hochberg([traces[i].decision.p_value for i in idx], alpha)
    out = [t.model_copy(deep=True) for t in traces]
    for j, i in enumerate(idx):
        if j not in keep:
            out[i].decision.verdict = "NOT_SURE"
            out[i].decision.reason = "did not survive batch check (BH)"
    return out
