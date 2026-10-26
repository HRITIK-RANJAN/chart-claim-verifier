import random

from chart_claim_verifier.claims.finder import is_candidate
from chart_claim_verifier.claims.parser import RuleParser
from chart_claim_verifier.generator.claims import figure_claims
from chart_claim_verifier.generator.tables import make_table


def test_novel_phrasings_are_claims_the_rule_parser_does_not_know():
    rng = random.Random(3)
    sentences = []
    for i in range(12):
        t = make_table(rng, f"t{i}", hard=False)
        sentences += [c.sentence for c in figure_claims(rng, t, "fig1", 1, 4, [0.1], f"r{i}_", novel=1.0)]
    assert sentences
    assert all(is_candidate(s) for s in sentences)
    assert all(RuleParser().parse(s, "c") is None for s in sentences)


def test_no_novel_phrasing_leaves_the_random_stream_unchanged():
    a, b = random.Random(5), random.Random(5)
    t1, t2 = make_table(a, "t", hard=False), make_table(b, "t", hard=False)
    x = [c.sentence for c in figure_claims(a, t1, "fig1", 1, 4, [0.1], "r_")]
    y = [c.sentence for c in figure_claims(b, t2, "fig1", 1, 4, [0.1], "r_", novel=0.0)]
    assert x == y
