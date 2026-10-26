"""U6: compare the four rules for a sentence that fits two figures, using the figure_runs stored in the traces.

    python scripts/ambiguous_rules.py -c configs/exp/local_real.yaml runs/local/u2_informed [runs/local/dev_P3 ...]

For each rule the claim is accepted (CONSISTENT) or sent to the TA (NOT_SURE); an ambiguous claim is never flagged.
Choose by missed errors first, then coverage.
"""
import argparse
import json
from pathlib import Path

from chart_claim_verifier.agent.report_agent import AMBIGUOUS_RULES, ambiguous_accepts
from chart_claim_verifier.config import load_config
from chart_claim_verifier.evaluation.metrics import join, summarize
from chart_claim_verifier.generator.build import load_truth
from chart_claim_verifier.pipeline import load_traces


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("-c", "--config", default=None)
    ap.add_argument("runs", nargs="+")
    args = ap.parse_args()
    cfg = load_config(args.config)
    for run in map(Path, args.runs):
        traces = load_traces(run / "traces_raw.jsonl")
        ids = json.loads((run / "truths.json").read_text())
        truths = [load_truth(Path(cfg["paths"]["data_dir"]) / rid.rsplit("_", 1)[0] / rid) for rid in ids]
        n_amb = sum(bool(t.figure_runs) for t in traces)
        print(f"\n{run.name}: {n_amb} ambiguous claims")
        print(f"  {'rule':8s} {'accepted':>9s} {'coverage':>9s} {'missed errors':>14s} {'wrong flags':>12s}")
        for rule in AMBIGUOUS_RULES:
            out = []
            for t in traces:
                if t.figure_runs:
                    t = t.model_copy(deep=True)
                    t.decision.verdict = ("CONSISTENT" if ambiguous_accepts(rule, [r["verdict"] for r in t.figure_runs.values()])
                                          else "NOT_SURE")
                out.append(t)
            m = summarize(join(out, truths))
            acc = sum(t.decision.verdict == "CONSISTENT" for t in out if t.figure_runs)
            print(f"  {rule:8s} {acc:9d} {m['coverage']:9.1%} {m['missed_errors']:14.1%} {m['wrong_flag_rate']:12.1%}")


if __name__ == "__main__":
    main()
