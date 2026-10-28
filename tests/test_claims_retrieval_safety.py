import json

import pytest

from chart_claim_verifier.agent.policies import FixedOrderPolicy, LLMPolicy
from chart_claim_verifier.claims.finder import is_candidate
from chart_claim_verifier.claims.parser import LLMParser, ParseError, RuleParser
from chart_claim_verifier.lms.guard import ActionGuard
from chart_claim_verifier.lms.mock_lms import MockLMS
from chart_claim_verifier.models.vlm import ScriptedLLM, extract_json
from chart_claim_verifier.retrieval.figure_index import FigureIndex
from chart_claim_verifier.schemas import ClaimSpec, Figure
from chart_claim_verifier.tools.base import ToolError, lookup
from chart_claim_verifier.tools.deplot import parse_linearized
from chart_claim_verifier.tools.vlm_table import parse_table


# ---------------------------------------------------------------- finder / parser
def test_finder():
    assert is_candidate("ResNet-50 reaches 91.2% accuracy on CIFAR-10 (Figure 2).")
    assert not is_candidate("We trained each model for 50 epochs with a batch size of 64.")
    assert not is_candidate("Figure 2 shows the accuracy during training.")


@pytest.mark.parametrize("sentence,ctype,ops,value,tol,rel", [
    ("ResNet-50 reaches 91.2% accuracy at epoch 10.", "point", [("ResNet-50", "10")], 91.2, 0.05, "approx"),
    ("As shown in Figure 2, at epoch 5, ViT-S achieves about 80% accuracy.", "point", [("ViT-S", "5")], 80, 5, "approx"),
    ("On AG News, Random Forest obtains an accuracy of over 70%.", "point", [("Random Forest", "AG News")], 70, 0, "greater"),
    ("CNN has a loss of 0.235 at epoch 3 (Figure 1).", "point", [("CNN", "3")], 0.235, 0.0005, "approx"),
    ("ViT-S outperforms MLP by 3.4 percentage points on MNIST.", "difference",
     [("ViT-S", "MNIST"), ("MLP", "MNIST")], 3.4, 0.05, "approx"),
    ("LSTM scores 5.4 points higher on SST-2 than on IMDB.", "difference",
     [("LSTM", "SST-2"), ("LSTM", "IMDB")], 5.4, 0.05, "approx"),
    ("From epoch 10 to epoch 60, the accuracy of GRU improves by a relative 60%.", "relative_change",
     [("GRU", "10"), ("GRU", "60")], 60, 0.5, "approx"),
])
def test_rule_parser(sentence, ctype, ops, value, tol, rel):
    c = RuleParser().parse(sentence, "c1")
    assert c.claim_type == ctype and c.operands() == ops
    assert c.claimed_value == value and c.tolerance == pytest.approx(tol) and c.relation == rel


def test_rule_parser_rejects_non_claims():
    assert RuleParser().parse("The results look stable after 10 epochs overall.", "c") is None


def _llm_answer(form):
    return ScriptedLLM(lambda p, i, n: json.dumps(form))


def test_llm_parser_takes_tolerance_from_text_not_model():
    form = {"is_chart_claim": True, "claim_type": "point", "series": "ViT-S", "x": "epoch 5",
            "number_as_written": "about 80%"}
    c = LLMParser(_llm_answer(form)).parse("ViT-S gets roughly... about 80% at epoch 5.", "c")
    assert c.x == "5" and c.claimed_value == 80 and c.tolerance == 5


def test_llm_parser_retries_then_fails():
    llm = ScriptedLLM(lambda p, i, n: "not json at all")
    with pytest.raises(ParseError):
        LLMParser(llm).parse("ViT-S reaches 80% at epoch 5.", "c")
    assert llm.calls == 2


def test_llm_parser_rejects_number_not_in_sentence():
    form = {"is_chart_claim": True, "claim_type": "point", "series": "A", "x": "1", "number_as_written": "99%"}
    with pytest.raises(ParseError):
        LLMParser(_llm_answer(form)).parse("A reaches 80% at epoch 1.", "c")


def test_extract_json():
    assert extract_json('Sure! ```json\n{"value": 3.5}\n```') == {"value": 3.5}


# ---------------------------------------------------------------- retrieval
def _fig(fid, n, kind, lines, cap=""):
    return Figure(figure_id=fid, report_id="r", image_path=f"/x/{fid}.png", number=n, chart_type=kind,
                  caption=cap, text_lines=lines)


FIGS = [
    _fig("fig1", 1, "line", ["Training loss", "ResNet-50", "ViT-S", "Epoch"], "Training loss."),
    _fig("fig2", 2, "line", ["Accuracy during training", "ResNet-50", "ViT-S", "Epoch"], "Accuracy."),
    _fig("fig3", 3, "grouped_bar", ["Accuracy by dataset", "SVHN", "MNIST", "MLP", "CNN"], "Accuracy by dataset."),
]


def _claim(sentence):
    return RuleParser().parse(sentence, "c")


def test_retrieval_uses_metric_and_axis_type():
    idx = FigureIndex(FIGS)
    figs, _ = idx.locate(_claim("ResNet-50 reaches 91.2% accuracy at epoch 10."))
    assert [f.figure_id for f in figs] == ["fig2"]                      # not the loss chart
    figs, _ = idx.locate(_claim("MLP achieves 71.0% accuracy on SVHN."))
    assert [f.figure_id for f in figs] == ["fig3"]


def test_retrieval_no_figure_and_short_names():
    idx = FigureIndex(FIGS)
    assert idx.locate(_claim("SVM reaches 70.1% accuracy on SVHN."))[0] == []    # SVM != SVHN
    assert idx.locate(_claim("XGBoost reaches 80.2% accuracy on IMDB."))[0] == []


def test_explicit_reference_settles_ambiguity():
    figs, _ = FigureIndex(FIGS).locate(_claim("ResNet-50 has a loss of 0.41 at epoch 3 (Figure 1)."))
    assert [f.figure_id for f in figs] == ["fig1"]


def test_cited_figure_survives_an_ocr_miss_of_the_series_name():
    idx = FigureIndex(FIGS)
    # "ViT-S" is not in fig2's OCR text here, but the sentence cites Figure 2 and everything else matches
    figs = [_fig("fig2", 2, "line", ["Accuracy during training", "ResNet-50", "Epoch"], "Accuracy.")]
    idx2 = FigureIndex(figs)
    assert [f.figure_id for f in idx2.locate(_claim("ViT-S reaches 80.1% accuracy at epoch 10 (Figure 2)."))[0]] == ["fig2"]
    assert idx2.locate(_claim("ViT-S reaches 80.1% accuracy at epoch 10."))[0] == []         # no citation: still NO_FIGURE
    # the cited figure must still fit the metric: a loss chart does not serve an accuracy claim
    assert idx.locate(_claim("XGBoost reaches 80.1% accuracy at epoch 10 (Figure 1)."))[0] == []


def test_legend_names_rescue_an_ocr_miss_but_not_a_missing_series():
    figs = [_fig("fig2", 2, "line", ["Accuracy during training", "ResNet-50", "Epoch"], "Accuracy.")]
    asked = []

    def reader(fig):
        asked.append(fig.figure_id)
        return ["ResNet-50", "ViT-S"]                   # the VLM read the legend OCR missed

    idx = FigureIndex(figs, legend_reader=reader)
    found, _ = idx.locate(_claim("ViT-S reaches 80.1% accuracy at epoch 10."))
    assert [f.figure_id for f in found] == ["fig2"] and asked == ["fig2"]
    assert "legend read by the VLM" in idx.rescued[("fig2", "ViT-S")]
    assert idx.locate(_claim("XGBoost reaches 80.1% accuracy at epoch 10."))[0] == []    # not in the legend either


def test_llm_parser_accepts_an_epoch_written_as_a_number():
    raw = ('{"is_chart_claim": true, "claim_type": "point", "series": "MLP", "x": 14, "series_b": null, '
           '"x_b": null, "number_as_written": "77.2%"}')
    c = LLMParser(ScriptedLLM(lambda prompt, images, i: raw)).parse("Epoch 14 sees MLP post a validation accuracy of 77.2%.", "c1")
    assert c.x == "14" and c.series == "MLP" and c.claimed_value == 77.2


# ---------------------------------------------------------------- table parsing
def test_parse_vlm_table_and_lookup():
    t = parse_table('Here: {"ResNet-50": {"CIFAR-10": "91.2%", "MNIST": 99}, "junk": 3}')
    assert lookup(t, "resnet50", "CIFAR10") == 91.2
    with pytest.raises(ToolError):
        lookup(t, "ResNet-50", "SVHN")


def test_parse_deplot():
    t = parse_linearized("TITLE | Acc <0x0A> Epoch | ResNet | ViT <0x0A> 1 | 50.5 | 60 <0x0A> 2 | 70% | 80")
    assert t == {"ResNet": {"1": 50.5, "2": 70.0}, "ViT": {"1": 60.0, "2": 80.0}}


# ---------------------------------------------------------------- safety
def test_guard_blocks_forbidden_actions():
    g = ActionGuard(MockLMS())
    assert g.execute("update_grade", caller="llm", report_id="r", score=100)["ok"] is False
    assert g.execute("email_student", caller="llm", report_id="r", message="hi")["ok"] is False
    assert g.execute("post_flag", caller="rule", report_id="r", claim_id="c", verdict="MISMATCH", evidence={})["ok"]
    assert g.lms.grades == {} and g.lms.outbox == [] and len(g.lms.review_list) == 1
    assert len(g.blocked) == 2 and g.unsafe_executed == 0


def test_llm_policy_cannot_use_lms_tools_or_give_verdicts():
    state = {"available": ["ocr_pixel", "deplot"], "costs": {}, "cached_for_free": [], "chart_type": "bar"}
    pol = LLMPolicy(ScriptedLLM(lambda p, i, n: '{"action": "read", "tool": "update_grade"}'), {}, MockLMS.CATALOG,
                    FixedOrderPolicy(["ocr_pixel", "deplot"]))
    a = pol.next_action(state)
    assert a["tool"] == "ocr_pixel" and a["forbidden"] == "update_grade" and pol.invalid == 1
    pol = LLMPolicy(ScriptedLLM(lambda p, i, n: '{"verdict": "CONSISTENT"}'), {}, MockLMS.CATALOG,
                    FixedOrderPolicy(["deplot"]))
    assert pol.next_action(state)["action"] == "read"


# ---------------------------------------------------------------- baselines (with a scripted model)
def test_baselines_with_scripted_model():
    from chart_claim_verifier.baselines.vlm_baselines import b1_direct, b2_threshold, b3_majority, b4_tools_no_rule
    from chart_claim_verifier.schemas import ClaimTrace, Decision, Report
    claim = RuleParser().parse("A reaches 80.0% accuracy at epoch 1.", "c")
    t = ClaimTrace(report_id="r", sentence_id="s", sentence=claim.sentence, claim=claim, figure_id="fig1",
                   tool_values={"a": 70.0, "b": 71.0}, decision=Decision(verdict="NOT_SURE"))
    reports = {"r": Report(report_id="r", pdf_path="x", sentences=[],
                           figures=[Figure(figure_id="fig1", report_id="r", image_path="/x.png")])}
    b1 = b1_direct([t], reports, ScriptedLLM(lambda p, i, n: '{"verdict": "REFUTED", "confidence": 60}'))
    assert b1[0].decision.verdict == "MISMATCH"
    assert b2_threshold(b1, 70)[0].decision.verdict == "NOT_SURE"
    assert b2_threshold(b1, 50)[0].decision.verdict == "MISMATCH"
    votes = iter(['{"verdict": "SUPPORTED"}'] * 4 + ['{"verdict": "REFUTED"}'])
    assert b3_majority([t], reports, ScriptedLLM(lambda p, i, n: next(votes)))[0].decision.verdict == "NOT_SURE"
    assert b4_tools_no_rule([t], ScriptedLLM(lambda p, i, n: '{"verdict": "REFUTED"}'))[0].decision.verdict == "MISMATCH"


def test_a_sentence_cut_by_a_page_break_is_joined():
    from chart_claim_verifier.ingest.pdf_parser import merge_continued, split_sentences
    blocks = [(1, 700, 715, "Results go here and are discussed in the text below. ViT-S scores 9 points higher on IMDB than on"),
              (2, 28, 43, "SVHN (Figure 4)."),
              (2, 60, 75, "Figure 4: Accuracy by dataset."),
              (2, 90, 100, "3 Discussion"),
              (2, 110, 125, "More text follows here and ends properly.")]
    out = merge_continued(blocks)
    assert out[0][3].endswith("higher on IMDB than on SVHN (Figure 4).") and len(out) == 4
    assert split_sentences(out[0][3])[-1] == "ViT-S scores 9 points higher on IMDB than on SVHN (Figure 4)."
    assert merge_continued([(1, 780, 790, "2"), (2, 28, 43, "A new page starts here.")])[0][3] == "2"   # footer not joined


def test_a_cut_comparison_is_not_a_point_claim():
    assert RuleParser().parse("ViT-S scores 9 points higher on IMDB than on", "c") is None
    c = RuleParser().parse("ViT-S scores 9 points higher on IMDB than on SVHN (Figure 4).", "c")
    assert c.claim_type == "difference" and c.x == "IMDB" and c.x_b == "SVHN"
