"""U7 pilot: does reading the legend with the VLM repair `ocr_pixel`'s "series_not_found"? (go / no-go)

    PYTHONPATH=. python scripts/pilot_legend.py -c configs/exp/local_real.yaml [--save]

For every calibration figure on which ocr_pixel failed with series_not_found (at most 14 VLM calls, one per
figure), read the legend with the VLM, hand it to ocr_pixel, and read every point of the figure again.
GO only if all three hold:
  * at least 50% of the series_not_found points now read
  * those new readings are badly wrong (> 5% of the axis) at most 5% of the time
  * the repaired ocr_pixel agrees on a WRONG value with vlm_crop at most 5% of the time (a VLM that misreads
    the legend would send ocr_pixel to the wrong line: a mistake shared with vlm_crop)
With --save and GO, the result is written into the tool profile ("repairs") so the planner may propose the repair.
"""
import argparse
import json
import statistics
import time
from collections import Counter
from pathlib import Path

from rapidfuzz import fuzz

from chart_claim_verifier.config import load_config
from chart_claim_verifier.generator.build import report_dirs
from chart_claim_verifier.generator.tables import ChartTable
from chart_claim_verifier.pipeline import Context, ingest, load_profile
from chart_claim_verifier.schemas import PointQuery
from chart_claim_verifier.tools.base import image_key
from chart_claim_verifier.tools.legend import read_legend
from chart_claim_verifier.evaluation.tool_profile import save_profile

BIG, AGREE = 0.05, 0.03


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("-c", "--config", default=None)
    ap.add_argument("--save", action="store_true")
    args = ap.parse_args()
    cfg = load_config(args.config)
    ctx = Context(cfg)
    names = list(cfg["tools"]["enabled"])
    out = Path(cfg["paths"]["calibration_dir"])
    stem = "_".join(names)
    errors = json.loads((out / f"{stem}.errors.json").read_text())
    failed_before = {(e["figure"], e["series"], e["x"]) for e in errors if e["_fail"].get("ocr_pixel") == "series_not_found"}
    figures = sorted({f for f, _, _ in failed_before})
    ocr, crop, llm = ctx.tools(["ocr_pixel"])["ocr_pixel"], ctx.tools(["vlm_crop"])["vlm_crop"], ctx.llm

    newly_read, newly_big, legend_ok, legend_n = [], [], 0, 0
    agree = agree_wrong = both = 0
    secs, codes = [], Counter()
    for split in cfg.get("calibration", {}).get("splits", ["calib"]):
        for rd in report_dirs(ctx.data, split):
            report, truth = ingest(ctx, rd)
            by_num = {f["number"]: f for f in truth["figures"]}
            for fig in report.figures:
                if fig.image_path not in figures or fig.number not in by_num:
                    continue
                table = ChartTable.from_dict(by_num[fig.number]["table"])
                t0 = time.perf_counter()
                legend = read_legend(llm, fig, ctx.cache)
                secs.append(time.perf_counter() - t0)
                legend_n += 1
                ok = bool(legend) and len(legend) == len(table.series) and all(
                    max(fuzz.token_set_ratio(n.lower(), s.lower()) for n in legend) >= 70 for s in table.series)
                legend_ok += ok
                print(f"{rd.name} {fig.figure_id}: legend {legend}  true series {list(table.series)}  {'OK' if ok else 'DIFFERENT'}",
                      flush=True)
                if legend:
                    ocr.legend_hint[image_key(fig.image_path)] = legend
                for s in table.series:
                    for x in table.x_values:
                        truth_v = table.value(s, x)
                        r = ocr.read(fig, PointQuery(series=s, x=x))
                        if not r.ok:
                            codes[r.error] += (fig.image_path, s, x) in failed_before
                            continue
                        err = (r.value - truth_v) / table.span
                        if (fig.image_path, s, x) in failed_before:
                            newly_read.append(err)
                            newly_big.append(abs(err) > BIG)
                        c = crop.read(fig, PointQuery(series=s, x=x))
                        if c.ok:
                            both += 1
                            ce = (c.value - truth_v) / table.span
                            if abs(err - ce) <= AGREE:
                                agree += 1
                                agree_wrong += abs((err + ce) / 2) > BIG
    fixed = len(newly_read) / max(len(failed_before), 1)
    big = sum(newly_big) / max(len(newly_big), 1)
    wwa = agree_wrong / agree if agree else float("nan")
    go = fixed >= 0.5 and big <= 0.05 and wwa <= 0.05
    print(f"\nfigures with the failure: {len(figures)}; legend read matches the true series on {legend_ok}/{legend_n}")
    print(f"series_not_found points: {len(failed_before)}; now read: {len(newly_read)} ({fixed:.0%}); still failing: {dict(codes)}")
    print(f"newly read values badly wrong: {big:.1%}")
    print(f"repaired ocr_pixel ~ vlm_crop: both answered {both}, agree {agree}, wrong when agreeing {agree_wrong} ({wwa:.1%})")
    print(f"VLM seconds per figure (median): {statistics.median(secs) if secs else 0:.1f}")
    print("GO" if go else "NO-GO")
    if args.save and go:
        prof = load_profile(ctx)
        prof.setdefault("repairs", {})["ocr_pixel:series_not_found"] = {
            "repair": "read_legend", "fixed": fixed, "n": len(failed_before), "big_error": big,
            "wrong_when_agree_vlm_crop": wwa, "seconds": statistics.median(secs)}
        prof["cost"]["repair:read_legend"] = {"seconds_per_figure": statistics.median(secs), "seconds_per_read": None}
        save_profile(prof, out / f"{stem}.profile.json")
        print("saved to the profile")


if __name__ == "__main__":
    main()
