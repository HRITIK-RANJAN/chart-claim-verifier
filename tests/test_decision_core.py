import math
import random

import pytest

from chart_claim_verifier.calibration.fit import CalibrationItem, fit_table
from chart_claim_verifier.calibration.pvalues import benjamini_hochberg, conformal_cutoff, p_value
from chart_claim_verifier.calibration.store import CalibrationTable, ConstantTable
from chart_claim_verifier.claims.tolerance import find_numbers, is_within, rounding_tolerance
from chart_claim_verifier.decide.rule import RuleConfig, batch_check, claim_gap, decide
from chart_claim_verifier.measure.aggregate import derived_value, disagreement, estimate
from chart_claim_verifier.schemas import ClaimSpec, ClaimTrace, Decision


# ---------------------------------------------------------------- tolerance
@pytest.mark.parametrize("text,value,tol,rel,pct", [
    ("accuracy is 0.82", 0.82, 0.005, "approx", False),
    ("it reaches 82.4%", 82.4, 0.05, "approx", True),
    ("it reaches 82%", 82.0, 0.5, "approx", True),
    ("about 80% accuracy", 80.0, 5.0, "approx", True),
    ("around 82%", 82.0, 1.0, "approx", True),
    ("roughly 0.8", 0.8, 0.1, "approx", False),
    ("~80%", 80.0, 5.0, "approx", True),
    ("over 80% accuracy", 80.0, 0.0, "greater", True),
    ("less than 5% error", 5.0, 0.0, "less", True),
])
def test_tolerance_table(text, value, tol, rel, pct):
    (n,) = find_numbers(text)
    assert n.value == value and math.isclose(n.tolerance, tol) and n.relation == rel and n.percent == pct


def test_numbers_inside_names_are_ignored():
    # "ResNet-50" and "CIFAR-10" are names, not numbers
    nums = find_numbers("ResNet-50 reaches 91.2% on CIFAR-10.")
    assert [n.value for n in nums] == [91.2]


def test_is_within():
    assert is_within(90, 89.8, rounding_tolerance("90", False), "approx")
    assert not is_within(90, 89.2, rounding_tolerance("90", False), "approx")
    assert is_within(80, 81, 0, "greater") and not is_within(80, 79, 0, "greater")


# ---------------------------------------------------------------- aggregate
def test_estimate_and_disagreement():
    assert estimate([1, 2, 10]) == 2
    assert disagreement([1, 3]) == 1.0           # |v1 - v2| / 2
    assert disagreement([5, 5, 5, 5]) == 0.0


def test_derived_values():
    assert derived_value("point", [3.0]) == 3.0
    assert derived_value("difference", [80.0, 75.0]) == 5.0
    assert derived_value("relative_change", [50.0, 60.0]) == pytest.approx(20.0)
    assert derived_value("relative_change", [0.0, 1.0]) is None


# ---------------------------------------------------------------- conformal
def test_conformal_cutoff_uses_adjusted_rank():
    r = list(range(1, 20))                        # n = 19
    assert conformal_cutoff(r, 0.95) == 19        # ceil(20 * .95) = 19th smallest
    assert conformal_cutoff(r, 0.5) == 10
    assert conformal_cutoff(r[:5], 0.95) == math.inf   # too few points: never flag


def test_p_value():
    r = sorted([0.1, 0.5, 1.0, 2.0])
    assert p_value(3.0, r) == pytest.approx(1 / 5)
    assert p_value(0.0, r) == pytest.approx(1.0)
    assert p_value(1.0, r) == pytest.approx(3 / 5)


def test_conformal_coverage_holds_on_fresh_draws():
    rng = random.Random(1)
    cal = sorted(abs(rng.gauss(0, 1)) for _ in range(500))
    q = conformal_cutoff(cal, 0.9)
    fresh = [abs(rng.gauss(0, 1)) for _ in range(20000)]
    assert sum(x <= q for x in fresh) / len(fresh) >= 0.88


def test_benjamini_hochberg():
    assert benjamini_hochberg([0.001, 0.008, 0.039, 0.041, 0.6], alpha=0.05) == {0, 1}
    assert benjamini_hochberg([], 0.1) == set()
    assert benjamini_hochberg([0.9, 0.95], 0.1) == set()


# ---------------------------------------------------------------- rule
def _table(n=400, scale=2.0):
    rng = random.Random(0)
    items = []
    for _ in range(n):
        truth = rng.uniform(20, 90)
        vals = {t: truth + rng.gauss(0, 1.0) for t in ("a", "b", "c", "d")}
        items.append(CalibrationItem("bar", "point", truth, vals, span=100.0))
    return fit_table(items, eps=0.005, min_group_size=50)


def _claim(value, tol=0.05, relation="approx"):
    return ClaimSpec(claim_id="c", sentence="s", claim_type="point", series="A", x="1",
                     claimed_value=value, tolerance=tol, relation=relation)


def test_rule_three_outcomes():
    table, rc = _table(), RuleConfig()
    vals = {"a": 50.0, "b": 51.0, "c": 50.5, "d": 49.5}
    assert decide(_claim(50.2), vals, "bar", 100, table, rc)[0] == "CONSISTENT"
    status, d = decide(_claim(70.0), vals, "bar", 100, table, rc)
    assert status == "MISMATCH_CANDIDATE" and d.p_value < 0.01
    status, _ = decide(_claim(50.0 + 0.5 * (d.margin_flag + d.margin_accept) / 1), vals, "bar", 100, table, rc)
    assert status in ("UNCLEAR", "CONSISTENT", "MISMATCH_CANDIDATE")


def test_rule_needs_two_readings():
    status, d = decide(_claim(50), {"a": 50.0}, "bar", 100, _table(), RuleConfig())
    assert status == "TOO_FEW" and d.verdict == "NOT_SURE"


def test_rounded_claim_is_not_flagged():
    # "90%" when the chart shows 89.8 -- correct within rounding.
    vals = {"a": 89.8, "b": 89.8, "c": 89.8, "d": 89.8}
    status, d = decide(_claim(90.0, tol=0.5), vals, "bar", 100, _table(), RuleConfig())
    assert status == "CONSISTENT" and d.p_value == 1.0


def test_one_sided_claims():
    vals = {"a": 85.0, "b": 85.2, "c": 84.9, "d": 85.1}
    assert claim_gap(80, 85, "greater") == 0
    assert decide(_claim(80, 0, "greater"), vals, "bar", 100, _table(), RuleConfig())[0] == "CONSISTENT"
    assert decide(_claim(95, 0, "greater"), vals, "bar", 100, _table(), RuleConfig())[0] == "MISMATCH_CANDIDATE"


def test_shared_mistakes_widen_margins():
    # Tools that agree on the SAME wrong value -> big ratios -> wide margins.
    rng = random.Random(0)
    good, shared = [], []
    for _ in range(400):
        truth = rng.uniform(20, 90)
        good.append(CalibrationItem("bar", "point", truth, {t: truth + rng.gauss(0, 1) for t in "abcd"}, 100))
        off = rng.gauss(0, 3)
        shared.append(CalibrationItem("bar", "point", truth, {t: truth + off + rng.gauss(0, .3) for t in "abcd"}, 100))
    q_good = fit_table(good, 0.005, 50).cutoff("bar", "point", 4, 0.95)[1]
    q_shared = fit_table(shared, 0.005, 50).cutoff("bar", "point", 4, 0.95)[1]
    assert q_shared > 2 * q_good


def test_group_fallback():
    table = _table(n=100)
    table.min_group_size = 150
    key, _ = table.lookup("line", "difference", 3)
    assert key == "*|*|*"


def test_table_roundtrip(tmp_path):
    t = _table(100)
    t.save(tmp_path / "t.json")
    t2 = CalibrationTable.load(tmp_path / "t.json")
    assert t2.groups == t.groups


def test_constant_table_is_uncalibrated_baseline():
    vals = {"a": 50.0, "b": 52.0}
    status, d = decide(_claim(60), vals, "bar", 100, ConstantTable(2.0, 1.0), RuleConfig())
    assert status == "MISMATCH_CANDIDATE" and d.p_value != d.p_value      # NaN -> skipped by batch check


def _trace(verdict, p):
    return ClaimTrace(report_id="r", sentence_id="s", sentence="s",
                      decision=Decision(verdict=verdict, p_value=p))


def test_batch_check_demotes_weak_flags():
    traces = [_trace("MISMATCH", 0.001), _trace("MISMATCH", 0.5), _trace("CONSISTENT", 1.0)]
    out = batch_check(traces, alpha=0.1)
    assert [t.decision.verdict for t in out] == ["MISMATCH", "NOT_SURE", "CONSISTENT"]
    assert traces[1].decision.verdict == "MISMATCH"     # input untouched
