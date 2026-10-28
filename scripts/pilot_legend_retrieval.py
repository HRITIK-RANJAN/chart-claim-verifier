"""U11b pilot: can VLM-read legend names rescue claims that OCR made NO_FIGURE -- without inventing figures?

    PYTHONPATH=. python scripts/pilot_legend_retrieval.py -c configs/exp/local_real.yaml runs/local/u11a_test_informed runs/local/u11a_dev_informed

For every NO_FIGURE verdict, the figures that match the claim except for its series name get their legend read by the
VLM (one cached call per figure, shared with the U7 repair). The names are added to the figure's vocabulary and
`covers` is asked again. GO only if
  * at least half of the WRONG NO_FIGURE verdicts (the figure exists) find their figure, and
  * none of the RIGHT NO_FIGURE verdicts (no chart shows the series) finds one.
"""
import argparse
import json
from pathlib import Path

from chart_claim_verifier.config import load_config
from chart_claim_verifier.evaluation.metrics import join
from chart_claim_verifier.generator.build import load_truth
from chart_claim_verifier.pipeline import Context, ingest, load_traces
from chart_claim_verifier.retrieval.figure_index import FigureIndex
from chart_claim_verifier.tools.legend import read_legend


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("-c", "--config", default=None)
    ap.add_argument("runs", nargs="+")
    ap.add_argument("--save-names", default=None, help="write {image_path: names} for later use")
    args = ap.parse_args()
    ctx = Context(load_config(args.config))
    names_of, wrong, right = {}, [], []
    for run in map(Path, args.runs):
        ids = json.loads((run / "truths.json").read_text())
        truths = [load_truth(ctx.data / rid.rsplit("_", 1)[0] / rid) for rid in ids]
        reports = {}
        for r in join(load_traces(run / "traces_raw.jsonl"), truths):
            if r.verdict != "NO_FIGURE" or not r.trace.claim:
                continue
            rid = r.report_id
            if rid not in reports:
                reports[rid] = ingest(ctx, ctx.data / rid.rsplit("_", 1)[0] / rid)[0]
            rep, claim = reports[rid], r.trace.claim
            idx = FigureIndex(rep.figures)
            blank = claim.model_copy(update={"series": "", "series_b": None})
            near = [f for f in rep.figures if idx.covers(f, blank)]
            found = []
            for f in near:
                if f.image_path not in names_of:
                    names_of[f.image_path] = read_legend(ctx.llm, f, ctx.cache) or []
                aug = f.model_copy(update={"text_lines": f.text_lines + names_of[f.image_path]})
                if FigureIndex([aug]).covers(aug, claim):
                    found.append(f.figure_id)
            (right if r.gold == "no_figure" else wrong).append((run.name, rid, claim.series, found, r.sentence))
    for title, group in (("WRONG NO_FIGURE (figure exists)", wrong), ("RIGHT NO_FIGURE (no chart shows it)", right)):
        print(f"\n{title}: {len(group)}")
        for run, rid, series, found, sent in group:
            print(f"  {'FOUND ' + ','.join(found) if found else 'none':12s} {rid} {series!r}: {sent[:70]}")
    rec = sum(bool(g[3]) for g in wrong)
    false = sum(bool(g[3]) for g in right)
    print(f"\nrecovered {rec}/{len(wrong)} wrong NO_FIGUREs; invented a figure for {false}/{len(right)} right ones")
    print(f"legend calls: {len(names_of)}")
    print("GO" if wrong and rec / len(wrong) >= 0.5 and false == 0 else "NO-GO")
    if args.save_names:
        Path(args.save_names).write_text(json.dumps(names_of))


if __name__ == "__main__":
    main()
