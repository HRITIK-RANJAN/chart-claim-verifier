"""Measured tool performance -- the information the agent decides with.

Built from the calibration charts (true values known). For every tool and every
situation ("line|hard", "bar|easy", ...):

  success        share of reads that returned a value (vs. refused / failed)
  median_error   typical error, fraction of the axis range
  p90_error      a bad-but-not-rare error
  big_error      share of returned values that are off by more than 5% of the
                 axis range (silent failures: the dangerous kind)
  top_failures   the most common refusal reasons

plus each tool's time per call, how correlated the tools' errors are, and for
every PAIR of tools in every situation:

  agree             both answered and their values are within AGREE of each other
  agree_wrong       ... and their average is still off by more than BIG
  wrong_when_agree  agree_wrong / agree: how far an agreement between these two
                    tools can be trusted (two tools that make the same mistake
                    agree on the wrong value)
  figures, figures_wrong
                    on how many distinct charts those agreements / wrong agreements
                    happen. Points on one chart share their mistakes, so charts, not
                    points, say how much evidence there really is.

plus, for every tool, how far each failure code reaches ("failure_scope"): does a
failure repeat for the whole figure, the whole series, or only the point it was seen on?
"""
from __future__ import annotations

import itertools
import json
from collections import Counter, defaultdict
from pathlib import Path
from statistics import median

import numpy as np

BIG = 0.05            # defaults; the pipeline passes agent.informed.big_error / decision.max_accept_margin
AGREE = 0.03          # readings this close count as agreeing
REACH = 0.9           # a failure "reaches" a figure / series when this share of its other points fail the same way
MIN_CODE_POINTS = 10  # a failure code seen on fewer points than this is treated as point-level


def pair_stats(errors: list[dict], tools: list[str], big: float = BIG, agree_within: float = AGREE) -> dict:
    """situation -> "a~b" -> counts of agreement and of wrong agreement (errors are fractions of the axis range)."""
    out = defaultdict(dict)
    for key in sorted({e.get("_situation", "*") for e in errors} | {"*"}):
        es = [e for e in errors if key == "*" or e.get("_situation") == key]
        for a, b in itertools.combinations(tools, 2):
            both = [e for e in es if a in e and b in e]
            agree = [e for e in both if abs(e[a] - e[b]) <= agree_within]
            bad = [e for e in agree if abs((e[a] + e[b]) / 2) > big]
            out[key][f"{a}~{b}"] = {"both": len(both), "agree": len(agree), "agree_wrong": len(bad),
                                    "wrong_when_agree": len(bad) / len(agree) if agree else None,
                                    "figures": len({e.get("figure") for e in agree}),
                                    "figures_wrong": len({e.get("figure") for e in bad})}
    return dict(out)


def failure_scope(errors: list[dict], tools: list[str], min_points: int = MIN_CODE_POINTS) -> dict:
    """tool -> failure code -> "figure" | "series" | "point": how far one failure reaches.

    For the points that failed with a code, look at the OTHER points of the same figure
    (then of the same series): if REACH of them fail the same way, the failure belongs to
    the figure (series). A code seen on fewer than `min_points` points is "point": on thin
    evidence keep trying, a wasted retry is cheap.
    """
    out: dict[str, dict[str, str]] = {t: {} for t in tools}
    for t in tools:
        codes = Counter(e["_fail"][t] for e in errors if t not in e and t in e.get("_fail", {}))
        for code, n in codes.items():
            if n < min_points:
                out[t][code] = "point"
                continue
            reach = {}
            for level, keyf in (("figure", lambda e: e["figure"]), ("series", lambda e: (e["figure"], e.get("series")))):
                groups = defaultdict(list)
                for e in errors:
                    groups[keyf(e)].append(e.get("_fail", {}).get(t) == code and t not in e)
                num = sum(k * (k - 1) for g in groups.values() if (k := sum(g)) and len(g) > 1)
                den = sum(k * (len(g) - 1) for g in groups.values() if (k := sum(g)) and len(g) > 1)
                reach[level] = num / den if den else 0.0
            out[t][code] = ("figure" if reach["figure"] >= REACH else
                            "series" if reach["series"] >= REACH and any("series" in e for e in errors) else "point")
    return out


def build_profile(errors: list[dict], tools: list[str], correlation: dict | None = None,
                  big: float = BIG, agree_within: float = AGREE) -> dict:
    by = defaultdict(lambda: defaultdict(lambda: {"vals": [], "fails": Counter(), "n": 0, "figs": set(),
                                                  "tick": Counter(), "tick_ok": Counter()}))
    lat = defaultdict(list)
    per_fig = defaultdict(lambda: defaultdict(float))
    for e in errors:
        for key in (e.get("_situation", "*"), "*"):
            for t in tools:
                d = by[key][t]
                d["n"] += 1
                d["figs"].add(e["figure"])
                on = e.get("_on_tick")
                if on is not None:
                    d["tick"][on] += 1
                    d["tick_ok"][on] += t in e
                if t in e:
                    d["vals"].append(abs(e[t]))
                else:
                    d["fails"][e.get("_fail", {}).get(t, "failed")] += 1
        for t, s in e.get("_latency", {}).items():
            lat[t].append(s)
            per_fig[t][e["figure"]] += s

    situations = {}
    for key, tools_d in by.items():
        situations[key] = {}
        for t, d in tools_d.items():
            v = np.array(d["vals"])
            situations[key][t] = {
                "n": d["n"],
                "n_figures": len(d["figs"]),
                "success": len(v) / d["n"] if d["n"] else 0.0,
                "median_error": float(np.median(v)) if len(v) else None,
                "p90_error": float(np.percentile(v, 90)) if len(v) else None,
                "big_error": float((v > big).mean()) if len(v) else None,
                "top_failures": dict(d["fails"].most_common(3)),
                # success when the x value has its own tick label, and when it does not
                "success_on_tick": d["tick_ok"][True] / d["tick"][True] if d["tick"][True] >= 10 else None,
                "success_off_tick": d["tick_ok"][False] / d["tick"][False] if d["tick"][False] >= 10 else None,
            }
    cost = {t: {"seconds_per_read": float(median(lat[t])) if lat[t] else None,
                "seconds_per_figure": float(median(per_fig[t].values())) if per_fig[t] else None}
            for t in tools}
    pairs = {}
    for k, p in ((correlation or {}).get("pairs") or {}).items():
        pairs[k] = p.get("corr")
    return {"situations": situations, "cost": cost, "error_correlation": pairs,
            "pairs": pair_stats(errors, tools, big, agree_within), "failure_scope": failure_scope(errors, tools),
            "settings": {"big_error": big, "agree": agree_within}}


def save_profile(profile: dict, path: str | Path) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(profile, indent=1))


def load_profile(path: str | Path) -> dict:
    return json.loads(Path(path).read_text())


def format_profile(profile: dict) -> str:
    """Plain-text table for humans (and the report)."""
    lines = []
    for key in sorted(profile["situations"], key=lambda k: (k == "*", k)):
        lines.append(f"\nsituation {key}")
        lines.append(f"  {'tool':16s} {'points':>6s} {'charts':>6s} {'success':>8s} {'on/off tick':>12s} {'median':>8s} {'p90':>7s} {'big err':>8s}  top failures")
        for t, d in profile["situations"][key].items():
            f = lambda x: "-" if x is None else f"{100 * x:.2f}%"
            big = "-" if d["big_error"] is None else f"{d['big_error']:.1%}"
            tick = "/".join("-" if d.get(k) is None else f"{d[k]:.0%}" for k in ("success_on_tick", "success_off_tick"))
            lines.append(f"  {t:16s} {d['n']:6d} {d.get('n_figures', 0):6d} {d['success']:8.0%} {tick:>12s} {f(d['median_error']):>8s} {f(d['p90_error']):>7s} "
                         f"{big:>8s}  {d['top_failures']}")
    lines.append("\ncost (seconds):")
    for t, c in profile["cost"].items():
        lines.append(f"  {t:16s} per read {c['seconds_per_read'] or 0:.2f}   per figure {c['seconds_per_figure'] or 0:.1f}")
    lines.append("\nhow far a failure reaches (figure = repeats on every point of the figure, series = of the series):")
    for t, codes in (profile.get("failure_scope") or {}).items():
        lines.append(f"  {t:16s} " + ", ".join(f"{c}: {sc}" for c, sc in sorted(codes.items())))
    if profile.get("error_correlation"):
        lines.append("\nerror correlation between tools:")
        for k, v in profile["error_correlation"].items():
            lines.append(f"  {k:32s} {v:+.2f}" if v is not None else f"  {k:32s} -")
    if profile.get("pairs"):
        st = profile.get("settings") or {}
        lines.append(f"\nwhen two tools agree (within {st.get('agree', AGREE):.0%} of the axis), "
                     f"how often are both wrong (> {st.get('big_error', BIG):.0%})?")
        for key in sorted(profile["pairs"], key=lambda k: (k == "*", k)):
            lines.append(f"  situation {key}")
            for k, p in profile["pairs"][key].items():
                r = "-" if p["wrong_when_agree"] is None else f"{p['wrong_when_agree']:.1%}"
                lines.append(f"    {k:28s} both answered {p['both']:4d}  agree {p['agree']:4d}  "
                             f"wrong {p['agree_wrong']:3d}  ({r})  on {p.get('figures_wrong', '?')} of {p.get('figures', '?')} figures")
    return "\n".join(lines)
