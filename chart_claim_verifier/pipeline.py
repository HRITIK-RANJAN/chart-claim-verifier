"""Wire the modules together from a config. The CLI (cli.py) is a thin layer over this."""
from __future__ import annotations

import json
import random
from pathlib import Path

from .agent.controller import ClaimController
from .agent.policies import (TOOL_DESCRIPTIONS, AllToolsPolicy, CalibrationInformedPolicy, FixedOrderPolicy,
                             LLMPolicy, Policy)
from .agent.report_agent import ReportAgent, finalize
from .calibration.collect import collect_figure, success_rates, tool_error_table
from .calibration.fit import fit_table
from .calibration.store import CalibrationTable
from .claims.parser import LLMParser, RuleParser
from .decide.rule import RuleConfig
from .evaluation.correlation import error_correlation
from .generator.build import load_truth, report_dirs
from .generator.tables import ChartTable
from .ingest.pdf_parser import parse_pdf
from .lms.guard import ActionGuard
from .lms.mock_lms import MockLMS
from .schemas import ClaimTrace, Report
from .tools.cache import ReadingCache
from .tools.registry import build_tools
from .tools.simulated import TruthIndex


class Context:
    """Shared, lazily-built resources for one run."""

    def __init__(self, cfg: dict, offline: bool = False):
        self.cfg, self.offline = cfg, offline       # offline: replay from the reading cache, never call a model
        p = cfg["paths"]
        self.data = Path(p["data_dir"])
        self.work = self.data.parent / "work"
        self.cache = ReadingCache(p["cache_db"])
        self.truth = TruthIndex()
        self._llm = None

    @property
    def llm(self):
        if self._llm is None:
            m = self.cfg["models"]
            if self.offline:
                from .models.vlm import OfflineLLM
                self._llm = OfflineLLM(m["vlm"] + (f"+{m['lora_adapter']}" if m.get("lora_adapter") else ""))
            else:
                from .models.vlm import VLM
                self._llm = VLM(m["vlm"], m.get("dtype", "float16"), m.get("lora_adapter"))
        return self._llm

    def needs_llm(self, tools: list[str], parser: str, policy: str) -> bool:
        return parser == "llm" or policy == "llm" or any(t in ("vlm_table", "vlm_crop") for t in tools)

    def tools(self, names: list[str] | None = None):
        names = names or self.cfg["tools"]["enabled"]
        llm = self.llm if any(n in ("vlm_table", "vlm_crop") for n in names) else None
        return build_tools(names, self.cache, llm=llm, truth=self.truth,
                           deplot_model=self.cfg["models"].get("deplot", "google/deplot"), offline=self.offline)


# ------------------------------------------------------------------ ingest
def ingest(ctx: Context, report_dir: Path) -> tuple[Report, dict]:
    """Parse a generated report (cached as JSON) and register its true tables for simulated tools."""
    truth = load_truth(report_dir)
    work = ctx.work / report_dir.parent.name / report_dir.name
    cached = work / "report.json"
    if cached.exists():
        report = Report.model_validate_json(cached.read_text())
    else:
        report = parse_pdf(report_dir / "report.pdf", work, truth["report_id"])
        cached.write_text(report.model_dump_json())
    by_num = {f["number"]: f for f in truth["figures"]}
    for fig in report.figures:
        if fig.number in by_num:
            ctx.truth.add(fig.image_path, ChartTable.from_dict(by_num[fig.number]["table"]))
    return report, truth


# ------------------------------------------------------------------ calibration
def calibration_splits(cfg: dict, split: str | None = None) -> list[str]:
    """Which splits are read for calibration: --split "a,b", else calibration.splits from the config."""
    return split.split(",") if split else list((cfg.get("calibration") or {}).get("splits", ["calib"]))


def calibrate(ctx: Context, split: str | None = None, name: str | None = None) -> tuple[CalibrationTable, dict]:
    cfg = ctx.cfg
    tools = ctx.tools()
    rng = random.Random(cfg["seed"])
    items, errors = _collect(ctx, calibration_splits(cfg, split), tools, rng)
    names = list(tools)
    order = cfg["agent"]["fixed_order"] if cfg["agent"]["policy"] in ("fixed_order",) else None
    d = cfg["decision"]
    extras = {
        "tool_error": tool_error_table(errors, names),
        "tool_success": success_rates(errors, names),
        "correlation": error_correlation(errors, names),
        "n_points": len(errors), "n_items": len(items),
    }
    table = fit_table(items, d["eps"], d["min_group_size"], order=order, seed=cfg["seed"],
                      meta={"tools": names, "tool_error": extras["tool_error"],
                            "tool_costs": {n: t.cost for n, t in tools.items()},
                            "models": cfg["models"]})
    name = name or "_".join(names)
    out = Path(cfg["paths"]["calibration_dir"])
    table.save(out / f"{name}.json")
    (out / f"{name}.report.json").write_text(json.dumps({**extras, "groups": table.summary()}, indent=1))
    from .evaluation.tool_profile import build_profile, save_profile
    (out / f"{name}.errors.json").write_text(json.dumps(errors))
    extras["profile"] = build_profile(errors, names, extras["correlation"], *_profile_settings(cfg))
    save_profile(extras["profile"], out / f"{name}.profile.json")
    return table, extras


def _collect(ctx: Context, splits: list[str], tools: dict, rng: random.Random) -> tuple[list, list]:
    import sys
    import time
    items, errors = [], []
    dirs = [d for s in splits for d in report_dirs(ctx.data, s)]
    t0 = time.time()
    for k, rd in enumerate(dirs):
        print(f"[calibrate] {k + 1}/{len(dirs)} {rd.name}  {time.time() - t0:.0f}s", file=sys.stderr, flush=True)
        report, truth = ingest(ctx, rd)
        by_num = {f["number"]: f for f in truth["figures"]}
        for fig in report.figures:
            if fig.number not in by_num:
                continue
            it, er = collect_figure(fig, ChartTable.from_dict(by_num[fig.number]["table"]), tools, rng)
            items += it
            errors += er
    return items, errors


def _profile_settings(cfg: dict) -> tuple[float, float]:
    """(big_error, agree): what counts as 'badly wrong' and as 'two readings agree'."""
    return (cfg["agent"].get("informed", {}).get("big_error", 0.05), cfg["decision"].get("max_accept_margin", 0.03))


def rebuild_profile(ctx: Context, split: str | None = None, name: str | None = None) -> dict:
    """Recompute the tool profile from the calibration readings (saved errors, else the reading cache)."""
    from .evaluation.tool_profile import build_profile, save_profile
    names = list(ctx.cfg["tools"]["enabled"])
    name = name or "_".join(names)
    out = Path(ctx.cfg["paths"]["calibration_dir"])
    saved = out / f"{name}.errors.json"
    errors = json.loads(saved.read_text()) if saved.exists() else None
    if errors is None or not all("series" in e for e in errors):        # older file: re-collect from the cache
        errors = None
    if errors is None:
        _, errors = _collect(ctx, calibration_splits(ctx.cfg, split), ctx.tools(), random.Random(ctx.cfg["seed"]))
        if ctx.offline and any("offline_miss" in e.get("_fail", {}).values() for e in errors):
            raise RuntimeError("the reading cache does not hold every calibration reading: run `chart-claim-verifier calibrate`")
        saved.write_text(json.dumps(errors))
    profile = build_profile(errors, names, error_correlation(errors, names), *_profile_settings(ctx.cfg))
    try:                                                  # repairs are measured separately (scripts/pilot_legend.py): keep them
        old = load_profile(ctx, name)
        profile["repairs"] = old.get("repairs", {})
        profile["cost"].update({k: v for k, v in old.get("cost", {}).items() if k not in profile["cost"]})
    except FileNotFoundError:
        pass
    save_profile(profile, out / f"{name}.profile.json")
    return profile


def load_profile(ctx: Context, name: str | None = None) -> dict:
    from .evaluation.tool_profile import load_profile as _load
    name = name or "_".join(ctx.cfg["tools"]["enabled"])
    return _load(Path(ctx.cfg["paths"]["calibration_dir"]) / f"{name}.profile.json")


def load_table(ctx: Context, name: str | None = None) -> CalibrationTable:
    name = name or "_".join(ctx.cfg["tools"]["enabled"])
    return CalibrationTable.load(Path(ctx.cfg["paths"]["calibration_dir"]) / f"{name}.json")


def make_repairs(ctx: Context) -> dict:
    """Repairs the controller may run when the planner asks (U7). Needs the VLM (or the cached answers)."""
    def read_legend_for(fig, tool) -> bool:
        from .tools.base import image_key
        from .tools.legend import read_legend
        names = read_legend(ctx.llm, fig, ctx.cache)
        if names and hasattr(tool, "legend_hint"):
            tool.legend_hint[image_key(fig.image_path)] = names
        return bool(names)
    return {"read_legend": read_legend_for}


# ------------------------------------------------------------------ runs
def make_policy(ctx: Context, name: str, table: CalibrationTable, tools: dict, profile: dict | None = None) -> Policy:
    order = [t for t in ctx.cfg["agent"]["fixed_order"] if t in tools] + [t for t in tools if t not in ctx.cfg["agent"]["fixed_order"]]
    if name == "all_tools":
        return AllToolsPolicy(order)
    if name == "fixed_order":
        return FixedOrderPolicy(order)
    if name == "calibration_informed":
        return CalibrationInformedPolicy(table.meta.get("tool_error", {}), {n: t.cost for n, t in tools.items()})
    if name == "informed":
        from .agent.planner import InformedPolicy
        if profile is None:
            raise ValueError("the informed policy needs a tool profile: run `chart-claim-verifier calibrate` first")
        from .agent.planner import Thresholds
        return InformedPolicy(profile, Thresholds.from_cfg(ctx.cfg))
    if name == "llm":
        ref = None
        if profile is not None:                     # log what the informed policy would choose in each state
            from .agent.planner import InformedPolicy, Thresholds
            ref = InformedPolicy(profile, Thresholds.from_cfg(ctx.cfg))
        return LLMPolicy(ctx.llm, TOOL_DESCRIPTIONS, MockLMS.CATALOG, fallback=FixedOrderPolicy(order), reference=ref)
    raise ValueError(f"unknown policy {name!r}")


def run_split(ctx: Context, split: str, table: CalibrationTable, policy: str | None = None,
              parser: str = "rule", retrieval: str = "ours", limit: int | None = None):
    cfg = ctx.cfg
    tools = ctx.tools()
    try:
        profile = load_profile(ctx)
    except FileNotFoundError:
        profile = None
    pol = make_policy(ctx, policy or cfg["agent"]["policy"], table, tools, profile)
    rc = RuleConfig.from_cfg(cfg)
    repairs = make_repairs(ctx) if (profile or {}).get("repairs") else None
    controller = ClaimController(tools, pol, table, rc, cfg["decision"]["max_tool_calls"], profile, repairs)
    # parser: "rule" (no model), "llm" (always the model), "agent" (rules, LLM only when needed)
    prs = LLMParser(ctx.llm) if parser == "llm" else RuleParser()
    llm_parser = LLMParser(ctx.llm) if parser == "agent" else None
    truths, traces, mems, plans = [], [], [], {}
    oracle_map: dict = {}
    dirs = report_dirs(ctx.data, split)[:limit]
    for rd in dirs:
        report, truth = ingest(ctx, rd)
        truths.append(truth)
        for c in truth["claims"]:
            oracle_map[(truth["report_id"], c["sentence"].strip())] = c.get("figure_id")
    agent = ReportAgent(prs, controller, retrieval, oracle=lambda rid, s: oracle_map.get((rid, s.strip())),
                        ref_bonus=cfg["retrieval"]["ref_bonus"], vocab_match=cfg["retrieval"]["vocab_match"],
                        llm_parser=llm_parser, ambiguous_rule=cfg["agent"].get("ambiguous_rule", "either"))
    for rd, truth in zip(dirs, truths):
        report, _ = ingest(ctx, rd)
        tr, mem = agent.run(report)
        traces += tr
        mems.append(mem)
        plans[report.report_id] = mem.plan
    guard = ActionGuard(MockLMS())
    final = finalize(traces, guard, rc.alpha, cfg["decision"].get("batch_check", True))
    stats = {"calls_saved_by_memory": sum(m.calls_saved for m in mems),
             "calls_by_tool": dict(sum((m.calls for m in mems), start=__import__("collections").Counter())),
             "policy_invalid_actions": getattr(pol, "invalid", 0),
             "lms_blocked": len(guard.blocked), "lms_unsafe_executed": guard.unsafe_executed,
             "lms_review_list": len(guard.lms.review_list), "plans": plans,
             "offline_misses": sum(r.error == "offline_miss" for t in traces for r in t.readings)}
    return traces, final, truths, stats


def save_traces(path: Path, traces: list[ClaimTrace]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        for t in traces:
            f.write(t.model_dump_json() + "\n")


def load_traces(path: Path) -> list[ClaimTrace]:
    return [ClaimTrace.model_validate_json(line) for line in Path(path).read_text().splitlines() if line.strip()]
