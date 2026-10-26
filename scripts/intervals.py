"""95% bootstrap intervals for coverage, wrong flags and missed errors of saved runs.

    python scripts/intervals.py runs/local/final_dev_informed runs/local/final_test_informed ...

Claims of one report share figures, so whole REPORTS are resampled, not single claims.
"""
import json
import random
import sys
from collections import defaultdict
from pathlib import Path

from chart_claim_verifier.evaluation.metrics import coverage, join
from chart_claim_verifier.generator.build import load_truth
from chart_claim_verifier.pipeline import load_traces

DATA = Path("data/local/generated")


def wrong_flags(rows):
    f = [r for r in rows if r.verdict == "MISMATCH"]
    return sum(r.gold != "error" for r in f) / len(f) if f else float("nan")


def missed(rows):
    e = [r for r in rows if r.gold == "error"]
    return sum(r.verdict == "CONSISTENT" for r in e) / len(e) if e else float("nan")


def interval(by_report, stat, n=1000, seed=0):
    rng, ids, vals = random.Random(seed), list(by_report), []
    for _ in range(n):
        rows = [r for rid in (rng.choice(ids) for _ in ids) for r in by_report[rid]]
        v = stat(rows)
        if v == v:
            vals.append(v)
    vals.sort()
    return vals[int(0.025 * len(vals))], vals[int(0.975 * len(vals)) - 1]


def main(runs):
    for run in map(Path, runs):
        ids = json.loads((run / "truths.json").read_text())
        truths = [load_truth(DATA / rid.rsplit("_", 1)[0] / rid) for rid in ids]
        rows = join(load_traces(run / "traces_raw.jsonl"), truths)
        by = defaultdict(list)
        for r in rows:
            by[r.report_id].append(r)
        print(f"\n{run.name}: {len(by)} reports, {len(rows)} rows")
        for name, stat in (("coverage", coverage), ("wrong flags", wrong_flags), ("missed errors", missed)):
            lo, hi = interval(by, stat)
            print(f"  {name:14s} {stat(rows):6.1%}   95% interval [{lo:.1%}, {hi:.1%}]")


if __name__ == "__main__":
    main(sys.argv[1:])
