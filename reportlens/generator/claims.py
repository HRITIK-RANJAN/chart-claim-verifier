"""Generate sentences to check, with known labels (implementation.md §9.1).

Kinds (approximate shares among chart claims):
    correct_exact    20%   no error
    correct_rounded  20%   no error (incl. hedged "about 80%" and one-sided "over 80%")
    planted          35%   error of known size delta (fraction of axis range)
    mixup            10%   wrong series / wrong x-point
    no_figure        per report: claims about models/datasets no figure shows
    not_a_claim      per report: setup sentences with numbers ("trained for 50 epochs")

Labels use the same tolerance function as the checker (claims.tolerance), so
"correct" means "correct within the rounding its wording allows".
"""
from __future__ import annotations

import math
import random
from dataclasses import asdict, dataclass

from ..claims.tolerance import find_numbers, is_within
from .tables import DATASETS, OUTSIDE_DATASETS, OUTSIDE_MODELS, ChartTable


@dataclass
class ClaimRecord:
    claim_id: str
    sentence: str
    figure_id: str | None          # the figure that covers it (None for no_figure / not_a_claim)
    kind: str
    gold: str                      # "correct" | "error" | "no_figure" | "skip"
    claim_type: str | None = None
    series: str | None = None
    x: str | None = None
    series_b: str | None = None
    x_b: str | None = None
    true_value: float | None = None
    claimed_value: float | None = None
    tolerance: float | None = None
    relation: str = "approx"
    delta: float | None = None     # planted error, signed, fraction of axis range
    span: float | None = None
    cites_figure: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


# ------------------------------------------------------------------ formatting
def fmt(value: float, decimals: int, percent: bool) -> str:
    s = f"{value:.{decimals}f}"
    return s + ("%" if percent else "")


def rounded_variant(rng: random.Random, value: float, decimals: int, percent: bool,
                    allow_bound: bool = True) -> tuple[str, str]:
    """A correctly rounded / hedged / one-sided rendering. Returns (text, relation)."""
    r = rng.random() * (1.0 if allow_bound else 0.8)
    if r < 0.45:                                     # fewer decimals
        d = max(0, decimals - 1)
        return fmt(round(value, d), d, percent), "approx"
    if r < 0.8:                                      # hedged
        if percent and value >= 10:
            return "about " + fmt(round(value / 10) * 10, 0, percent), "approx"
        d = max(0, decimals - 2)
        return "about " + fmt(round(value, d), d, percent), "approx"
    step = 5 if percent else 0.1                     # one-sided, safely true
    bound = math.floor((value - 1e-6) / step) * step
    if value - bound < (1.0 if percent else 0.02):
        bound -= step
    return "over " + fmt(bound, 0 if percent else 1, percent), "greater"


def _measured(text: str):
    """Value, tolerance and relation exactly as the checker will read them."""
    n = find_numbers(text)[-1]
    sign = -1 if text.strip().startswith("-") else 1
    return sign * abs(n.value), n.tolerance, n.relation


# ------------------------------------------------------------------ templates
def point_sentence(rng, t: ChartTable, series: str, x: str, vtxt: str) -> str:
    w = t.metric_word
    if t.kind == "line":
        if not t.percent:
            return rng.choice([f"{series} has a {w} of {vtxt} at epoch {x}.",
                               f"At epoch {x}, the {w} of {series} is {vtxt}."])
        return rng.choice([f"{series} reaches {vtxt} {w} at epoch {x}.",
                           f"At epoch {x}, {series} achieves {vtxt} {w}.",
                           f"{series} attains a {w} of {vtxt} at epoch {x}."])
    return rng.choice([f"{series} achieves {vtxt} {w} on {x}.",
                       f"On {x}, {series} obtains a {w} of {vtxt}.",
                       f"{series} reaches {vtxt} {w} on {x}."])


def difference_sentence(rng, t: ChartTable, a: str, b: str, x: str, vtxt: str) -> str:
    where = f"at epoch {x}" if t.kind == "line" else f"on {x}"
    return rng.choice([f"{a} outperforms {b} by {vtxt} percentage points {where}.",
                       f"{where[0].upper()}{where[1:]}, {a} is {vtxt} points better than {b}."])


def across_x_sentence(rng, t: ChartTable, s: str, x1: str, x2: str, vtxt: str) -> str:
    return f"{s} scores {vtxt} points higher on {x1} than on {x2}."


def relative_sentence(rng, t: ChartTable, s: str, x1: str, x2: str, vtxt: str) -> str:
    return f"From epoch {x1} to epoch {x2}, the {t.metric_word} of {s} improves by a relative {vtxt}."


def cite(rng, sentence: str, number: int) -> str:
    if rng.random() < 0.5:
        if sentence.startswith(("At ", "On ", "From ")):
            sentence = sentence[0].lower() + sentence[1:]
        return f"As shown in Figure {number}, {sentence}"
    return sentence[:-1] + f" (Figure {number})."


# ------------------------------------------------------------------ generator
def _pick_target(rng, t: ChartTable):
    """Choose a claim type and operands. Returns (claim_type, operands, true_value, render)."""
    names = list(t.series)
    xs = t.x_values
    options = ["point"] * 6
    if t.percent and (len(names) > 1 or len(xs) > 1):
        options += ["difference"] * 3
    if t.percent and t.kind == "line":
        options += ["relative_change"] * 2
    ctype = rng.choice(options)

    if ctype == "point":
        s, x = rng.choice(names), rng.choice(xs)
        return ctype, (s, x, None, None), t.value(s, x)
    if ctype == "difference":
        if len(names) > 1:
            x = rng.choice(xs)
            a, b = sorted(rng.sample(names, 2), key=lambda n: -t.value(n, x))
            ops = (a, x, b, x)
        else:
            s = names[0]
            x1, x2 = sorted(rng.sample(xs, 2), key=lambda v: -t.value(s, v))
            ops = (s, x1, s, x2)
        diff = t.value(ops[0], ops[1]) - t.value(ops[2], ops[3])
        if diff >= 1.0:                          # "better by 0.3 points" is not a useful claim
            return ctype, ops, diff
        return "point", (ops[0], ops[1], None, None), t.value(ops[0], ops[1])
    s = rng.choice(names)
    i1 = rng.randrange(0, len(xs) - 1)
    i2 = rng.randrange(i1 + 1, len(xs))
    a, b = t.value(s, xs[i1]), t.value(s, xs[i2])
    if b <= a:                                   # only "improves" claims
        return "point", (s, xs[i2], None, None), b
    return ctype, (s, xs[i1], None, xs[i2]), (b - a) / abs(a) * 100


def _render(rng, t, ctype, ops, vtxt) -> str:
    s, x, sb, xb = ops
    if ctype == "point":
        return point_sentence(rng, t, s, x, vtxt)
    if ctype == "difference":
        if sb == s:
            return across_x_sentence(rng, t, s, x, xb, vtxt)
        return difference_sentence(rng, t, s, sb, x, vtxt)
    return relative_sentence(rng, t, s, x, xb, vtxt)


def figure_claims(rng: random.Random, t: ChartTable, figure_id: str, figure_number: int,
                  n: int, deltas: list[float], id_prefix: str) -> list[ClaimRecord]:
    out = []
    span = t.span
    for j in range(n):
        ctype, ops, truth = _pick_target(rng, t)
        s, x, sb, xb = ops
        pct_fmt = (ctype == "point" and t.percent) or ctype == "relative_change"
        dec = t.decimals if ctype == "point" else 1
        kind = rng.choices(["correct_exact", "correct_rounded", "planted", "mixup"], [20, 20, 35, 10])[0]
        delta = None
        claimed_true = truth

        if kind == "mixup":
            names = list(t.series)
            if ctype == "point" and len(names) > 1:
                other = rng.choice([n_ for n_ in names if n_ != s])
                claimed_true = t.value(other, x)                    # value belongs to another series
            elif ctype == "point":
                i = t.x_values.index(x)
                claimed_true = t.value(s, t.x_values[i - 1 if i > 0 else i + 1])   # neighbouring x
            else:
                kind = "planted"

        if kind == "correct_exact":
            vtxt = fmt(truth, dec, pct_fmt)
        elif kind == "correct_rounded":
            vtxt, _ = rounded_variant(rng, truth, dec, pct_fmt, allow_bound=ctype == "point")
        elif kind == "mixup":
            vtxt = fmt(claimed_true, dec, pct_fmt)
        else:                                                       # planted
            delta = rng.choice(deltas) * rng.choice([-1, 1])
            if ctype == "relative_change":                          # perturb the end value
                a = t.value(s, x)
                b_wrong = t.value(s, xb) + delta * span
                claimed_true = (b_wrong - a) / abs(a) * 100
            else:
                claimed_true = truth + delta * span
            if ctype == "difference" and claimed_true <= 0:
                delta, claimed_true = abs(delta), truth + abs(delta) * span
            if ctype == "relative_change" and claimed_true <= 0:
                delta = abs(delta)
                claimed_true = (t.value(s, xb) + delta * span - t.value(s, x)) / abs(t.value(s, x)) * 100
            vtxt = fmt(claimed_true, dec, pct_fmt)

        sentence = _render(rng, t, ctype, ops, vtxt)
        cites = rng.random() < 0.5
        if cites:
            sentence = cite(rng, sentence, figure_number)
        claimed, tol, rel = _measured(vtxt)
        correct = is_within(claimed, truth, tol, rel)
        if kind.startswith("correct") and not correct:              # rounding edge case
            continue
        if kind in ("planted", "mixup") and correct:                # error too small to be one
            continue
        out.append(ClaimRecord(
            claim_id=f"{id_prefix}c{j}", sentence=sentence, figure_id=figure_id, kind=kind,
            gold="correct" if correct else "error", claim_type=ctype, series=s, x=x, series_b=sb, x_b=xb,
            true_value=round(truth, 6), claimed_value=claimed, tolerance=tol, relation=rel,
            delta=delta, span=span, cites_figure=cites))
    return out


def no_figure_claim(rng: random.Random, claim_id: str) -> ClaimRecord:
    model, data = rng.choice(OUTSIDE_MODELS), rng.choice(OUTSIDE_DATASETS + DATASETS)
    v = round(rng.uniform(50, 95), 1)
    sentence = rng.choice([f"{model} reaches {v}% accuracy on {data}.",
                           f"On {data}, {model} obtains an accuracy of {v}%."])
    return ClaimRecord(claim_id=claim_id, sentence=sentence, figure_id=None, kind="no_figure",
                       gold="no_figure", claim_type="point", series=model, x=data, claimed_value=v)


def setup_sentences(rng: random.Random) -> list[str]:
    return rng.sample([
        f"We trained each model for {rng.choice([20, 30, 50, 100])} epochs with a batch size of {rng.choice([32, 64, 128])}.",
        f"The learning rate was set to {rng.choice(['0.001', '0.0003', '0.01'])} with the Adam optimizer.",
        f"Each experiment was repeated {rng.choice([3, 5])} times with different random seeds.",
        f"All experiments were run on a single GPU with {rng.choice([12, 16, 24])} GB of memory.",
        f"The dataset was split into {rng.choice([70, 80])} percent training data and the rest for testing.",
    ], 2)
