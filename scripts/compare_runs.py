"""Side-by-side table of several runs (e.g. the policies of the agentic ablation, E5).

    python scripts/compare_runs.py runs/local/test_P0 runs/local/test_P1 runs/local/test_P3 \
        --profile calibration_tables/local/ocr_pixel_deplot_vlm_table_vlm_crop.profile.json
"""
import json
import sys
from pathlib import Path

KEYS = [
    ("n_claims", "{:d}"), ("n_flagged", "{:d}"), ("wrong_flag_rate", "{:.1%}"), ("coverage", "{:.1%}"),
    ("accuracy_when_decided", "{:.1%}"), ("missed_errors", "{:.1%}"), ("margin_check", "{:.1%}"),
    ("detection_limit_delta50", "{}"), ("tool_calls_per_claim", "{:.2f}"), ("early_handoffs", "{:d}"),
    ("parse_escalations_to_llm", "{:d}"), ("retrieval_top1", "{:.1%}"), ("no_figure_accuracy", "{:.1%}"),
]


def fmt(v, f):
    if v is None or (isinstance(v, float) and v != v):
        return "-"
    try:
        return f.format(v)
    except (ValueError, TypeError):
        return str(v)


def main(paths, profile=None):
    runs = [(Path(p).name, json.loads((Path(p) / "metrics.json").read_text())) for p in paths]
    for layer in ("rule_only", "rule_plus_batch_check"):
        print(f"\n== {layer}")
        print(f"{'metric':28s}" + "".join(f"{n:>16s}" for n, _ in runs))
        for k, f in KEYS:
            print(f"{k:28s}" + "".join(f"{fmt(m[layer].get(k), f):>16s}" for _, m in runs))
    print("\ncatch rate by planted error size (rule only):")
    for n, m in runs:
        print(f"  {n:16s} " + "  ".join(f"{float(d):.0%}: {r:.0%}" for d, r in m["rule_only"]["catch_rate_by_delta"].items()))
    print("\nhand-off reasons (rule only):")
    for n, m in runs:
        print(f"  {n:16s} {m['rule_only'].get('handoff_reasons')}")
    print("\nmodel time actually spent per tool (calls):")
    for n, m in runs:
        print(f"  {n:16s} {m['run'].get('calls_by_tool')}")
    if profile:
        cost = {t: (c.get("seconds_per_figure") if t in ("deplot", "vlm_table") else c.get("seconds_per_read")) or 0.0
                for t, c in profile["cost"].items()}
        print("\nestimated model time (calls x measured seconds per call):")
        for n, m in runs:
            s = sum(cost.get(t, 0.0) * k for t, k in (m["run"].get("calls_by_tool") or {}).items())
            print(f"  {n:16s} {s / 60:6.1f} min")


if __name__ == "__main__":
    args = sys.argv[1:]
    prof = None
    if "--profile" in args:                      # e.g. calibration_tables/local/<tools>.profile.json
        i = args.index("--profile")
        prof = json.loads(Path(args[i + 1]).read_text())
        del args[i:i + 2]
    main(args, prof)
