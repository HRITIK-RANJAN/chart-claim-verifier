"""95% bootstrap intervals for coverage, wrong flags and missed errors of saved runs.

    python scripts/intervals.py runs/local/final_dev_informed runs/local/final_test_informed ...

Claims of one report share figures, so whole REPORTS are resampled, not single claims.
"""
import json
import sys
from pathlib import Path

from chart_claim_verifier.evaluation.metrics import bootstrap, coverage, join
from chart_claim_verifier.generator.build import load_truth
from chart_claim_verifier.pipeline import load_traces

DATA = Path("data/local/generated")


def wrong_flags(rows):
    f = [r for r in rows if r.verdict == "MISMATCH"]
    return sum(r.gold != "error" for r in f) / len(f) if f else float("nan")


def missed(rows):
    e = [r for r in rows if r.gold == "error"]
    return sum(r.verdict == "CONSISTENT" for r in e) / len(e) if e else float("nan")


def main(runs):
    for run in map(Path, runs):
        ids = json.loads((run / "truths.json").read_text())
        truths = [load_truth(DATA / rid.rsplit("_", 1)[0] / rid) for rid in ids]
        rows = join(load_traces(run / "traces_raw.jsonl"), truths)
        print(f"\n{run.name}: {len({r.report_id for r in rows})} reports, {len(rows)} rows")
        for name, stat in (("coverage", coverage), ("wrong flags", wrong_flags), ("missed errors", missed)):
            lo, hi = bootstrap(rows, stat, n=1000)
            print(f"  {name:14s} {stat(rows):6.1%}   95% interval [{lo:.1%}, {hi:.1%}]")


if __name__ == "__main__":
    main(sys.argv[1:])
