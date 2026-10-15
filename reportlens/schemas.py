"""The data contract (implementation.md §6.1).

Every module talks through these objects. Changing this file needs the whole
team to agree, because every workstream depends on it.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

ChartType = Literal["bar", "grouped_bar", "line", "unknown"]
ClaimType = Literal["point", "difference", "relative_change"]
Relation = Literal["approx", "greater", "less"]
Verdict = Literal["CONSISTENT", "MISMATCH", "NOT_SURE", "NO_FIGURE", "SKIPPED"]
# SKIPPED = the sentence has a number but is not a chart claim
# ("we trained for 50 epochs"). It is excluded from coverage but a MISMATCH on
# such a sentence still counts as a wrong flag.


class Figure(BaseModel):
    figure_id: str                     # "fig3"
    report_id: str
    image_path: str
    caption: str = ""
    number: int | None = None          # "Figure 3" -> 3
    chart_type: ChartType = "unknown"
    page: int = 0
    text_lines: list[str] = Field(default_factory=list)  # OCR'd legend / ticks / titles
    y_span: float | None = None        # axis range, used for the disagreement floor


class Sentence(BaseModel):
    sentence_id: str
    report_id: str
    text: str
    page: int = 0
    nearest_figure_id: str | None = None   # figure closest above on the page (ablation)


class Report(BaseModel):
    report_id: str
    pdf_path: str
    figures: list[Figure]
    sentences: list[Sentence]


class ClaimSpec(BaseModel):
    """The "checkable form" of a sentence."""
    claim_id: str
    sentence: str
    claim_type: ClaimType
    series: str                        # "ResNet-50"
    x: str                             # "10" (epoch) / "CIFAR-10"
    series_b: str | None = None        # second operand (difference)
    x_b: str | None = None             # second x (relative change: from x to x_b)
    claimed_value: float
    unit: Literal["abs", "percent", "pct_points"] = "abs"
    relation: Relation = "approx"
    tolerance: float = 0.0             # allowed rounding, same units as the value
    figure_hint: int | None = None     # 3 if the sentence says "Figure 3"

    def operands(self) -> list[tuple[str, str]]:
        """The chart points that must be read to check this claim."""
        if self.claim_type == "point":
            return [(self.series, self.x)]
        if self.claim_type == "difference":
            return [(self.series, self.x), (self.series_b or self.series, self.x_b or self.x)]
        return [(self.series, self.x), (self.series, self.x_b or self.x)]


class PointQuery(BaseModel):
    series: str
    x: str


class Reading(BaseModel):
    tool: str                          # "vlm_crop" | "vlm_table" | "deplot" | "ocr_pixel" | ...
    value: float | None
    ok: bool
    error: str | None = None           # "series_not_found", "ocr_failed", "bad_json", ...
    latency_s: float = 0.0
    cached: bool = False
    query: PointQuery | None = None


class Decision(BaseModel):
    estimate: float | None = None      # median of per-tool derived values
    disagreement: float | None = None  # spread (MAD) of per-tool derived values
    gap: float | None = None           # how far the claim is from the estimate
    margin_flag: float | None = None
    margin_accept: float | None = None
    p_value: float | None = None
    n_readings: int = 0
    calibration_group: str | None = None
    verdict: Verdict
    reason: str = ""


class ClaimTrace(BaseModel):
    """One per claim, written as JSONL. Everything downstream reads this."""
    report_id: str
    sentence_id: str
    sentence: str
    claim: ClaimSpec | None = None
    figure_id: str | None = None
    figure_candidates: list[tuple[str, float]] = Field(default_factory=list)
    chart_type: ChartType = "unknown"
    y_span: float | None = None        # axis span of the figure (for re-deciding offline)
    tool_values: dict[str, float] = Field(default_factory=dict)  # per-tool derived value
    readings: list[Reading] = Field(default_factory=list)
    controller_steps: list[dict] = Field(default_factory=list)
    decision: Decision
    blocked_actions: list[str] = Field(default_factory=list)
    stages: list[dict] = Field(default_factory=list)   # agent log: stage, observation, decision, why
    # when two figures fit the sentence: what each one said, in ranking order
    # (figure_id -> {"verdict", "estimate", "gap", "margin_flag"}); lets the ambiguity rule be compared offline
    figure_runs: dict[str, dict] = Field(default_factory=dict)
    tool_calls: int = 0                # uncached calls
    policy: str = ""
