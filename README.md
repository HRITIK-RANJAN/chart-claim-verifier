# Chart Claim Verifier

Uncertainty-aware verification of number-based chart claims in student technical reports.

Chart Claim Verifier checks whether the numbers written in a report match its own charts. Each chart value is read through four different tools, and the spread of those readings is calibrated against charts with known values. A claim is flagged only when the mismatch is clearly larger than the reading error. Unclear cases go to the TA instead of becoming a wrong accusation.

## How it works

1. **Find the figure.** Match the sentence to the right chart, or return "no matching figure".
2. **Parse the claim.** Turn the sentence into a checkable form: series, point, value, allowed rounding.
3. **Measure.** Read the value with a VLM crop, a VLM chart-to-table pass, DePlot, and OCR with pixel measurement. Take the median.
4. **Calibrate.** Convert tool disagreement into an error margin using conformal calibration on charts with known values.
5. **Decide.** Flag, accept, or send to the TA. Benjamini–Hochberg controls the wrong-flag rate across a batch.

The language model parses sentences and picks the next tool; it never decides a verdict. That is a few lines of tested Python (`chart_claim_verifier/decide/rule.py`).

## How the agent decides

Measure first, then decide. `chart-claim-verifier calibrate` reads every data point of the calibration charts with every tool and writes a **tool profile**: for each kind of chart (`line|easy`, `line|hard`, `bar|easy`, `bar|hard`), each tool's measured success rate, typical error, rate of silent big errors, time per call, and for every pair of tools how often they agree on a wrong value (`chart-claim-verifier profile` prints it; `chart-claim-verifier profile --rebuild` recomputes it from the cached calibration readings).

Every number comes with the number of *charts* behind it (`chart-claim-verifier profile` shows both): points on one chart share their mistakes, so a situation measured on fewer than 5 charts falls back to the pooled numbers. The profile also records how far each failure reaches (`failure_scope`: does `y_fit_failed` repeat on every point of the figure, `series_not_found` on every point of the series, `two_lines_at_x` only on its own point?), which is what report memory uses to decide what not to retry.

The pair numbers matter more than the single-tool ones: the rule only accepts or flags when readings agree, so a wrong verdict needs two tools that make the *same* mistake. On hard line charts the VLM crop reader alone is badly wrong 40% of the time, yet when it agrees with the pixel reader both are wrong only 2.4% of the time; the two VLM tools (same model) agree on a wrong value 10% of the time.

At run time the agent looks before it acts, at every stage, and logs why (`stages` in each trace):

| Stage | Looks at | Decides |
|---|---|---|
| Plan (per report) | each figure's situation: chart type, image size, legend size, printed labels, readable axis | which tools are worth using on that figure |
| Parse | did the rule parser recognise the phrasing? do the parsed names exist in a figure? | keep the rule result, or escalate to the LLM parser |
| Figure | explicit "Figure N", text-match scores | one figure, check two, or no matching figure |
| Measure | will the tool answer for this x (labelled or not)? are its answers right? would its agreement with the tools already read be trustworthy? cost (a table tool's one-off cost is shared by the claims waiting on that figure) | plan a trustworthy *pair* first and read the member most likely to fail per second first, so a failure shows up before the expensive tool is paid for; don't call tools that would refuse; don't use a tool as a cross-check if it shares the first tool's mistakes |
| Remember | which tool failed on which figure/series, with which code, and how far that code reaches | don't retry a failure that repeats; do retry one that doesn't |
| Repair | the code of the last failure | if a repair was measured to work (`read_legend` for `ocr_pixel`'s `series_not_found`) and would complete a trustworthy pair, run it, then read again |
| Stop / hand off | gap vs. margins, calls left, any trustworthy cross-check left? | stop, measure again, or hand to the TA early (no model time spent when no pair can cross-check) |
| Decide | gap, rounding, calibrated margin | fixed rule (never the LLM) |

Policies to compare (ablation E5): `all_tools` (P0), `fixed_order` (P1), `calibration_informed` (P1b), `llm` (P2, the LLM picks with the same evidence), `informed` (P3, decides from the measured profile). Parser modes: `rule`, `llm`, `agent` (rules first, LLM only when needed).

## Outcomes

| Verdict | Meaning |
|---|---|
| Consistent | Claim matches the chart within the error margin |
| Mismatch | Gap is clearly larger than the reading error |
| Not sure | Sent to the TA for review |
| No matching figure | No chart covers the claim |

## Status

Week-0/1 skeleton of the implementation plan, plus most of the CPU-side system.

| Part | State |
|---|---|
| Data generator (charts, PDF reports, labelled claims, hidden injections, clean twins) | working |
| Ingest (PDF → figures, captions, sentences, chart type, axis span) | working |
| Tool 4: OCR + pixel reader | working; ~90–100% success on clean charts (median error ~0.1% of the axis range), weak on small JPEG charts with many lines (it refuses rather than guesses, mostly) |
| Tools 1–3: VLM crop, VLM table (Qwen3-VL-4B), DePlot | working locally on Apple silicon (MPS); also run on CUDA |
| Simulated tools 1–3 (read the truth + noise) | working; **for pipeline testing only, never report their numbers** |
| Claim finder, rule parser, tolerance rules | working |
| Measured tool profile + informed agent (P3), stage logs | working |
| LLM parser, LLM controller (P2), baselines B1–B4 | working with Qwen3-VL-4B |
| Retrieval, calibration, decision rule, BH batch check | working |
| Agent: failure-aware memory, policies P0 / P1 / P1b / P3, claim loop, report planner, repair step | working (repair gated on `scripts/pilot_legend.py`) |
| Offline replay (`run --offline`): policies re-run from the reading cache, a missing reading is counted and never calls a model | working |
| Mock LMS + action guard | working |
| Metrics, sweeps (coverage at 10% wrong flags, B5), E4 correlation, E8 safety | working |
| LoRA data + training script | data script works; training script **not yet run** |

## Quick start (CPU, simulated tools)

Needs Python ≥ 3.10 and Tesseract (`brew install tesseract` / `apt install tesseract-ocr`).

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest                                                    # 72 tests

chart-claim-verifier generate  -c configs/exp/smoke_cpu.yaml        # 12 calibration + 12 test reports
chart-claim-verifier calibrate -c configs/exp/smoke_cpu.yaml
chart-claim-verifier run       -c configs/exp/smoke_cpu.yaml --split test --policy all_tools
chart-claim-verifier sweep     -c configs/exp/smoke_cpu.yaml --run runs/smoke/test_all_tools_rule_ours
chart-claim-verifier check     -c configs/exp/smoke_cpu.yaml data/smoke/generated/test/test_000
```

Replay a policy from the reading cache (no model is loaded; `offline_misses` in `metrics.json` counts readings the cache lacked):

```bash
chart-claim-verifier run -c configs/exp/local_real.yaml --split test --policy informed --offline --name replay_P3
python scripts/compare_runs.py runs/local/test_P0 runs/local/replay_P3 --profile calibration_tables/local/<tools>.profile.json
python scripts/ambiguous_rules.py -c configs/exp/local_real.yaml runs/local/replay_P3    # the four rules for a sentence that fits two figures
python scripts/eval_parse.py -c configs/exp/phrasing.yaml --split phrasing               # the parse stage alone (rules, then the LLM)
```

If the `chart-claim-verifier` command or `import chart_claim_verifier` stops working after the project folder is moved or renamed (the virtualenv remembers the old path), run `pip install -e .` again, or use `python -m chart_claim_verifier.cli ...` from the project folder.

On a T4 (Kaggle / Colab): `pip install -e ".[gpu,dev]"` and use `configs/exp/main_gpu.yaml`. Its header lists the commands for each experiment. `E4_homogeneous.yaml` and `E6_lora.yaml` cover E4 and E6.

## Layout

```
configs/            default.yaml + one file per experiment
chart_claim_verifier/
  schemas.py        the data contract every module uses
  generator/        synthetic tables, charts, reports, claims, injections
  ingest/           PDF -> Report; chart-type detection
  retrieval/        which figure a sentence is about (BM25 + coverage check)
  claims/           finder, rule / LLM parser, tolerance rules
  tools/            OCR+pixel, VLM crop, VLM table, DePlot, simulated tools, disk cache
  measure/          median, disagreement, per-tool derived values
  calibration/      collect readings, fit conformal tables, p-values, BH
  decide/           the decision rule and the batch check
  agent/            memory, policies, the informed policy (planner.py), claim loop, report planner
  lms/              mock LMS and allow-list guard
  baselines/        B1–B4 (B5 is in evaluation/sweep.py)
  evaluation/       metrics, sweeps, tool correlation, safety
finetune/           LoRA data + training
scripts/            compare_runs, ambiguous_rules, eval_parse, pilot_legend, quick benchmarks
tests/
```


