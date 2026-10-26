"""U8: evaluate the parse stage alone -- rules first, the LLM parser only when the rules do not recognise a sentence.

    python scripts/eval_parse.py -c configs/exp/phrasing.yaml --split phrasing [--rules-only]

No chart is read, so the only model cost is the LLM parses. For each gold claim:
  rules   the rule parser alone (a sentence it does not recognise counts as a miss)
  agent   rule parser, then the LLM parser when the rules return nothing (the escalation decision)
Reported: how many sentences the rules recognised, how many escalated, per-field accuracy of each, LLM calls per report.
"""
import argparse
from collections import Counter
from pathlib import Path

from chart_claim_verifier.agent.memory import ReportMemory
from chart_claim_verifier.claims.finder import is_candidate, strip_figure_refs
from chart_claim_verifier.claims.parser import LLMParser, ParseError, RuleParser
from chart_claim_verifier.claims.tolerance import find_numbers
from chart_claim_verifier.config import load_config
from chart_claim_verifier.evaluation.metrics import gold_lookup, norm
from chart_claim_verifier.generator.build import report_dirs
from chart_claim_verifier.pipeline import Context, ingest
from chart_claim_verifier.retrieval.figure_index import FigureIndex

FIELDS = ("claim_type", "series", "x", "value", "tolerance")


def fields_ok(c, g) -> dict:
    if c is None:
        return {f: False for f in FIELDS}
    return {"claim_type": c.claim_type == g["claim_type"], "series": norm(c.series) == norm(g["series"]),
            "x": norm(c.x) == norm(g["x"]),
            "value": g.get("claimed_value") is not None and abs(c.claimed_value - g["claimed_value"]) < 1e-9,
            "tolerance": g.get("tolerance") is None or abs(c.tolerance - g["tolerance"]) < 1e-9}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("-c", "--config", default=None)
    ap.add_argument("--split", default="phrasing")
    ap.add_argument("--rules-only", action="store_true", help="skip the LLM (no model is loaded)")
    args = ap.parse_args()
    ctx = Context(load_config(args.config))
    rules, llm = RuleParser(), None if args.rules_only else LLMParser(ctx.llm)
    acc = {"rules": Counter(), "agent": Counter()}
    n = n_rule = n_esc = n_llm_fail = llm_calls = 0
    dirs = report_dirs(ctx.data, args.split)
    for rd in dirs:
        report, truth = ingest(ctx, rd)
        gold = gold_lookup([truth])
        context = ReportMemory(report, FigureIndex(report.figures)).context()
        for s in report.sentences:
            g = gold.get((report.report_id, norm(s.text)))
            if g is None or g["gold"] not in ("correct", "error") or not is_candidate(s.text):
                continue
            if not find_numbers(strip_figure_refs(s.text)):
                continue
            n += 1
            c = rules.parse(s.text, s.sentence_id, context)
            n_rule += c is not None
            ok_rules = fields_ok(c, g)
            ok_agent = ok_rules
            if c is None and llm is not None:                       # the escalation decision
                n_esc += 1
                try:
                    c2 = llm.parse(s.text, s.sentence_id, context)
                except ParseError:
                    c2, n_llm_fail = None, n_llm_fail + 1
                llm_calls += len(llm.last_raw)
                ok_agent = fields_ok(c2, g)
            for f in FIELDS:
                acc["rules"][f] += ok_rules[f]
                acc["agent"][f] += ok_agent[f]
    print(f"{args.split}: {len(dirs)} reports, {n} chart claims")
    print(f"  recognised by the rules: {n_rule} ({n_rule / max(n, 1):.0%});  escalated to the LLM parser: {n_esc};  "
          f"LLM parse failures: {n_llm_fail};  LLM calls: {llm_calls} ({llm_calls / max(len(dirs), 1):.1f} per report)")
    print(f"  {'field':12s} {'rules only':>11s} {'agent':>8s}")
    for f in FIELDS:
        print(f"  {f:12s} {acc['rules'][f] / max(n, 1):11.0%} {acc['agent'][f] / max(n, 1):8.0%}")


if __name__ == "__main__":
    main()
