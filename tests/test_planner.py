from chart_claim_verifier.agent.planner import InformedPolicy, answers, trust, wrong_when_agree
from chart_claim_verifier.evaluation.tool_profile import pair_stats

TOOLS = ["ocr_pixel", "deplot", "vlm_table", "vlm_crop"]


def _pair(agree, wrong):
    return {"both": agree, "agree": agree, "agree_wrong": wrong, "wrong_when_agree": wrong / agree}


PROFILE = {
    "situations": {
        "line|hard": {
            # the pixel reader often refuses but is right when it answers; the crop reader always answers
            "ocr_pixel": {"n": 100, "success": 0.3, "big_error": 0.02},
            "deplot": {"n": 100, "success": 0.45, "big_error": 0.08, "success_on_tick": 0.9, "success_off_tick": 0.05},
            "vlm_table": {"n": 100, "success": 0.45, "big_error": 0.47, "success_on_tick": 0.9, "success_off_tick": 0.05},
            "vlm_crop": {"n": 100, "success": 1.0, "big_error": 0.40},
        },
        "bar|easy": {t: {"n": 100, "success": 0.99, "big_error": 0.0} for t in TOOLS},
        "*": {t: {"n": 400, "success": 0.8, "big_error": 0.02} for t in TOOLS},
    },
    "cost": {},
    "pairs": {
        "line|hard": {"ocr_pixel~deplot": _pair(100, 1), "ocr_pixel~vlm_table": _pair(90, 0),
                      "ocr_pixel~vlm_crop": _pair(120, 3), "deplot~vlm_table": _pair(100, 1),
                      "deplot~vlm_crop": _pair(160, 3), "vlm_table~vlm_crop": _pair(100, 10)},
        "*": {},
    },
}
COSTS = {"ocr_pixel": 0.0, "deplot": 10.0, "vlm_table": 18.0, "vlm_crop": 4.0}


def state(sit, readings=(), available=TOOLS, costs=None, on_tick=None):
    return {"situation": sit, "readings": [{"tool": t, "value": 1.0} for t in readings], "failed_here": [],
            "available": [t for t in available if t not in readings], "all_tools": TOOLS,
            "costs": costs or COSTS, "cached_for_free": [], "x_on_tick": on_tick}


def test_measurements():
    assert answers(PROFILE, "line|hard", "deplot", on_tick=False) == 0.05
    assert abs(trust(PROFILE, "line|hard", "vlm_crop") - 0.6) < 1e-9
    assert wrong_when_agree(PROFILE, "line|hard", "vlm_crop", "vlm_table") == 0.1   # order does not matter


def test_pair_stats_counts_wrong_agreements():
    errs = [{"_situation": "s", "a": 0.10, "b": 0.11},     # agree, both wrong
            {"_situation": "s", "a": 0.00, "b": 0.01},     # agree, right
            {"_situation": "s", "a": 0.00, "b": 0.20}]     # disagree
    p = pair_stats(errs, ["a", "b"])["s"]["a~b"]
    assert (p["both"], p["agree"], p["agree_wrong"]) == (3, 2, 1)


def test_a_tool_that_often_refuses_is_still_used():
    # the old rule (success * (1 - 2 big_error)) skipped the pixel reader here; it is free and right when it answers
    a = InformedPolicy(PROFILE).next_action(state("line|hard", readings=["vlm_crop"], on_tick=False))
    assert a["action"] == "read" and a["tool"] == "ocr_pixel"


def test_does_not_call_tools_that_would_refuse():
    a = InformedPolicy(PROFILE).next_action(state("line|hard", readings=["vlm_crop"], available=["deplot", "vlm_table"],
                                                  on_tick=False))
    assert a["action"] == "handoff"


def test_same_model_is_not_a_cross_check():
    # after the crop reader, the table reader (same VLM, wrong-agreement 10%) is not used; deplot is
    a = InformedPolicy(PROFILE).next_action(state("line|hard", readings=["vlm_crop"],
                                                  available=["deplot", "vlm_table"], on_tick=True))
    assert a["tool"] == "deplot"
    assert "vlm_table (wrong-agreement 10.0%)" in a["why"]       # the decision cites the measurement


def test_hands_off_when_only_a_bad_pair_is_left():
    a = InformedPolicy(PROFILE).next_action(state("line|hard", readings=["vlm_crop"], available=["vlm_table"],
                                                  on_tick=True))
    assert a["action"] == "handoff" and "agrees wrongly" in a["why"]


def test_cheap_tool_first_on_easy_charts():
    assert InformedPolicy(PROFILE).next_action(state("bar|easy"))["tool"] == "ocr_pixel"


def test_hands_off_at_once_when_no_pair_can_cross_check():
    prof = {**PROFILE, "pairs": {"x": {"ocr_pixel~vlm_crop": _pair(100, 20)}}}
    prof["situations"] = {"x": {t: {"n": 100, "success": 0.05, "big_error": 0.0} for t in TOOLS}}
    prof["situations"]["x"]["ocr_pixel"]["success"] = prof["situations"]["x"]["vlm_crop"]["success"] = 0.9
    a = InformedPolicy(prof).next_action(state("x"))
    assert a["action"] == "handoff" and "no two tools can cross-check" in a["why"]


# ---------------------------------------------------------------- U1: thresholds come from the config
def test_thresholds_come_from_the_config():
    from chart_claim_verifier.agent.planner import Thresholds
    from chart_claim_verifier.config import load_config
    th = Thresholds.from_cfg(load_config(None, agent={"informed": {"min_answer": 0.5}}))
    assert th.min_answer == 0.5 and th.max_wrong_agree == 0.05
    # deplot answers 45% here: with min_answer 0.5 it is no longer worth calling
    a = InformedPolicy(PROFILE, th).assess("line|hard", TOOLS, on_tick=None)
    assert "deplot" in a["skipped"]


# ---------------------------------------------------------------- U3: plan a pair, fail fast
def test_free_unreliable_tool_is_read_first_and_no_expensive_read_follows_its_failure():
    pol = InformedPolicy(PROFILE)
    first = pol.next_action(state("line|hard", on_tick=False))
    assert first["action"] == "read" and first["tool"] == "ocr_pixel"           # free, fails 70% of the time
    assert "ocr_pixel+vlm_crop" in first["why"] and "before vlm_crop is paid for" in first["why"]
    # it failed: nothing it could pair with is left that would answer, so no vlm_crop call is made
    after = pol.next_action(state("line|hard", available=["vlm_crop", "deplot", "vlm_table"], on_tick=False))
    assert after["action"] == "handoff" and "no trustworthy pair" in after["why"]


# ---------------------------------------------------------------- U4: a table tool's cost is shared
def test_blocked_and_shared_costs_reach_the_state(tmp_path):
    from PIL import Image

    from chart_claim_verifier.agent.controller import ClaimController
    from chart_claim_verifier.agent.memory import ReportMemory
    from chart_claim_verifier.agent.policies import FixedOrderPolicy
    from chart_claim_verifier.calibration.store import CalibrationTable
    from chart_claim_verifier.decide.rule import RuleConfig
    from chart_claim_verifier.retrieval.figure_index import FigureIndex
    from chart_claim_verifier.schemas import ClaimSpec, Figure, Report
    from chart_claim_verifier.tools.base import Table, TableTool, Tool

    class Table_(TableTool):
        name = "tab"
        def extract_table(self, fig) -> Table: return {"A": {"1": 1.0}}

    class Point_(Tool):
        name = "pt"
        def _read(self, fig, q): return 1.0

    Image.new("RGB", (60, 40), "white").save(tmp_path / "c.png")
    fig = Figure(figure_id="f1", report_id="r", image_path=str(tmp_path / "c.png"), chart_type="line")
    mem = ReportMemory(Report(report_id="r", pdf_path="", figures=[fig], sentences=[]), FigureIndex([fig]))
    mem.pending["f1"] = 3
    ctl = ClaimController({"tab": Table_(), "pt": Point_()}, FixedOrderPolicy(["tab", "pt"]), CalibrationTable({}),
                          RuleConfig(), profile={"cost": {"tab": {"seconds_per_figure": 9.0}, "pt": {"seconds_per_read": 2.0}},
                                                 "situations": {}, "failure_scope": {"pt": {"bad": "figure"}}})
    claim = ClaimSpec(claim_id="c", sentence="s", claim_type="point", series="A", x="1", claimed_value=1.0)
    from chart_claim_verifier.agent.controller import ClaimResult
    from chart_claim_verifier.schemas import Decision
    res = ClaimResult(status="TOO_FEW", decision=Decision(verdict="NOT_SURE"))
    st = ctl._state(claim, fig, res, mem, set(), None)
    assert st["costs"] == {"tab": 3.0, "pt": 2.0} and st["shared_by"] == {"tab": 3}
    mem.note_failure("pt", "f1", "A", "bad")                                   # a figure-wide failure
    st = ctl._state(claim, fig, res, mem, set(), None)
    assert st["blocked"] == {"pt": "bad"} and st["available"] == ["tab"]


# ---------------------------------------------------------------- U5: evidence counted in charts
def test_numbers_from_too_few_charts_fall_back_to_the_pooled_ones():
    import copy
    prof = copy.deepcopy(PROFILE)
    prof["situations"]["bar|easy"]["deplot"] = {"n": 100, "n_figures": 3, "success": 0.01, "big_error": 0.0}
    prof["situations"]["*"]["deplot"] = {"n": 400, "n_figures": 20, "success": 0.8, "big_error": 0.02}
    assert answers(prof, "bar|easy", "deplot") == 0.8                          # 3 charts: not enough
    prof["situations"]["bar|easy"]["deplot"]["n_figures"] = 6
    assert answers(prof, "bar|easy", "deplot") == 0.01
    p = {"n": 1, "n_figures": 2, "success": 0.5, "big_error": 0.0}
    prof["pairs"]["bar|easy"] = {"ocr_pixel~deplot": {**_pair(50, 10), "figures": 2, "figures_wrong": 1}}
    assert wrong_when_agree(prof, "bar|easy", "ocr_pixel", "deplot") is None   # 2 charts: pair not measured enough


def test_pair_stats_counts_charts():
    errs = [{"_situation": "s", "figure": "f1", "a": 0.10, "b": 0.11}, {"_situation": "s", "figure": "f2", "a": 0.0, "b": 0.01}]
    p = pair_stats(errs, ["a", "b"])["s"]["a~b"]
    assert (p["figures"], p["figures_wrong"]) == (2, 1)


# ---------------------------------------------------------------- U9: the LLM policy logs what P3 would do
def test_llm_policy_logs_what_the_informed_policy_would_choose():
    from chart_claim_verifier.agent.policies import FixedOrderPolicy, LLMPolicy
    from chart_claim_verifier.models.vlm import ScriptedLLM
    llm = ScriptedLLM(lambda p, i, n: '{"action": "read", "tool": "vlm_crop"}')
    pol = LLMPolicy(llm, {}, {}, FixedOrderPolicy(TOOLS), reference=InformedPolicy(PROFILE))
    out = pol.next_action(state("bar|easy"))
    assert out["tool"] == "vlm_crop" and out["p3_choice"] == "ocr_pixel" and out["agrees_with_p3"] is False
