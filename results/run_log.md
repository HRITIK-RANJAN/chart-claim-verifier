# Run log: every action, and what it gained or lost

One row per action, oldest first. "Gain/loss" is measured on the saved readings or a live run, never guessed. P3 = the informed planner (main method). Wrong flags = share of *correct* claims flagged as wrong. Details and reasons: `implementation.md` §22–§24.7. Numbers are on the split named; `dev` and `test` are development splits, `holdout*` are fresh.

## A. Findings and fixes before this log was started (from implementation.md §24.5)

| # | Action | Gain / loss | Kept? |
|---|---|---|---|
| U11a | Use a cited "Figure N" to find the figure when OCR misses the series name | 6 of 13 wrong NO_FIGURE fixed; 0 of 23 right ones changed | yes |
| U11b | Ask the VLM for legend names of near-miss figures | pilot: 5 of 7 wrong NO_FIGURE recovered, 0 of 23 invented; 28 cached calls. With U11a: retrieval errors dev 9 → 2, test 4 → 0; P3 accuracy when decided dev 92.9 → 97.0%, test 96.7 → 100% | yes |
| U10 | A tool that reads both legs of a difference as the same number gives no reading | dev wrong flags: P0 5.6 → 2.9%, P1 4.1 → 1.4%, P3 2.9 → 1.4%; test unchanged; coverage −0.5 point on dev | yes |
| U14 | Margins fitted per tool set | dev wrong flags P3 1.4 → 4.1%; margin check 98.8 → 93.2% (dev); coverage +1 point | **rejected** |
| U13 | Legend markers without OCR text | marker count right 25/32 today, at best 26/32 | **rejected** |
| U7 | Legend repair for colour_ambiguous / two_lines_at_x | a legend read gives names, not separation | **rejected** |
| U16 | LLM parse: accept an epoch written as a number | parse failures 24 → 0; per-field accuracy 66% → 87–89%; LLM calls 75 → 51 | yes |
| One vote per model | Average vlm_table and vlm_crop into one reading | coverage 70.2 → 67.2% (test), 80.5 → 75.1% (dev); removes 2 wrong flags but 9 right ones | **rejected** |
| Ambiguous rule `both` | Hand off a claim when two figures fit | about −3 coverage points on test, one missed error removed | yes |

## B. This phase (all splits, P3 informed unless stated)

| # | Date | Action | Run names | Gain / loss | Kept? |
|---|---|---|---|---|---|
| B1 | 2026-10-27 | Fresh split `holdout` (20 reports), frozen config | `holdout_*` | worst split: wrong flags 13.6%, margin check 88%, grouped bars 40% of charts | diagnostic |
| B2 | 2026-10-27 | Chart-count rule: a calibration group needs at least 20 charts (`min_group_charts`) | `mc_*`, `holdout2` | almost no difference on `holdout2` (coverage 83.3% vs 83.8%) | yes (harmless) |
| B3 | 2026-10-27 | Fresh split `holdout2` (20 reports) | `holdout2_*` | coverage 83.8%, right when decided 97.7%, wrong flags 3.6%, margin check 98.8% | split |
| B4 | 2026-10-27 | Fix: join sentences cut by a page break; reject a cut comparison in the rule parser | `v3_*` | removes 3 wrong flags (2 on holdout2, 1 on holdout); holdout2 wrong flags 3.6 → 1.2%; test 1.2%, dev 1.4% | yes |
| B5 | 2026-10-27 | Fresh split `holdout3` (20 reports) | `u17old_holdout3_*` | coverage 76.1%, right when decided 97.3%, wrong flags 3.0%, margin check 99.3% | split |
| B6 | 2026-10-27 | U17: 34 more grouped-bar calibration charts (`calib_grouped`) | `u17_*`; old-table replay `u17old_holdout3_*` | wrong flags worse: test 1.2 → 2.4%, holdout 9.4 → 10.8%, holdout3 3.0 → 5.7%; dev, holdout2 unchanged; coverage unchanged or −1 | **rejected**; old table restored, rejected one in `calibration_tables/_u17_rejected` |
| B7 | 2026-10-27 | U18: legend-occlusion guard (NOT_SURE when claim and reading sit under the legend box) | saved traces only | saves 2 wrong flags on holdout, 0 on dev/holdout2; loses about 50 true catches (5 holdout, 16 dev, 27 holdout2) | **rejected**; code removed |
| B8 | 2026-10-27 | Pooled result over test, dev, holdout, holdout2, holdout3 (1,000 claims) | `v3_*` + `u17old_holdout3_*` | P3: coverage 78.6%, right when decided 96.8%, wrong flags 3.0% [1.4, 4.8], missed errors 0.6% | the reported number |

## C. Fine-tuning (E6)

| # | Date | Action | Gain / loss | Status |
|---|---|---|---|---|
| C1 | 2026-10-27 | Built `ft_pool`: 1,088 charts (504 line, 370 grouped bar, 214 bar), fresh seeds | – | done |
| C2 | 2026-10-27 | LoRA training, first try | stopped at step 7: GPU out of memory on a long chart; no checkpoint | failed |
| C3 | 2026-10-27 | LoRA training, second try: OOM skip, target cap 450 tokens, save every 20 steps | crashed at start: a memory-limit setting this PyTorch rejects | failed |
| C4 | 2026-10-27/28 | LoRA training, third try: 918 charts, 1 epoch, 114 steps, 146 min | held-out loss 0.53 → 0.27; training loss ≈ 0.21; 0 OOM skips; adapter in `checkpoints/lora_chart2table` | done |
| C5 | 2026-10-28 | Evaluation chain: re-read the calibration charts with the adapter (vlm_table only), re-calibrate, read 5 splits live, replay P1 and P3 (`lora_*` runs; table `calibration_tables/local_lora`; full tables in `results/lora_adapter/`) | see C6 and C7 | done |
| C6 | 2026-10-28 | Reading error of `vlm_table` on the 51 calibration charts (1,063 readings), base → LoRA | answers 66.2% → 74.0%; median error 1.4% → 0.8% of the axis range; 90th-percentile error 17.3% → 8.7%; badly wrong (> 5% of range) 26.0% → 17.3%; answers on charts with a tick at x 95% → 87.5%, without a tick 31% → 47%; error correlation with DePlot 0.10 → 0.04, with vlm_crop 0.31 → 0.36 | **gain** |
| C7 | 2026-10-28 | P3 informed, base → LoRA, per split (coverage / right when decided / wrong flags / missed) | test 74.1/99.3/1.2/0.0 → 74.1/100/0.0/0.0; dev 80.8/97.6/1.4/1.1 → 84.6/95.5/5.3/2.2; holdout 78.0/91.7/9.4/0.0 → 82.8/89.0/14.1/1.3; holdout2 83.7/97.7/1.2/0.9 → 86.1/97.8/1.1/0.9; holdout3 76.1/97.3/3.0/1.1 → 79.2/98.1/1.4/1.1 | mixed |
| C8 | 2026-10-28 | P3 informed pooled over 1,000 claims, base → LoRA | coverage 78.6% → 81.4% (+2.8); right when decided 96.8% → 96.1%; wrong flags 3.0% [1.4, 4.8] → 4.1% [2.2, 6.2]; missed errors 0.6% → 1.1%; intervals overlap. P1 fixed order: coverage 79.5% → 82.4%, wrong flags 3.2% → 3.6% | **not a clear win**: better reading, more coverage, but no fewer wrong flags |

## How this file is kept
Add a row after every run, including failures and rejected ideas. `scripts/export_results.py` never overwrites this file.
