"""Find the figure a claim is about -- the RAG step (implementation.md §6.3).

Signals: an explicit "Figure N" in the sentence, and BM25 over each figure's
caption + OCR'd chart text (legend, ticks, title). A figure is only accepted if
the parsed series (and, for category axes, the x value) actually appear in it;
otherwise the claim is NO_FIGURE. An embedding scorer can be plugged in via
`embed` (bge-small on the GPU side).
"""
from __future__ import annotations

import re
from typing import Callable

from rank_bm25 import BM25Plus
from rapidfuzz import fuzz

from ..schemas import ClaimSpec, Figure


def tokenize(text: str) -> list[str]:
    toks = re.findall(r"[a-z0-9]+(?:[-.][a-z0-9]+)*", text.lower())
    out = []
    for t in toks:
        out.append(t)
        if "-" in t:
            out.extend(t.split("-"))
    return out


def figure_text(f: Figure) -> str:
    return " ".join([f.caption] + f.text_lines)


METRICS = {"accuracy": r"\baccurac", "loss": r"\bloss", "f1": r"\bf1\b", "precision": r"\bprecision",
           "recall": r"\brecall"}


def metric_words(text: str) -> set[str]:
    t = text.lower()
    return {m for m, pat in METRICS.items() if re.search(pat, t)}


class FigureIndex:
    def __init__(self, figures: list[Figure], ref_bonus: float = 10.0, vocab_match: int = 80,
                 embed: Callable[[str, list[str]], list[float]] | None = None, embed_weight: float = 2.0,
                 ambiguity_ratio: float = 0.8):
        self.figures = figures
        self.ref_bonus, self.vocab_match, self.ambiguity_ratio = ref_bonus, vocab_match, ambiguity_ratio
        self.embed, self.embed_weight = embed, embed_weight
        docs = [tokenize(figure_text(f)) or ["_"] for f in figures]
        self.bm25 = BM25Plus(docs) if figures else None      # BM25Plus: no negative scores on tiny corpora

    def rank(self, sentence: str, hint: int | None = None) -> list[tuple[Figure, float]]:
        if not self.figures:
            return []
        scores = list(self.bm25.get_scores(tokenize(sentence)))
        if self.embed:
            sims = self.embed(sentence, [figure_text(f) for f in self.figures])
            scores = [s + self.embed_weight * e for s, e in zip(scores, sims)]
        for i, f in enumerate(self.figures):
            if hint is not None and f.number == hint:
                scores[i] += self.ref_bonus
        return sorted(zip(self.figures, scores), key=lambda p: -p[1])

    def covers(self, f: Figure, claim: ClaimSpec) -> bool:
        """Does this figure show the claim's series (and x, for category axes)?"""
        vocab = [figure_text(f)] + f.text_lines

        tokens = set(tokenize(" ".join(vocab)))

        def present(term: str | None) -> bool:
            if not term:
                return True
            if len(term) <= 4:                            # "SVM" must not match "SVHN"
                return all(t in tokens for t in tokenize(term))
            return max(fuzz.partial_ratio(term.lower(), v.lower()) for v in vocab if v) >= self.vocab_match

        names = {claim.series, claim.series_b or claim.series}
        if not all(present(n) for n in names):
            return False
        said, shown = metric_words(claim.sentence), metric_words(figure_text(f))
        if said and shown and not (said & shown):         # "accuracy" claim vs a loss chart
            return False
        for x in {claim.x, claim.x_b or claim.x}:
            if _is_number(x):
                if f.chart_type not in ("line", "unknown"):
                    return False
            elif not present(x):
                return False
        return True

    def locate(self, claim: ClaimSpec) -> tuple[list[Figure], list[tuple[str, float]]]:
        """Figures that could be meant: one if clear, two if ambiguous, none -> NO_FIGURE."""
        ranked = self.rank(claim.sentence, claim.figure_hint)
        cands = [(f.figure_id, round(float(s), 3)) for f, s in ranked]
        covering = [(f, s) for f, s in ranked if self.covers(f, claim)]
        if not covering:
            return [], cands
        if claim.figure_hint is not None and covering[0][0].number == claim.figure_hint:
            return [covering[0][0]], cands                # an explicit "Figure N" settles it
        top = covering[0][1]
        close = [f for f, s in covering if s >= self.ambiguity_ratio * top]
        return close[:2], cands


def _is_number(s: str | None) -> bool:
    try:
        float(s)
        return True
    except (TypeError, ValueError):
        return False
