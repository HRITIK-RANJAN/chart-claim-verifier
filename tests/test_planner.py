from reportlens.agent.planner import InformedPolicy, answers, trust, wrong_when_agree
from reportlens.evaluation.tool_profile import pair_stats

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
