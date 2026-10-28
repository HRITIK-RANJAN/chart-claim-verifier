# Results

Main method: **informed** (the planner picks tools from the measured profile). Runs: `v3_test_<policy>` (test), `v3_dev_<policy>` (dev), `v3_holdout_<policy>` (holdout), `v3_holdout2_<policy>` (holdout2), `u17old_holdout3_<policy>` (holdout3).
Intervals are 95% bootstrap intervals that resample whole reports.
How far each split can be trusted: `test` and `dev` are development splits (design choices were made while looking at them). `holdout` was run once with a frozen configuration and then used to diagnose a calibration problem, so it is no longer unbiased. `holdout2` and `holdout3` are fresh reports; the only things changed after seeing `holdout2` were two bug fixes (page-break sentence join, cut comparison guard), and `holdout3` was used once to choose between two calibration tables, so it is nearly but not fully unbiased (implementation.md §24.7).
Accuracy overall counts a hand-off to the TA as not right; accuracy when decided counts only claims the system decided.

### test

| Method | Claims | Coverage | Accuracy when decided | Accuracy overall | Wrong flags | Missed errors | Model time |
|---|---|---|---|---|---|---|---|
| all_tools | 201 | 69.7% [59.2%, 79.1%] | 97.9% [95.4%, 100.0%] | 68.2% [58.2%, 77.4%] | 2.6% [0.0%, 6.2%] | 1.0% [0.0%, 3.2%] | 44.0 min |
| fixed_order | 201 | 73.1% [62.0%, 83.2%] | 98.6% [96.3%, 100.0%] | 72.1% [61.3%, 82.0%] | 1.3% [0.0%, 4.2%] | 1.0% [0.0%, 3.2%] | 26.8 min |
| informed (main) | 201 | 74.1% [63.5%, 84.1%] | 99.3% [97.7%, 100.0%] | 73.6% [62.9%, 83.1%] | 1.2% [0.0%, 4.2%] | 0.0% [0.0%, 0.0%] | 16.6 min |

#### test: what the main method said, against the truth

| Truth \ Verdict | CONSISTENT | MISMATCH | NOT_SURE | NO_FIGURE |
|---|---|---|---|---|
| claim is right | 58 | 1 | 28 | 0 |
| claim is wrong | 0 | 80 | 20 | 0 |
| no chart shows it | 0 | 0 | 4 | 10 |

#### test: by claim type

| Claim type | Claims | Decided | Right of decided | Handed off |
|---|---|---|---|---|
| difference | 44 | 32 | 31/32 | 12 |
| point | 141 | 107 | 107/107 | 34 |
| relative_change | 16 | 10 | 10/10 | 6 |

#### test: by chart type

| Chart type | Claims | Decided | Right of decided | Handed off |
|---|---|---|---|---|
| bar | 56 | 52 | 52/52 | 4 |
| grouped_bar | 35 | 32 | 31/32 | 3 |
| line | 100 | 55 | 55/55 | 45 |
| unknown | 10 | 10 | 10/10 | 0 |

#### test: planted errors by size

| Planted error size | Errors | Measured (2+ readings) | Flagged of measured | Flagged of all |
|---|---|---|---|---|
| 0.02 | 10 | 8 | 7/8 | 7/10 |
| 0.05 | 14 | 13 | 12/13 | 12/14 |
| 0.1 | 18 | 15 | 13/15 | 13/18 |
| 0.2 | 22 | 19 | 19/19 | 19/22 |
| 0.5 | 18 | 17 | 17/17 | 17/18 |

#### test: by report

| Report | Claims | Right | Wrong | Handed off |
|---|---|---|---|---|
| test_000 | 10 | 6 | 0 | 4 |
| test_001 | 10 | 5 | 0 | 5 |
| test_002 | 15 | 15 | 0 | 0 |
| test_003 | 5 | 4 | 0 | 1 |
| test_004 | 15 | 14 | 0 | 1 |
| test_005 | 13 | 7 | 0 | 6 |
| test_006 | 11 | 10 | 0 | 1 |
| test_007 | 11 | 10 | 0 | 1 |
| test_008 | 7 | 5 | 0 | 2 |
| test_009 | 7 | 4 | 0 | 3 |
| test_010 | 8 | 6 | 1 | 1 |
| test_011 | 9 | 9 | 0 | 0 |
| test_012 | 13 | 10 | 0 | 3 |
| test_013 | 4 | 1 | 0 | 3 |
| test_014 | 12 | 2 | 0 | 10 |
| test_015 | 13 | 12 | 0 | 1 |
| test_016 | 8 | 5 | 0 | 3 |
| test_017 | 8 | 5 | 0 | 3 |
| test_018 | 8 | 8 | 0 | 0 |
| test_019 | 14 | 10 | 0 | 4 |

### dev

| Method | Claims | Coverage | Accuracy when decided | Accuracy overall | Wrong flags | Missed errors | Model time |
|---|---|---|---|---|---|---|---|
| all_tools | 208 | 79.3% [72.5%, 85.6%] | 97.0% [94.0%, 99.4%] | 76.9% [69.7%, 83.7%] | 2.8% [0.0%, 7.4%] | 1.1% [0.0%, 3.8%] | 45.2 min |
| fixed_order | 208 | 84.1% [77.1%, 90.1%] | 97.1% [94.3%, 99.4%] | 81.7% [74.8%, 88.4%] | 1.3% [0.0%, 4.2%] | 2.2% [0.0%, 6.0%] | 22.7 min |
| informed (main) | 208 | 80.8% [72.9%, 87.6%] | 97.6% [94.7%, 100.0%] | 78.8% [71.0%, 86.6%] | 1.4% [0.0%, 4.6%] | 1.1% [0.0%, 3.8%] | 17.1 min |

#### dev: what the main method said, against the truth

| Truth \ Verdict | CONSISTENT | MISMATCH | NOT_SURE | NO_FIGURE |
|---|---|---|---|---|
| claim is right | 81 | 1 | 21 | 1 |
| claim is wrong | 1 | 70 | 18 | 1 |
| no chart shows it | 0 | 0 | 1 | 13 |

#### dev: by claim type

| Claim type | Claims | Decided | Right of decided | Handed off |
|---|---|---|---|---|
| difference | 53 | 42 | 42/42 | 11 |
| point | 142 | 118 | 115/118 | 24 |
| relative_change | 13 | 8 | 7/8 | 5 |

#### dev: by chart type

| Chart type | Claims | Decided | Right of decided | Handed off |
|---|---|---|---|---|
| bar | 43 | 41 | 41/41 | 2 |
| grouped_bar | 42 | 38 | 38/38 | 4 |
| line | 108 | 74 | 72/74 | 34 |
| unknown | 15 | 15 | 13/15 | 0 |

#### dev: planted errors by size

| Planted error size | Errors | Measured (2+ readings) | Flagged of measured | Flagged of all |
|---|---|---|---|---|
| 0.02 | 14 | 13 | 12/13 | 12/14 |
| 0.05 | 17 | 15 | 12/15 | 12/17 |
| 0.1 | 16 | 11 | 11/11 | 11/16 |
| 0.2 | 14 | 10 | 9/10 | 9/14 |
| 0.5 | 15 | 14 | 14/14 | 14/15 |

#### dev: by report

| Report | Claims | Right | Wrong | Handed off |
|---|---|---|---|---|
| dev_000 | 10 | 9 | 0 | 1 |
| dev_001 | 6 | 6 | 0 | 0 |
| dev_002 | 7 | 7 | 0 | 0 |
| dev_003 | 12 | 7 | 0 | 5 |
| dev_004 | 7 | 6 | 0 | 1 |
| dev_005 | 12 | 5 | 0 | 7 |
| dev_006 | 9 | 6 | 1 | 2 |
| dev_007 | 9 | 9 | 0 | 0 |
| dev_008 | 14 | 10 | 1 | 3 |
| dev_009 | 14 | 12 | 0 | 2 |
| dev_010 | 10 | 7 | 0 | 3 |
| dev_011 | 9 | 9 | 0 | 0 |
| dev_012 | 13 | 9 | 0 | 4 |
| dev_013 | 8 | 7 | 0 | 1 |
| dev_014 | 11 | 11 | 0 | 0 |
| dev_015 | 10 | 9 | 0 | 1 |
| dev_016 | 9 | 7 | 0 | 2 |
| dev_017 | 16 | 9 | 2 | 5 |
| dev_018 | 12 | 12 | 0 | 0 |
| dev_019 | 10 | 7 | 0 | 3 |

### holdout

| Method | Claims | Coverage | Accuracy when decided | Accuracy overall | Wrong flags | Missed errors | Model time |
|---|---|---|---|---|---|---|---|
| all_tools | 186 | 75.3% [67.2%, 84.0%] | 92.9% [87.4%, 97.7%] | 69.9% [62.2%, 78.8%] | 6.3% [0.0%, 13.5%] | 0.0% [0.0%, 0.0%] | 39.2 min |
| fixed_order | 186 | 78.5% [70.3%, 87.0%] | 92.5% [87.4%, 97.2%] | 72.6% [64.9%, 81.3%] | 7.8% [1.8%, 14.5%] | 0.0% [0.0%, 0.0%] | 21.7 min |
| informed (main) | 186 | 78.0% [69.6%, 86.9%] | 91.7% [87.4%, 96.1%] | 71.5% [63.6%, 80.3%] | 9.4% [3.8%, 15.0%] | 0.0% [0.0%, 0.0%] | 14.8 min |

#### holdout: what the main method said, against the truth

| Truth \ Verdict | CONSISTENT | MISMATCH | NOT_SURE | NO_FIGURE |
|---|---|---|---|---|
| claim is right | 57 | 6 | 23 | 2 |
| claim is wrong | 0 | 58 | 17 | 4 |
| no chart shows it | 0 | 0 | 1 | 18 |

#### holdout: by claim type

| Claim type | Claims | Decided | Right of decided | Handed off |
|---|---|---|---|---|
| difference | 53 | 45 | 41/45 | 8 |
| point | 121 | 93 | 85/93 | 28 |
| relative_change | 12 | 7 | 7/7 | 5 |

#### holdout: by chart type

| Chart type | Claims | Decided | Right of decided | Handed off |
|---|---|---|---|---|
| bar | 23 | 22 | 21/22 | 1 |
| grouped_bar | 67 | 58 | 55/58 | 9 |
| line | 72 | 41 | 39/41 | 31 |
| unknown | 24 | 24 | 18/24 | 0 |

#### holdout: planted errors by size

| Planted error size | Errors | Measured (2+ readings) | Flagged of measured | Flagged of all |
|---|---|---|---|---|
| 0.02 | 12 | 8 | 6/8 | 6/12 |
| 0.05 | 8 | 7 | 6/7 | 6/8 |
| 0.1 | 15 | 13 | 12/13 | 12/15 |
| 0.2 | 21 | 17 | 14/17 | 14/21 |
| 0.5 | 16 | 15 | 15/15 | 15/16 |

#### holdout: by report

| Report | Claims | Right | Wrong | Handed off |
|---|---|---|---|---|
| holdout_000 | 10 | 6 | 0 | 4 |
| holdout_001 | 9 | 6 | 2 | 1 |
| holdout_002 | 9 | 9 | 0 | 0 |
| holdout_003 | 7 | 7 | 0 | 0 |
| holdout_004 | 7 | 5 | 1 | 1 |
| holdout_005 | 10 | 4 | 0 | 6 |
| holdout_006 | 5 | 4 | 0 | 1 |
| holdout_007 | 9 | 6 | 0 | 3 |
| holdout_008 | 12 | 10 | 1 | 1 |
| holdout_009 | 7 | 7 | 0 | 0 |
| holdout_010 | 5 | 5 | 0 | 0 |
| holdout_011 | 15 | 8 | 1 | 6 |
| holdout_012 | 11 | 5 | 1 | 5 |
| holdout_013 | 13 | 7 | 1 | 5 |
| holdout_014 | 8 | 5 | 0 | 3 |
| holdout_015 | 8 | 8 | 0 | 0 |
| holdout_016 | 7 | 5 | 1 | 1 |
| holdout_017 | 10 | 8 | 1 | 1 |
| holdout_018 | 13 | 10 | 0 | 3 |
| holdout_019 | 11 | 8 | 3 | 0 |

### holdout2

| Method | Claims | Coverage | Accuracy when decided | Accuracy overall | Wrong flags | Missed errors | Model time |
|---|---|---|---|---|---|---|---|
| all_tools | 208 | 79.3% [71.6%, 87.4%] | 97.0% [94.2%, 99.4%] | 76.9% [69.5%, 85.4%] | 2.4% [0.0%, 5.7%] | 0.9% [0.0%, 2.9%] | 45.3 min |
| fixed_order | 208 | 83.7% [75.5%, 92.0%] | 97.7% [95.3%, 100.0%] | 81.7% [74.0%, 90.0%] | 1.2% [0.0%, 3.6%] | 0.9% [0.0%, 2.9%] | 21.8 min |
| informed (main) | 208 | 83.7% [75.2%, 92.7%] | 97.7% [95.3%, 100.0%] | 81.7% [73.7%, 90.6%] | 1.2% [0.0%, 3.5%] | 0.9% [0.0%, 2.9%] | 17.7 min |

#### holdout2: what the main method said, against the truth

| Truth \ Verdict | CONSISTENT | MISMATCH | NOT_SURE | NO_FIGURE |
|---|---|---|---|---|
| claim is right | 74 | 1 | 11 | 1 |
| claim is wrong | 1 | 83 | 21 | 1 |
| no chart shows it | 0 | 0 | 2 | 13 |

#### holdout2: by claim type

| Claim type | Claims | Decided | Right of decided | Handed off |
|---|---|---|---|---|
| difference | 56 | 47 | 44/47 | 9 |
| point | 141 | 121 | 120/121 | 20 |
| relative_change | 11 | 6 | 6/6 | 5 |

#### holdout2: by chart type

| Chart type | Claims | Decided | Right of decided | Handed off |
|---|---|---|---|---|
| bar | 44 | 43 | 43/43 | 1 |
| grouped_bar | 70 | 66 | 64/66 | 4 |
| line | 79 | 50 | 50/50 | 29 |
| unknown | 15 | 15 | 13/15 | 0 |

#### holdout2: planted errors by size

| Planted error size | Errors | Measured (2+ readings) | Flagged of measured | Flagged of all |
|---|---|---|---|---|
| 0.02 | 17 | 12 | 9/12 | 9/17 |
| 0.05 | 16 | 14 | 12/14 | 12/16 |
| 0.1 | 19 | 16 | 15/16 | 15/19 |
| 0.2 | 11 | 10 | 10/10 | 10/11 |
| 0.5 | 23 | 22 | 21/22 | 21/23 |

#### holdout2: by report

| Report | Claims | Right | Wrong | Handed off |
|---|---|---|---|---|
| holdout2_000 | 11 | 7 | 0 | 4 |
| holdout2_001 | 11 | 9 | 0 | 2 |
| holdout2_002 | 10 | 10 | 0 | 0 |
| holdout2_003 | 11 | 4 | 0 | 7 |
| holdout2_004 | 13 | 12 | 0 | 1 |
| holdout2_005 | 6 | 6 | 0 | 0 |
| holdout2_006 | 9 | 9 | 0 | 0 |
| holdout2_007 | 11 | 6 | 0 | 5 |
| holdout2_008 | 7 | 7 | 0 | 0 |
| holdout2_009 | 11 | 5 | 0 | 6 |
| holdout2_010 | 11 | 11 | 0 | 0 |
| holdout2_011 | 7 | 7 | 0 | 0 |
| holdout2_012 | 7 | 7 | 0 | 0 |
| holdout2_013 | 12 | 8 | 0 | 4 |
| holdout2_014 | 12 | 10 | 2 | 0 |
| holdout2_015 | 6 | 6 | 0 | 0 |
| holdout2_016 | 15 | 14 | 0 | 1 |
| holdout2_017 | 15 | 11 | 1 | 3 |
| holdout2_018 | 11 | 11 | 0 | 0 |
| holdout2_019 | 12 | 10 | 1 | 1 |

### holdout3

| Method | Claims | Coverage | Accuracy when decided | Accuracy overall | Wrong flags | Missed errors | Model time |
|---|---|---|---|---|---|---|---|
| all_tools | 197 | 73.6% [67.5%, 79.6%] | 93.1% [88.1%, 96.9%] | 68.5% [61.9%, 74.9%] | 8.7% [1.8%, 17.8%] | 3.3% [0.0%, 7.7%] | 44.1 min |
| fixed_order | 197 | 77.7% [72.0%, 83.9%] | 95.4% [91.5%, 98.3%] | 74.1% [67.0%, 81.0%] | 5.8% [0.0%, 13.8%] | 2.2% [0.0%, 6.0%] | 22.4 min |
| informed (main) | 197 | 76.1% [69.5%, 83.0%] | 97.3% [94.7%, 99.4%] | 74.1% [67.0%, 81.5%] | 3.0% [0.0%, 7.8%] | 1.1% [0.0%, 3.8%] | 15.5 min |

#### holdout3: what the main method said, against the truth

| Truth \ Verdict | CONSISTENT | MISMATCH | NOT_SURE | NO_FIGURE |
|---|---|---|---|---|
| claim is right | 67 | 2 | 21 | 1 |
| claim is wrong | 1 | 65 | 24 | 0 |
| no chart shows it | 0 | 0 | 2 | 14 |

#### holdout3: by claim type

| Claim type | Claims | Decided | Right of decided | Handed off |
|---|---|---|---|---|
| difference | 46 | 34 | 33/34 | 12 |
| point | 144 | 112 | 109/112 | 32 |
| relative_change | 7 | 4 | 4/4 | 3 |

#### holdout3: by chart type

| Chart type | Claims | Decided | Right of decided | Handed off |
|---|---|---|---|---|
| bar | 22 | 17 | 17/17 | 5 |
| grouped_bar | 72 | 62 | 61/62 | 10 |
| line | 88 | 56 | 54/56 | 32 |
| unknown | 15 | 15 | 14/15 | 0 |

#### holdout3: planted errors by size

| Planted error size | Errors | Measured (2+ readings) | Flagged of measured | Flagged of all |
|---|---|---|---|---|
| 0.02 | 21 | 16 | 11/16 | 11/21 |
| 0.05 | 9 | 8 | 7/8 | 7/9 |
| 0.1 | 15 | 14 | 13/14 | 13/15 |
| 0.2 | 14 | 10 | 9/10 | 9/14 |
| 0.5 | 17 | 14 | 13/14 | 13/17 |

#### holdout3: by report

| Report | Claims | Right | Wrong | Handed off |
|---|---|---|---|---|
| holdout3_000 | 10 | 4 | 1 | 5 |
| holdout3_001 | 9 | 7 | 0 | 2 |
| holdout3_002 | 11 | 8 | 0 | 3 |
| holdout3_003 | 9 | 8 | 1 | 0 |
| holdout3_004 | 11 | 7 | 0 | 4 |
| holdout3_005 | 10 | 7 | 1 | 2 |
| holdout3_006 | 5 | 3 | 0 | 2 |
| holdout3_007 | 6 | 5 | 0 | 1 |
| holdout3_008 | 5 | 3 | 0 | 2 |
| holdout3_009 | 13 | 7 | 0 | 6 |
| holdout3_010 | 10 | 9 | 0 | 1 |
| holdout3_011 | 14 | 11 | 0 | 3 |
| holdout3_012 | 10 | 10 | 0 | 0 |
| holdout3_013 | 10 | 7 | 0 | 3 |
| holdout3_014 | 6 | 6 | 0 | 0 |
| holdout3_015 | 13 | 12 | 0 | 1 |
| holdout3_016 | 9 | 9 | 0 | 0 |
| holdout3_017 | 5 | 3 | 0 | 2 |
| holdout3_018 | 16 | 11 | 0 | 5 |
| holdout3_019 | 15 | 9 | 1 | 5 |

### All splits pooled

| Method | Claims | Coverage | Accuracy when decided | Wrong flags | Missed errors |
|---|---|---|---|---|---|
| all_tools | 1000 | 75.5% [72.0%, 78.9%] | 95.6% [93.9%, 97.2%] | 4.4% [2.2%, 6.9%] | 1.3% [0.4%, 2.4%] |
| fixed_order | 1000 | 79.5% [75.8%, 83.2%] | 96.4% [94.8%, 97.7%] | 3.2% [1.4%, 5.2%] | 1.3% [0.4%, 2.5%] |
| informed (main) | 1000 | 78.6% [74.8%, 82.5%] | 96.8% [95.4%, 98.0%] | 3.0% [1.4%, 4.8%] | 0.6% [0.0%, 1.5%] |

Report ids are unique across splits, so the interval resamples whole reports of all splits together.

