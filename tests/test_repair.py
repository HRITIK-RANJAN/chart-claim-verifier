import dataclasses
import random

from chart_claim_verifier.agent.controller import ClaimController
from chart_claim_verifier.agent.memory import ReportMemory
from chart_claim_verifier.agent.planner import InformedPolicy
from chart_claim_verifier.agent.policies import Policy
from chart_claim_verifier.calibration.store import CalibrationTable
from chart_claim_verifier.decide.rule import RuleConfig
from chart_claim_verifier.retrieval.figure_index import FigureIndex
from chart_claim_verifier.schemas import ClaimSpec, Figure, Report
from chart_claim_verifier.tools.axis import analyse, series_colour
from chart_claim_verifier.tools.base import Tool, ToolError
from chart_claim_verifier.tools.chart_ocr import load_bgr


def test_legend_names_from_the_vlm_pick_the_right_colour(tmp_path):
    from chart_claim_verifier.generator.plot import render, sample_style
    from chart_claim_verifier.generator.tables import make_table
    rng = random.Random(11)
    for _ in range(20):                                     # find a chart whose legend OCR works, with 2+ series
        t = make_table(rng, "t", "line")
        style = sample_style(rng)
        render(t, style, tmp_path / "c.png")
        geo = analyse(str(tmp_path / "c.png"))
        if len(t.series) >= 2 and len(geo.legend) == len(t.series) == len(geo.swatches):
            break
    else:
        raise AssertionError("no suitable chart")
    img = load_bgr(str(tmp_path / "c.png"))
    names = list(geo.legend)                                # top to bottom, as the swatches are
    garbled = dataclasses.replace(geo, legend={})           # what Tesseract failing looks like
    for s in names:
        want = series_colour(img, geo, s)
        got = series_colour(img, garbled, s, names=names)
        assert abs(want.astype(int) - got.astype(int)).max() <= 2
    try:
        series_colour(img, garbled, names[0], names=names[:-1])
        raise AssertionError("a different number of names and handles must be refused")
    except Exception as e:
        assert getattr(e, "code", str(e)) in ("legend_mismatch",) or "legend_mismatch" in str(e)


class _Pt(Tool):
    name = "pt"

    def __init__(self):
        super().__init__()
        self.fixed = False

    def _read(self, fig, q):
        if not self.fixed:
            raise ToolError("nolegend")
        return 1.0


class _Other(Tool):
    name = "other"

    def _read(self, fig, q):
        return 1.0


class _RepairThenRead(Policy):
    def next_action(self, state):
        if state["failed_now"] and "pt:fix" not in state["repaired"]:
            return {"action": "repair", "tool": "pt", "repair": "fix", "why": "test"}
        for t in ("pt", "other"):
            if t in state["available"]:
                return {"action": "read", "tool": t}
        return {"action": "handoff"}


def test_a_repair_lifts_the_block_and_the_tool_is_read_again(tmp_path):
    from PIL import Image
    Image.new("RGB", (60, 40), "white").save(tmp_path / "c.png")
    fig = Figure(figure_id="f1", report_id="r", image_path=str(tmp_path / "c.png"), chart_type="line")
    mem = ReportMemory(Report(report_id="r", pdf_path="", figures=[fig], sentences=[]), FigureIndex([fig]))
    pt = _Pt()
    profile = {"cost": {}, "situations": {}, "failure_scope": {"pt": {"nolegend": "series"}},
               "repairs": {"pt:nolegend": {"repair": "fix", "fixed": 0.9, "n": 50}}}
    calls = []

    def fix(fig_, tool):
        calls.append(fig_.figure_id)
        tool.fixed = True
        return True

    ctl = ClaimController({"pt": pt, "other": _Other()}, _RepairThenRead(), CalibrationTable({}), RuleConfig(),
                          profile=profile, repairs={"fix": fix})
    claim = ClaimSpec(claim_id="c", sentence="s", claim_type="point", series="A", x="1", claimed_value=1.0)
    res = ctl.run(claim, fig, mem)
    assert calls == ["f1"] and set(res.tool_values) == {"pt", "other"}      # failed, repaired once, read again
    assert [s["action"]["action"] for s in res.steps][:3] == ["read", "repair", "read"]
    assert mem.blocked("pt", "f1", ["A"], {"nolegend": "series"}) is None
    assert res.calls == 4                       # failed read, the repair, the read after it, the other tool


def test_planner_proposes_only_a_repair_that_was_measured_and_completes_a_pair():
    from tests.test_planner import PROFILE, state
    prof = {**PROFILE, "repairs": {"ocr_pixel:series_not_found": {"repair": "read_legend", "fixed": 0.7, "n": 100, "seconds": 5}}}
    st = state("line|hard", readings=[], available=["vlm_crop"], on_tick=False)
    st.update(failed_now={"ocr_pixel": "series_not_found"}, can_repair=["read_legend"], repaired=[], repairs=prof["repairs"])
    a = InformedPolicy(prof).next_action(st)
    assert a["action"] == "repair" and a["repair"] == "read_legend" and "fixed 70%" in a["why"]
    st["repaired"] = ["ocr_pixel:read_legend"]                              # already tried on this figure
    assert InformedPolicy(prof).next_action(st)["action"] == "handoff"
    st["repaired"] = []
    prof["repairs"]["ocr_pixel:series_not_found"]["fixed"] = 0.3            # measured to work too rarely
    st["repairs"] = prof["repairs"]
    assert InformedPolicy(prof).next_action(st)["action"] == "handoff"
