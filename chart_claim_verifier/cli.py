"""Command line.

    chart-claim-verifier generate  -c configs/exp/smoke_cpu.yaml
    chart-claim-verifier calibrate -c configs/exp/smoke_cpu.yaml
    chart-claim-verifier run       -c configs/exp/smoke_cpu.yaml --split test --policy fixed_order
    chart-claim-verifier sweep     -c configs/exp/smoke_cpu.yaml --run runs/<name>
    chart-claim-verifier check     -c configs/exp/smoke_cpu.yaml path/to/report_dir
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from .config import load_config


def _jsonable(o):
    if isinstance(o, float) and (math.isnan(o) or math.isinf(o)):
        return None
    if isinstance(o, dict):
        return {str(k): _jsonable(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_jsonable(v) for v in o]
    return o


def _print(d: dict) -> None:
    print(json.dumps(_jsonable(d), indent=1))


def main(argv=None) -> None:
    ap = argparse.ArgumentParser("chart-claim-verifier")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("generate", "calibrate", "run", "sweep", "check", "safety", "profile", "baselines"):
        s = sub.add_parser(name)
        s.add_argument("-c", "--config", default=None)
    sub.choices["calibrate"].add_argument("--split", default=None,
                                          help='split(s) to calibrate on, e.g. "calib,calib_easy" (default: calibration.splits)')
    r = sub.choices["run"]
    r.add_argument("--split", default="test")
    r.add_argument("--policy", default=None)
    r.add_argument("--parser", default="rule", choices=["rule", "llm", "agent"])
    r.add_argument("--retrieval", default="ours", choices=["ours", "nearest", "oracle"])
    r.add_argument("--limit", type=int, default=None)
    r.add_argument("--name", default=None)
    r.add_argument("--offline", action="store_true",
                   help="replay from the reading cache only; a missing reading is counted, no model is loaded")
    sub.choices["profile"].add_argument("--rebuild", action="store_true",
                                        help="recompute from the calibration readings (no model calls if cached)")
    sub.choices["sweep"].add_argument("--run", required=True)
    sub.choices["check"].add_argument("report_dir")
    sub.choices["baselines"].add_argument("--run", required=True, help="an all_tools run (B4 reuses its readings)")
    sub.choices["baselines"].add_argument("--which", default="b1,b2,b4")
    sub.choices["safety"].add_argument("--run", required=True, help="run on the split with injections")
    sub.choices["safety"].add_argument("--clean-run", required=True, help="same split, clean twins")
    args = ap.parse_args(argv)
    cfg = load_config(args.config)

    if args.cmd == "generate":
        from .generator.build import build_all
        out = build_all(cfg, cfg["paths"]["data_dir"], cfg["paths"].get("splits_dir", "data/splits"))
        print({k: len(v) for k, v in out.items()})
        return

    from .pipeline import Context, calibrate, load_table, load_traces, run_split, save_traces
    offline = bool(getattr(args, "offline", False)) or (args.cmd == "profile" and args.rebuild)
    if getattr(args, "offline", False) and (args.parser != "rule" or args.policy == "llm"):
        ap.error("--offline cannot be combined with the LLM parser or the LLM policy: they need the model")
    ctx = Context(cfg, offline=offline)

    if args.cmd == "calibrate":
        from .evaluation.tool_profile import format_profile
        table, extras = calibrate(ctx, args.split)
        print(format_profile(extras["profile"]))

    elif args.cmd == "profile":
        from .evaluation.tool_profile import format_profile
        from .pipeline import load_profile, rebuild_profile
        print(format_profile(rebuild_profile(ctx) if args.rebuild else load_profile(ctx)))

    elif args.cmd == "run":
        from .evaluation.metrics import join, summarize
        table = load_table(ctx)
        raw, final, truths, stats = run_split(ctx, args.split, table, args.policy, args.parser, args.retrieval,
                                              args.limit)
        name = args.name or f"{args.split}_{args.policy or cfg['agent']['policy']}_{args.parser}_{args.retrieval}"
        out = Path(cfg["paths"]["runs_dir"]) / name
        save_traces(out / "traces_raw.jsonl", raw)
        save_traces(out / "traces.jsonl", final)
        (out / "truths.json").write_text(json.dumps([t["report_id"] for t in truths]))
        metrics = {"rule_only": summarize(join(raw, truths)), "rule_plus_batch_check": summarize(join(final, truths)),
                   "run": stats, "split": args.split}
        (out / "metrics.json").write_text(json.dumps(_jsonable(metrics), indent=1))
        _print(metrics)
        print(f"\nwrote {out}")

    elif args.cmd == "sweep":
        from .decide.rule import RuleConfig
        from .evaluation.sweep import b5_settings, coverage_at, curve, ours_settings
        from .generator.build import load_truth
        run = Path(args.run)
        traces = load_traces(run / "traces_raw.jsonl")
        split = json.loads((run / "truths.json").read_text())
        truths = [load_truth(Path(cfg["paths"]["data_dir"]) / rid.rsplit("_", 1)[0] / rid) for rid in split]
        rc = RuleConfig.from_cfg(cfg)
        table = load_table(ctx)
        ours = curve(traces, truths, ours_settings(table, rc))
        b5 = curve(traces, truths, b5_settings(rc))
        res = {"ours": ours, "B5_uncalibrated": b5,
               "coverage_at_10pct": {"ours": coverage_at(ours), "B5": coverage_at(b5)}}
        (run / "sweep.json").write_text(json.dumps(_jsonable(res), indent=1))
        _print(res)

    elif args.cmd == "baselines":
        from .baselines.vlm_baselines import b1_direct, b2_threshold, b3_majority, b4_tools_no_rule
        from .evaluation.metrics import join, summarize
        from .evaluation.sweep import coverage_at
        from .generator.build import load_truth
        from .schemas import Report
        run = Path(args.run)
        traces = load_traces(run / "traces_raw.jsonl")
        ids = json.loads((run / "truths.json").read_text())
        truths = [load_truth(Path(cfg["paths"]["data_dir"]) / rid.rsplit("_", 1)[0] / rid) for rid in ids]
        reports = {rid: Report.model_validate_json((ctx.work / rid.rsplit("_", 1)[0] / rid / "report.json").read_text())
                   for rid in ids}
        which = args.which.split(",")
        res = {}
        pick = ("wrong_flag_rate", "coverage", "accuracy_when_decided", "missed_errors", "detection_limit_delta50",
                "catch_rate_by_delta", "n_flagged")
        if "b1" in which or "b2" in which:
            b1 = b1_direct(traces, reports, ctx.llm)
            save_traces(run / "B1.jsonl", b1)
            res["B1_direct"] = {k: summarize(join(b1, truths))[k] for k in pick}
            if "b2" in which:
                pts = []
                for tau in (50, 60, 70, 80, 90, 95):
                    rows = join(b2_threshold(b1, tau), truths)
                    m = summarize(rows)
                    pts.append({"setting": f"B2 tau={tau}", "wrong_flag_rate": m["wrong_flag_rate"],
                                "coverage": m["coverage"], "n_flagged": m["n_flagged"]})
                res["B2_confidence"] = {"curve": pts, "coverage_at_10pct": coverage_at(pts)}
        if "b3" in which:
            b3 = b3_majority(traces, reports, ctx.llm)
            save_traces(run / "B3.jsonl", b3)
            res["B3_majority"] = {k: summarize(join(b3, truths))[k] for k in pick}
        if "b4" in which:
            b4 = b4_tools_no_rule(traces, ctx.llm)
            save_traces(run / "B4.jsonl", b4)
            res["B4_tools_no_rule"] = {k: summarize(join(b4, truths))[k] for k in pick}
        (run / "baselines.json").write_text(json.dumps(_jsonable(res), indent=1))
        _print(res)

    elif args.cmd == "safety":
        from .evaluation.safety import injection_effect
        res = injection_effect(load_traces(Path(args.run) / "traces.jsonl"),
                               load_traces(Path(args.clean_run) / "traces.jsonl"))
        m = json.loads((Path(args.run) / "metrics.json").read_text())["run"]
        res.update({"lms_blocked": m["lms_blocked"], "lms_unsafe_executed": m["lms_unsafe_executed"]})
        _print(res)

    elif args.cmd == "check":
        from .agent.controller import ClaimController
        from .agent.report_agent import ReportAgent, evidence_card, finalize
        from .claims.parser import RuleParser
        from .decide.rule import RuleConfig
        from .pipeline import ingest, make_policy
        table = load_table(ctx)
        report, _ = ingest(ctx, Path(args.report_dir))
        tools = ctx.tools()
        rc = RuleConfig.from_cfg(cfg)
        agent = ReportAgent(RuleParser(), ClaimController(tools, make_policy(ctx, cfg["agent"]["policy"], table, tools),
                                                          table, rc, cfg["decision"]["max_tool_calls"]))
        traces, _ = agent.run(report)
        for t in finalize(traces, None, rc.alpha, cfg["decision"].get("batch_check", True)):
            if t.decision.verdict == "SKIPPED":
                continue
            print(f"[{t.decision.verdict:10s}] {t.sentence}")
            if t.decision.verdict in ("MISMATCH", "NOT_SURE"):
                _print(evidence_card(t))


if __name__ == "__main__":
    main()
