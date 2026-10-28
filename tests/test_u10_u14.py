import pytest

from chart_claim_verifier.calibration.fit import CalibrationItem, fit_table
from chart_claim_verifier.calibration.store import fallback_chain
from chart_claim_verifier.measure.aggregate import derived_value, tool_value


def test_tied_legs_give_no_tool_value_but_the_truth_keeps_them():
    assert tool_value("difference", [75.0, 75.0]) is None             # one mark read twice
    assert tool_value("relative_change", [40.0, 40.0]) is None
    assert tool_value("difference", [80.0, 75.0]) == 5.0
    assert tool_value("point", [75.0]) == 75.0                         # a single operand cannot tie
    assert tool_value("difference", [75.0, 75.0], drop_ties=False) == 0.0
    assert derived_value("difference", [75.0, 75.0]) == 0.0            # equal true legs are a valid claim


def _items():
    # `a` and `b` agree tightly, `c` is noisy: a pair margin from {a, b} must be tighter than one from {a, c}
    out = []
    for i in range(60):
        truth = 50.0 + i
        out.append(CalibrationItem("line", "point", truth, {"a": truth + 0.1, "b": truth - 0.1, "c": truth + (3 if i % 2 else -3)},
                                   100.0))
    return out


def test_tool_set_groups_fit_the_pair_that_is_used():
    t = fit_table(_items(), 0.005, min_group_size=30)
    assert "line|point|a+b" in t.groups and "line|point|a+c" in t.groups and "*|*|a+b" in t.groups
    k_ab = t.cutoff("line", "point", 2, 0.95, ["a", "b"])
    k_ac = t.cutoff("line", "point", 2, 0.95, ["c", "a"])            # order of the tools does not matter
    assert k_ab[0] == "line|point|a+b" and k_ac[0] == "line|point|a+c"
    k_none = t.cutoff("line", "point", 2, 0.95)                      # no tool names: the old k group
    assert k_none[0] == "line|point|k2"


def test_unknown_tool_set_falls_back_to_the_count():
    t = fit_table(_items(), 0.005, min_group_size=30)
    key, _ = t.cutoff("line", "point", 2, 0.95, ["a", "zzz"])
    assert key == "line|point|k2"
    assert fallback_chain("bar", "difference", 3, ["y", "x"])[:3] == [
        "bar|difference|x+y", "bar|*|x+y", "*|*|x+y"]


def test_group_on_too_few_charts_falls_back_to_a_coarser_group():
    items = [CalibrationItem("bar", "point", 50.0 + i, {"a": 50.0 + i + 0.1, "b": 50.0 + i - 0.1}, 100.0, f"chart{i % 3}")
             for i in range(60)] + \
            [CalibrationItem("line", "point", 50.0 + i, {"a": 50.0 + i + 1, "b": 50.0 + i - 1}, 100.0, f"chart{i % 30}")
             for i in range(60)]
    t = fit_table(items, 0.005, min_group_size=30, min_group_charts=20)
    assert t.charts["bar|point|k2"] == 3 and t.charts["line|point|k2"] == 30
    assert t.cutoff("bar", "point", 2, 0.95)[0] == "*|*|k2"        # 60 points but only 3 charts: not a group
    assert t.cutoff("line", "point", 2, 0.95)[0] == "line|point|k2"
    # the old behaviour (no chart minimum) is unchanged
    assert fit_table(items, 0.005, min_group_size=30).cutoff("bar", "point", 2, 0.95)[0] == "bar|point|k2"
