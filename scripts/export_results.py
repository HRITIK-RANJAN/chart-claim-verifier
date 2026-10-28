"""R1: write results/ from saved runs -- numbers, every claim, and a few reports with their PDFs.

    python scripts/export_results.py --run test=mc_test dev=mc_dev holdout=mc_holdout holdout2=holdout2 --out results

`--run SPLIT=PREFIX` reads runs/local/<PREFIX>_<policy> (informed = the main method; all_tools and fixed_order are shown
for comparison). Without --run it uses <tag>_<split>. No model is called. See implementation.md §24 (R1).
"""
import argparse
import csv
import json
import shutil
from collections import Counter, defaultdict
from pathlib import Path

from chart_claim_verifier.evaluation.metrics import (DECIDED, bootstrap, catch_rates_measured, coverage, join,
                                                     summarize)
from chart_claim_verifier.generator.build import load_truth
from chart_claim_verifier.pipeline import load_traces

DATA = Path("data/local/generated")
PROFILE = Path("calibration_tables/local/ocr_pixel_deplot_vlm_table_vlm_crop.profile.json")
RUNS = Path("runs/local")
POLICIES = ("all_tools", "fixed_order", "informed")
MAIN = "informed"
VERDICTS = ("CONSISTENT", "MISMATCH", "NOT_SURE", "NO_FIGURE")


def load_rows(run: Path):
    ids = json.loads((run / "truths.json").read_text())
    truths = [load_truth(DATA / rid.rsplit("_", 1)[0] / rid) for rid in ids]
    rows = join(load_traces(run / "traces_raw.jsonl"), truths)
    return [r for r in rows if r.gold in ("correct", "error", "no_figure")]


def outcome(r) -> str:
    if r.verdict == "NOT_SURE":
        return "handed off"
    right = {"CONSISTENT": "correct", "MISMATCH": "error", "NO_FIGURE": "no_figure"}.get(r.verdict)
    return "right" if right == r.gold else "wrong"


def wrong_flags(rows):
    f = [r for r in rows if r.verdict == "MISMATCH"]
    return sum(r.gold != "error" for r in f) / len(f) if f else float("nan")


def missed(rows):
    e = [r for r in rows if r.gold == "error"]
    return sum(r.verdict == "CONSISTENT" for r in e) / len(e) if e else float("nan")


def accuracy_decided(rows):
    d = [r for r in rows if r.verdict in DECIDED]
    return sum(outcome(r) == "right" for r in d) / len(d) if d else float("nan")


def accuracy_all(rows):
    return sum(outcome(r) == "right" for r in rows) / len(rows) if rows else float("nan")


def pct(v) -> str:
    return "-" if v != v else f"{v:.1%}"


def with_interval(rows, stat) -> str:
    lo, hi = bootstrap(rows, stat, n=1000)
    return f"{pct(stat(rows))} [{pct(lo)}, {pct(hi)}]"


def model_minutes(run: Path) -> str:
    """Estimated model time: calls per tool x the measured seconds per call (tool profile)."""
    try:
        cost = {t: (c.get("seconds_per_figure") if t in ("deplot", "vlm_table") else c.get("seconds_per_read")) or 0.0
                for t, c in json.loads(PROFILE.read_text())["cost"].items()}
        calls = json.loads((run / "metrics.json").read_text())["run"].get("calls_by_tool") or {}
        return f"{sum(cost.get(t, 0.0) * k for t, k in calls.items()) / 60:.1f} min"
    except (OSError, KeyError, ValueError):
        return "-"


# ---------------------------------------------------------------------------------------------- tables
def method_table(split: str, runs: dict, dirs: dict) -> list[str]:
    out = [f"### {split}", "",
           "| Method | Claims | Coverage | Accuracy when decided | Accuracy overall | Wrong flags | Missed errors | Model time |",
           "|---|---|---|---|---|---|---|---|"]
    for p in POLICIES:
        rows = runs[p]
        out.append(f"| {p}{' (main)' if p == MAIN else ''} | {len(rows)} | {with_interval(rows, coverage)} | "
                   f"{with_interval(rows, accuracy_decided)} | {with_interval(rows, accuracy_all)} | "
                   f"{with_interval(rows, wrong_flags)} | {with_interval(rows, missed)} | {model_minutes(dirs[p])} |")
    return out + [""]


def confusion(rows) -> list[str]:
    c = Counter((r.gold, r.verdict) for r in rows)
    out = ["| Truth \\ Verdict | " + " | ".join(VERDICTS) + " |", "|---|" + "---|" * len(VERDICTS)]
    for g, name in (("correct", "claim is right"), ("error", "claim is wrong"), ("no_figure", "no chart shows it")):
        out.append(f"| {name} | " + " | ".join(str(c[(g, v)]) for v in VERDICTS) + " |")
    return out + [""]


def breakdown(rows, key, title) -> list[str]:
    by = defaultdict(list)
    for r in rows:
        by[key(r)].append(r)
    out = [f"| {title} | Claims | Decided | Right of decided | Handed off |", "|---|---|---|---|---|"]
    for k, rs in sorted(by.items(), key=lambda kv: str(kv[0])):
        d = [r for r in rs if r.verdict in DECIDED]
        out.append(f"| {k} | {len(rs)} | {len(d)} | "
                   f"{sum(outcome(r) == 'right' for r in d)}/{len(d)} | {sum(r.verdict == 'NOT_SURE' for r in rs)} |")
    return out + [""]


def catch_table(rows) -> list[str]:
    out = ["| Planted error size | Errors | Measured (2+ readings) | Flagged of measured | Flagged of all |", "|---|---|---|---|---|"]
    allv = defaultdict(list)
    for r in rows:
        if r.gold == "error" and r.kind == "planted" and r.delta is not None:
            allv[round(abs(r.delta), 4)].append(r.verdict == "MISMATCH")
    for d, m in catch_rates_measured(rows).items():
        out.append(f"| {d:g} | {m['errors']} | {m['measured']} | {m['caught']}/{m['measured']} | "
                   f"{sum(allv[d])}/{len(allv[d])} |")
    return out + [""]


def per_report(rows) -> list[str]:
    by = defaultdict(list)
    for r in rows:
        by[r.report_id].append(r)
    out = ["| Report | Claims | Right | Wrong | Handed off |", "|---|---|---|---|---|"]
    for rid, rs in sorted(by.items()):
        c = Counter(outcome(r) for r in rs)
        out.append(f"| {rid} | {len(rs)} | {c['right']} | {c['wrong']} | {c['handed off']} |")
    return out + [""]


# ---------------------------------------------------------------------------------------------- claims
FIELDS = ["report_id", "sentence", "truth", "claim_kind", "claim_type", "chart_type", "planted_error_size",
          "true_value", "estimate", "flag_margin", "verdict", "outcome", "reason", "tools_used", "tool_calls",
          "figure_true", "figure_found"]


def claim_row(r) -> dict:
    d = r.trace.decision
    return {"report_id": r.report_id, "sentence": r.sentence, "truth": r.gold, "claim_kind": r.kind,
            "claim_type": r.claim_type, "chart_type": r.chart_type, "planted_error_size": r.delta,
            "true_value": r.true_value, "estimate": None if d.estimate is None else round(d.estimate, 4),
            "flag_margin": None if d.margin_flag is None else round(d.margin_flag, 4), "verdict": r.verdict,
            "outcome": outcome(r), "reason": d.reason, "tools_used": " ".join(sorted(r.trace.tool_values)),
            "tool_calls": r.tool_calls, "figure_true": r.figure_true, "figure_found": r.figure_pred}


def write_csv(path: Path, rows) -> None:
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, FIELDS)
        w.writeheader()
        w.writerows(claim_row(r) for r in rows)


# ---------------------------------------------------------------------------------------------- examples
def pick_examples(by_split: dict, n: int) -> list[tuple[str, str, str]]:
    """(split, report_id, why chosen) by fixed rules, so failures are shown as well as successes."""
    reports = {}
    for split, rows in by_split.items():
        by = defaultdict(list)
        for r in rows:
            by[r.report_id].append(r)
        for rid, rs in by.items():
            reports[(split, rid)] = rs

    rules = [
        ("the report with the most claims (test)", "test",
         lambda rs: len(rs)),
        ("a wrongly flagged claim", None,
         lambda rs: sum(r.verdict == "MISMATCH" and r.gold != "error" for r in rs) * 100 + len(rs)),
        ("a figure that exists was reported as NO_FIGURE", None,
         lambda rs: sum(r.verdict == "NO_FIGURE" and r.gold != "no_figure" for r in rs) * 100 + len(rs)),
        ("a sentence that fits two figures", None,
         lambda rs: sum(r.trace.decision.reason.startswith("ambiguous") for r in rs) * 100 + len(rs)),
        ("every decided claim is right (test)", "test",
         lambda rs: (all(outcome(r) != "wrong" for r in rs)) * 100 + len(rs)),
    ]
    chosen, seen = [], set()
    for why, only, score in rules[:n]:
        cands = [(score(rs), (s, rid)) for (s, rid), rs in reports.items()
                 if (only is None or s == only) and (s, rid) not in seen]
        cands = [c for c in cands if c[0] > 0]
        if not cands:
            continue
        _, (s, rid) = sorted(cands, key=lambda c: (-c[0], c[1][0], c[1][1]))[0]
        seen.add((s, rid))
        chosen.append((s, rid, why))
    return chosen


def evidence(r) -> str:
    d = r.trace.decision
    vals = ", ".join(f"{k} {v:.3g}" for k, v in sorted(r.trace.tool_values.items())) or "none"
    fig = r.figure_pred or "none"
    margin = "-" if d.margin_flag is None else f"{d.margin_flag:.3g}"
    est = "-" if d.estimate is None else f"{d.estimate:.3g}"
    truth = "-" if r.true_value is None else f"{r.true_value:.3g}"
    return (f"figure {fig} (true {r.figure_true}); readings: {vals}; estimate {est}; flag margin {margin}; "
            f"true value {truth}; why: {d.reason}")


def write_example(split: str, rid: str, why: str, rows, out: Path) -> None:
    d = out / "examples" / rid
    d.mkdir(parents=True, exist_ok=True)
    shutil.copy(DATA / split / rid / "report.pdf", d / "report.pdf")
    c = Counter(outcome(r) for r in rows)
    lines = [f"# {rid} ({split} split)", "", f"Chosen because: {why}.", "",
             f"{len(rows)} claims: {c['right']} right, {c['wrong']} wrong, {c['handed off']} handed off to the TA.", "",
             "| # | Sentence | Truth | Verdict | Outcome |", "|---|---|---|---|---|"]
    for i, r in enumerate(rows, 1):
        lines.append(f"| {i} | {r.sentence} | {r.gold} | {r.verdict} | **{outcome(r)}** |")
    lines += ["", "## Evidence for each claim", ""]
    for i, r in enumerate(rows, 1):
        lines.append(f"{i}. {outcome(r).upper()}: {evidence(r)}")
    (d / "results.md").write_text("\n".join(lines) + "\n")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default="final")
    ap.add_argument("--splits", nargs="+", default=["test", "dev"])
    ap.add_argument("--run", nargs="+", default=None, metavar="SPLIT=PREFIX", help="run-name prefix per split")
    ap.add_argument("--out", default="results")
    ap.add_argument("--examples", type=int, default=5)
    args = ap.parse_args()
    out = Path(args.out)
    log = out / "run_log.md"                      # the run log is kept by hand: never wipe it
    kept = log.read_text() if log.exists() else None
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    if kept is not None:
        log.write_text(kept)

    if args.run:
        prefix = dict(a.split("=", 1) for a in args.run)
        args.splits = list(prefix)
    else:
        prefix = {s: f"{args.tag}_{s}" for s in args.splits}
    dirs = {s: {p: RUNS / f"{prefix[s]}_{p}" for p in POLICIES} for s in args.splits}
    all_runs = {s: {p: load_rows(dirs[s][p]) for p in POLICIES} for s in args.splits}
    main_rows = {s: all_runs[s][MAIN] for s in args.splits}

    md = ["# Results", "",
          f"Main method: **{MAIN}** (the planner picks tools from the measured profile). Runs: "
          + ", ".join(f"`{prefix[s]}_<policy>` ({s})" for s in args.splits) + ".",
          "Intervals are 95% bootstrap intervals that resample whole reports.",
          "How far each split can be trusted: `test` and `dev` are development splits (design choices were made while looking "
          "at them). `holdout` was run once with a frozen configuration and then used to diagnose a calibration problem, "
          "so it is no longer unbiased. `holdout2` and `holdout3` are fresh reports; the only things changed after seeing "
          "`holdout2` were two bug fixes (page-break sentence join, cut comparison guard), and `holdout3` was used once to "
          "choose between two calibration tables, so it is nearly but not fully unbiased (implementation.md §24.7).",
          "Accuracy overall counts a hand-off to the TA as not right; accuracy when decided counts only claims the system decided.", ""]
    for s in args.splits:
        md += method_table(s, all_runs[s], dirs[s])
        md += [f"#### {s}: what the main method said, against the truth", ""] + confusion(main_rows[s])
        md += [f"#### {s}: by claim type", ""] + breakdown(main_rows[s], lambda r: r.claim_type, "Claim type")
        md += [f"#### {s}: by chart type", ""] + breakdown(main_rows[s], lambda r: r.chart_type, "Chart type")
        md += [f"#### {s}: planted errors by size", ""] + catch_table(main_rows[s])
        md += [f"#### {s}: by report", ""] + per_report(main_rows[s])
        write_csv(out / f"all_claims_{s}.csv", main_rows[s])
    pooled = {p: [r for sp in args.splits for r in all_runs[sp][p]] for p in POLICIES}
    md += ["### All splits pooled", "",
           "| Method | Claims | Coverage | Accuracy when decided | Wrong flags | Missed errors |", "|---|---|---|---|---|---|"]
    for p in POLICIES:
        rows = pooled[p]
        md.append(f"| {p}{' (main)' if p == MAIN else ''} | {len(rows)} | {with_interval(rows, coverage)} | "
                  f"{with_interval(rows, accuracy_decided)} | {with_interval(rows, wrong_flags)} | "
                  f"{with_interval(rows, missed)} |")
    md += ["", "Report ids are unique across splits, so the interval resamples whole reports of all splits together.", ""]
    (out / "summary.md").write_text("\n".join(md) + "\n")

    chosen = pick_examples(main_rows, args.examples)
    for s, rid, why in chosen:
        write_example(s, rid, why, [r for r in main_rows[s] if r.report_id == rid], out)

    readme = ["# What is in this folder", "",
              "- `summary.md`: accuracy, coverage, wrong flags and missed errors per method and split, with intervals; "
              "a table of truth against verdict; breakdowns; accuracy of every report.",
              "- `all_claims_<split>.csv`: every claim of the split, one row each, with the truth, the verdict and the evidence.",
              "- `examples/<report>/`: a few reports with their PDF and a per-claim results file. "
              "They are chosen by fixed rules, so failures are shown as well as successes:", ""]
    readme += [f"  - `{rid}`: {why}" for s, rid, why in chosen]
    readme += ["", "Made by `python scripts/export_results.py` from the saved runs; no model is called.", ""]
    (out / "README.md").write_text("\n".join(readme))
    print(f"wrote {out}/: summary.md, {len(args.splits)} csv, {len(chosen)} example reports")


if __name__ == "__main__":
    main()
