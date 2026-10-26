from chart_claim_verifier.agent.memory import ReportMemory
from chart_claim_verifier.agent.report_agent import ambiguous_accepts
from chart_claim_verifier.evaluation.tool_profile import failure_scope
from chart_claim_verifier.retrieval.figure_index import FigureIndex
from chart_claim_verifier.schemas import Report


def _mem():
    return ReportMemory(Report(report_id="r", pdf_path="", figures=[], sentences=[]), FigureIndex([]))


def test_failure_reach_decides_what_is_blocked():
    m = _mem()
    scope = {"y_fit_failed": "figure", "series_not_found": "series", "two_lines_at_x": "point"}
    m.note_failure("ocr", "f1", "A", "two_lines_at_x")
    assert m.blocked("ocr", "f1", ["A"], scope) is None                        # a point-level failure does not repeat
    m.note_failure("ocr", "f1", "A", "series_not_found")
    assert m.blocked("ocr", "f1", ["A"], scope) == "series_not_found"
    assert m.blocked("ocr", "f1", ["B"], scope) is None                        # another series is still worth trying
    assert m.blocked("ocr", "f2", ["A"], scope) is None                        # another figure too
    m.note_failure("ocr", "f1", "A", "y_fit_failed")
    assert m.blocked("ocr", "f1", ["B"], scope) == "y_fit_failed"              # figure-wide: every series
    m.note_failure("deplot", "f1", "A", "exception:KeyError")
    assert m.blocked("deplot", "f1", ["B"], {}) == "exception:KeyError"        # a crash is never retried on the figure


def test_failure_scope_is_measured_from_the_calibration_points():
    errs = []
    for f in ("f1", "f2"):
        for s in ("A", "B"):
            for x in range(10):
                e = {"figure": f, "series": s, "x": str(x), "_fail": {}, "ocr": 0.0}
                if s == "A":                                   # whole series A fails: series-wide
                    e = {**e, "_fail": {"ocr": "no_series"}}; del e["ocr"]
                elif x % 3 == 0:                               # scattered: point-level
                    e = {**e, "_fail": {"ocr": "overlap"}}; del e["ocr"]
                errs.append(e)
    scope = failure_scope(errs, ["ocr"])["ocr"]
    assert scope["no_series"] == "series" and scope["overlap"] == "point"


def test_ambiguous_figure_rules():
    both, one, none_ = ["CONSISTENT", "CONSISTENT"], ["NOT_SURE", "CONSISTENT"], ["NOT_SURE", "MISMATCH"]
    assert [ambiguous_accepts("either", v) for v in (both, one, none_)] == [True, True, False]
    assert [ambiguous_accepts("top", v) for v in (both, one, none_)] == [True, False, False]
    assert [ambiguous_accepts("both", v) for v in (both, one, none_)] == [True, False, False]
    assert not any(ambiguous_accepts("never", v) for v in (both, one, none_))
