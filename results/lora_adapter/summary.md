# Results

Main method: **informed** (the planner picks tools from the measured profile). Runs: `lora_test_<policy>` (test), `lora_dev_<policy>` (dev), `lora_holdout_<policy>` (holdout), `lora_holdout2_<policy>` (holdout2), `lora_holdout3_<policy>` (holdout3).
Intervals are 95% bootstrap intervals that resample whole reports.
How far each split can be trusted: `test` and `dev` are development splits (design choices were made while looking at them). `holdout` was run once with a frozen configuration and then used to diagnose a calibration problem, so it is no longer unbiased. `holdout2` and `holdout3` are fresh reports; the only things changed after seeing `holdout2` were two bug fixes (page-break sentence join, cut comparison guard), and `holdout3` was used once to choose between two calibration tables, so it is nearly but not fully unbiased (implementation.md §24.7).
Accuracy overall counts a hand-off to the TA as not right; accuracy when decided counts only claims the system decided.

### test

| Method | Claims | Coverage | Accuracy when decided | Accuracy overall | Wrong flags | Missed errors | Model time |
|---|---|---|---|---|---|---|---|
| all_tools | 201 | 71.1% [61.9%, 79.7%] | 100.0% [100.0%, 100.0%] | 71.1% [61.9%, 79.7%] | 0.0% [0.0%, 0.0%] | 0.0% [0.0%, 0.0%] | 44.0 min |
| fixed_order | 201 | 74.6% [65.1%, 83.2%] | 98.7% [96.6%, 100.0%] | 73.6% [63.3%, 82.9%] | 0.0% [0.0%, 0.0%] | 2.0% [0.0%, 4.6%] | 26.8 min |
| informed (main) | 201 | 74.1% [63.5%, 83.9%] | 100.0% [100.0%, 100.0%] | 74.1% [63.5%, 83.9%] | 0.0% [0.0%, 0.0%] | 0.0% [0.0%, 0.0%] | 23.3 min |

#### test: what the main method said, against the truth

| Truth \ Verdict | CONSISTENT | MISMATCH | NOT_SURE | NO_FIGURE |
|---|---|---|---|---|
| claim is right | 59 | 0 | 28 | 0 |
| claim is wrong | 0 | 80 | 20 | 0 |
| no chart shows it | 0 | 0 | 4 | 10 |

#### test: by claim type

| Claim type | Claims | Decided | Right of decided | Handed off |
|---|---|---|---|---|
| difference | 44 | 32 | 32/32 | 12 |
| point | 141 | 109 | 109/109 | 32 |
| relative_change | 16 | 8 | 8/8 | 8 |

#### test: by chart type

| Chart type | Claims | Decided | Right of decided | Handed off |
|---|---|---|---|---|
| bar | 56 | 52 | 52/52 | 4 |
| grouped_bar | 35 | 31 | 31/31 | 4 |
| line | 100 | 56 | 56/56 | 44 |
| unknown | 10 | 10 | 10/10 | 0 |

#### test: planted errors by size

| Planted error size | Errors | Measured (2+ readings) | Flagged of measured | Flagged of all |
|---|---|---|---|---|
| 0.02 | 10 | 9 | 8/9 | 8/10 |
| 0.05 | 14 | 14 | 11/14 | 11/14 |
| 0.1 | 18 | 16 | 13/16 | 13/18 |
| 0.2 | 22 | 19 | 19/19 | 19/22 |
| 0.5 | 18 | 17 | 17/17 | 17/18 |

#### test: by report

| Report | Claims | Right | Wrong | Handed off |
|---|---|---|---|---|
| test_000 | 10 | 6 | 0 | 4 |
| test_001 | 10 | 5 | 0 | 5 |
| test_002 | 15 | 15 | 0 | 0 |
| test_003 | 5 | 3 | 0 | 2 |
| test_004 | 15 | 14 | 0 | 1 |
| test_005 | 13 | 7 | 0 | 6 |
| test_006 | 11 | 10 | 0 | 1 |
| test_007 | 11 | 10 | 0 | 1 |
| test_008 | 7 | 5 | 0 | 2 |
| test_009 | 7 | 5 | 0 | 2 |
| test_010 | 8 | 6 | 0 | 2 |
| test_011 | 9 | 9 | 0 | 0 |
| test_012 | 13 | 11 | 0 | 2 |
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
| all_tools | 208 | 82.7% [76.8%, 88.0%] | 95.9% [93.2%, 98.4%] | 79.3% [73.5%, 85.0%] | 5.3% [1.3%, 10.3%] | 1.1% [0.0%, 3.3%] | 45.2 min |
| fixed_order | 208 | 86.1% [79.9%, 91.1%] | 95.0% [91.6%, 97.8%] | 81.7% [75.4%, 87.6%] | 5.3% [1.3%, 10.3%] | 3.3% [0.0%, 7.5%] | 23.2 min |
| informed (main) | 208 | 84.6% [78.1%, 90.2%] | 95.5% [92.4%, 97.9%] | 80.8% [74.0%, 86.8%] | 5.3% [1.3%, 10.1%] | 2.2% [0.0%, 5.6%] | 23.8 min |

#### dev: what the main method said, against the truth

| Truth \ Verdict | CONSISTENT | MISMATCH | NOT_SURE | NO_FIGURE |
|---|---|---|---|---|
| claim is right | 83 | 4 | 16 | 1 |
| claim is wrong | 2 | 72 | 15 | 1 |
| no chart shows it | 0 | 0 | 1 | 13 |

#### dev: by claim type

| Claim type | Claims | Decided | Right of decided | Handed off |
|---|---|---|---|---|
| difference | 53 | 46 | 42/46 | 7 |
| point | 142 | 122 | 119/122 | 20 |
| relative_change | 13 | 8 | 7/8 | 5 |

#### dev: by chart type

| Chart type | Claims | Decided | Right of decided | Handed off |
|---|---|---|---|---|
| bar | 43 | 42 | 41/42 | 1 |
| grouped_bar | 42 | 39 | 37/39 | 3 |
| line | 108 | 80 | 77/80 | 28 |
| unknown | 15 | 15 | 13/15 | 0 |

#### dev: planted errors by size

| Planted error size | Errors | Measured (2+ readings) | Flagged of measured | Flagged of all |
|---|---|---|---|---|
| 0.02 | 14 | 14 | 11/14 | 11/14 |
| 0.05 | 17 | 16 | 13/16 | 13/17 |
| 0.1 | 16 | 13 | 11/13 | 11/16 |
| 0.2 | 14 | 12 | 11/12 | 11/14 |
| 0.5 | 15 | 14 | 14/14 | 14/15 |

#### dev: by report

| Report | Claims | Right | Wrong | Handed off |
|---|---|---|---|---|
| dev_000 | 10 | 9 | 1 | 0 |
| dev_001 | 6 | 5 | 0 | 1 |
| dev_002 | 7 | 7 | 0 | 0 |
| dev_003 | 12 | 8 | 1 | 3 |
| dev_004 | 7 | 5 | 1 | 1 |
| dev_005 | 12 | 6 | 0 | 6 |
| dev_006 | 9 | 5 | 1 | 3 |
| dev_007 | 9 | 8 | 0 | 1 |
| dev_008 | 14 | 10 | 0 | 4 |
| dev_009 | 14 | 12 | 0 | 2 |
| dev_010 | 10 | 7 | 0 | 3 |
| dev_011 | 9 | 9 | 0 | 0 |
| dev_012 | 13 | 10 | 1 | 2 |
| dev_013 | 8 | 8 | 0 | 0 |
| dev_014 | 11 | 11 | 0 | 0 |
| dev_015 | 10 | 9 | 0 | 1 |
| dev_016 | 9 | 8 | 0 | 1 |
| dev_017 | 16 | 11 | 2 | 3 |
| dev_018 | 12 | 12 | 0 | 0 |
| dev_019 | 10 | 8 | 1 | 1 |

### holdout

| Method | Claims | Coverage | Accuracy when decided | Accuracy overall | Wrong flags | Missed errors | Model time |
|---|---|---|---|---|---|---|---|
| all_tools | 186 | 81.2% [73.7%, 89.3%] | 88.7% [85.2%, 93.0%] | 72.0% [65.6%, 79.5%] | 14.1% [7.8%, 19.4%] | 1.3% [0.0%, 4.0%] | 39.2 min |
| fixed_order | 186 | 82.8% [74.9%, 91.8%] | 90.3% [86.5%, 94.3%] | 74.7% [67.2%, 83.2%] | 11.6% [5.7%, 17.5%] | 1.3% [0.0%, 4.0%] | 20.8 min |
| informed (main) | 186 | 82.8% [74.9%, 91.8%] | 89.0% [85.4%, 93.2%] | 73.7% [66.7%, 81.8%] | 14.1% [7.8%, 19.4%] | 1.3% [0.0%, 4.0%] | 19.2 min |

#### holdout: what the main method said, against the truth

| Truth \ Verdict | CONSISTENT | MISMATCH | NOT_SURE | NO_FIGURE |
|---|---|---|---|---|
| claim is right | 58 | 10 | 18 | 2 |
| claim is wrong | 1 | 61 | 13 | 4 |
| no chart shows it | 0 | 0 | 1 | 18 |

#### holdout: by claim type

| Claim type | Claims | Decided | Right of decided | Handed off |
|---|---|---|---|---|
| difference | 53 | 48 | 44/48 | 5 |
| point | 121 | 97 | 86/97 | 24 |
| relative_change | 12 | 9 | 7/9 | 3 |

#### holdout: by chart type

| Chart type | Claims | Decided | Right of decided | Handed off |
|---|---|---|---|---|
| bar | 23 | 22 | 21/22 | 1 |
| grouped_bar | 67 | 59 | 55/59 | 8 |
| line | 72 | 49 | 43/49 | 23 |
| unknown | 24 | 24 | 18/24 | 0 |

#### holdout: planted errors by size

| Planted error size | Errors | Measured (2+ readings) | Flagged of measured | Flagged of all |
|---|---|---|---|---|
| 0.02 | 12 | 10 | 6/10 | 6/12 |
| 0.05 | 8 | 7 | 6/7 | 6/8 |
| 0.1 | 15 | 13 | 13/13 | 13/15 |
| 0.2 | 21 | 19 | 16/19 | 16/21 |
| 0.5 | 16 | 15 | 15/15 | 15/16 |

#### holdout: by report

| Report | Claims | Right | Wrong | Handed off |
|---|---|---|---|---|
| holdout_000 | 10 | 7 | 0 | 3 |
| holdout_001 | 9 | 7 | 2 | 0 |
| holdout_002 | 9 | 9 | 0 | 0 |
| holdout_003 | 7 | 6 | 1 | 0 |
| holdout_004 | 7 | 5 | 1 | 1 |
| holdout_005 | 10 | 5 | 0 | 5 |
| holdout_006 | 5 | 4 | 0 | 1 |
| holdout_007 | 9 | 6 | 0 | 3 |
| holdout_008 | 12 | 10 | 2 | 0 |
| holdout_009 | 7 | 7 | 0 | 0 |
| holdout_010 | 5 | 5 | 0 | 0 |
| holdout_011 | 15 | 8 | 1 | 6 |
| holdout_012 | 11 | 6 | 1 | 4 |
| holdout_013 | 13 | 7 | 1 | 5 |
| holdout_014 | 8 | 6 | 1 | 1 |
| holdout_015 | 8 | 8 | 0 | 0 |
| holdout_016 | 7 | 4 | 1 | 2 |
| holdout_017 | 10 | 8 | 1 | 1 |
| holdout_018 | 13 | 11 | 2 | 0 |
| holdout_019 | 11 | 8 | 3 | 0 |

### holdout2

| Method | Claims | Coverage | Accuracy when decided | Accuracy overall | Wrong flags | Missed errors | Model time |
|---|---|---|---|---|---|---|---|
| all_tools | 208 | 81.7% [74.5%, 89.2%] | 97.1% [94.3%, 99.4%] | 79.3% [72.0%, 87.5%] | 1.1% [0.0%, 3.2%] | 1.9% [0.0%, 4.3%] | 45.3 min |
| fixed_order | 208 | 87.0% [80.7%, 93.4%] | 97.8% [95.5%, 100.0%] | 85.1% [79.2%, 91.5%] | 1.1% [0.0%, 3.1%] | 0.9% [0.0%, 2.9%] | 20.9 min |
| informed (main) | 208 | 86.1% [79.4%, 93.0%] | 97.8% [95.5%, 100.0%] | 84.1% [77.8%, 90.8%] | 1.1% [0.0%, 3.1%] | 0.9% [0.0%, 2.9%] | 22.1 min |

#### holdout2: what the main method said, against the truth

| Truth \ Verdict | CONSISTENT | MISMATCH | NOT_SURE | NO_FIGURE |
|---|---|---|---|---|
| claim is right | 73 | 1 | 12 | 1 |
| claim is wrong | 1 | 89 | 15 | 1 |
| no chart shows it | 0 | 0 | 2 | 13 |

#### holdout2: by claim type

| Claim type | Claims | Decided | Right of decided | Handed off |
|---|---|---|---|---|
| difference | 56 | 47 | 44/47 | 9 |
| point | 141 | 124 | 123/124 | 17 |
| relative_change | 11 | 8 | 8/8 | 3 |

#### holdout2: by chart type

| Chart type | Claims | Decided | Right of decided | Handed off |
|---|---|---|---|---|
| bar | 44 | 42 | 42/42 | 2 |
| grouped_bar | 70 | 65 | 63/65 | 5 |
| line | 79 | 57 | 57/57 | 22 |
| unknown | 15 | 15 | 13/15 | 0 |

#### holdout2: planted errors by size

| Planted error size | Errors | Measured (2+ readings) | Flagged of measured | Flagged of all |
|---|---|---|---|---|
| 0.02 | 17 | 16 | 11/16 | 11/17 |
| 0.05 | 16 | 15 | 12/15 | 12/16 |
| 0.1 | 19 | 18 | 15/18 | 15/19 |
| 0.2 | 11 | 11 | 11/11 | 11/11 |
| 0.5 | 23 | 23 | 22/23 | 22/23 |

#### holdout2: by report

| Report | Claims | Right | Wrong | Handed off |
|---|---|---|---|---|
| holdout2_000 | 11 | 7 | 0 | 4 |
| holdout2_001 | 11 | 8 | 0 | 3 |
| holdout2_002 | 10 | 9 | 0 | 1 |
| holdout2_003 | 11 | 6 | 0 | 5 |
| holdout2_004 | 13 | 12 | 0 | 1 |
| holdout2_005 | 6 | 6 | 0 | 0 |
| holdout2_006 | 9 | 9 | 0 | 0 |
| holdout2_007 | 11 | 6 | 0 | 5 |
| holdout2_008 | 7 | 7 | 0 | 0 |
| holdout2_009 | 11 | 7 | 0 | 4 |
| holdout2_010 | 11 | 11 | 0 | 0 |
| holdout2_011 | 7 | 7 | 0 | 0 |
| holdout2_012 | 7 | 7 | 0 | 0 |
| holdout2_013 | 12 | 9 | 0 | 3 |
| holdout2_014 | 12 | 10 | 2 | 0 |
| holdout2_015 | 6 | 6 | 0 | 0 |
| holdout2_016 | 15 | 14 | 0 | 1 |
| holdout2_017 | 15 | 13 | 1 | 1 |
| holdout2_018 | 11 | 11 | 0 | 0 |
| holdout2_019 | 12 | 10 | 1 | 1 |

### holdout3

| Method | Claims | Coverage | Accuracy when decided | Accuracy overall | Wrong flags | Missed errors | Model time |
|---|---|---|---|---|---|---|---|
| all_tools | 197 | 75.1% [70.2%, 80.4%] | 98.0% [95.7%, 100.0%] | 73.6% [68.3%, 79.4%] | 2.7% [0.0%, 7.1%] | 0.0% [0.0%, 0.0%] | 44.1 min |
| fixed_order | 197 | 81.2% [75.7%, 87.6%] | 97.5% [94.9%, 99.4%] | 79.2% [73.1%, 85.7%] | 1.4% [0.0%, 4.8%] | 2.2% [0.0%, 6.0%] | 22.4 min |
| informed (main) | 197 | 79.2% [73.7%, 85.1%] | 98.1% [95.8%, 100.0%] | 77.7% [71.6%, 84.3%] | 1.4% [0.0%, 4.8%] | 1.1% [0.0%, 3.8%] | 21.9 min |

#### holdout3: what the main method said, against the truth

| Truth \ Verdict | CONSISTENT | MISMATCH | NOT_SURE | NO_FIGURE |
|---|---|---|---|---|
| claim is right | 68 | 1 | 21 | 1 |
| claim is wrong | 1 | 71 | 18 | 0 |
| no chart shows it | 0 | 0 | 2 | 14 |

#### holdout3: by claim type

| Claim type | Claims | Decided | Right of decided | Handed off |
|---|---|---|---|---|
| difference | 46 | 35 | 35/35 | 11 |
| point | 144 | 117 | 114/117 | 27 |
| relative_change | 7 | 4 | 4/4 | 3 |

#### holdout3: by chart type

| Chart type | Claims | Decided | Right of decided | Handed off |
|---|---|---|---|---|
| bar | 22 | 17 | 17/17 | 5 |
| grouped_bar | 72 | 62 | 62/62 | 10 |
| line | 88 | 62 | 60/62 | 26 |
| unknown | 15 | 15 | 14/15 | 0 |

#### holdout3: planted errors by size

| Planted error size | Errors | Measured (2+ readings) | Flagged of measured | Flagged of all |
|---|---|---|---|---|
| 0.02 | 21 | 17 | 12/17 | 12/21 |
| 0.05 | 9 | 8 | 7/8 | 7/9 |
| 0.1 | 15 | 15 | 14/15 | 14/15 |
| 0.2 | 14 | 13 | 11/13 | 11/14 |
| 0.5 | 17 | 15 | 14/15 | 14/17 |

#### holdout3: by report

| Report | Claims | Right | Wrong | Handed off |
|---|---|---|---|---|
| holdout3_000 | 10 | 6 | 1 | 3 |
| holdout3_001 | 9 | 7 | 0 | 2 |
| holdout3_002 | 11 | 8 | 0 | 3 |
| holdout3_003 | 9 | 8 | 0 | 1 |
| holdout3_004 | 11 | 9 | 0 | 2 |
| holdout3_005 | 10 | 8 | 1 | 1 |
| holdout3_006 | 5 | 2 | 0 | 3 |
| holdout3_007 | 6 | 5 | 0 | 1 |
| holdout3_008 | 5 | 3 | 0 | 2 |
| holdout3_009 | 13 | 8 | 0 | 5 |
| holdout3_010 | 10 | 8 | 0 | 2 |
| holdout3_011 | 14 | 11 | 0 | 3 |
| holdout3_012 | 10 | 10 | 0 | 0 |
| holdout3_013 | 10 | 8 | 0 | 2 |
| holdout3_014 | 6 | 6 | 0 | 0 |
| holdout3_015 | 13 | 13 | 0 | 0 |
| holdout3_016 | 9 | 9 | 0 | 0 |
| holdout3_017 | 5 | 4 | 0 | 1 |
| holdout3_018 | 16 | 11 | 0 | 5 |
| holdout3_019 | 15 | 9 | 1 | 5 |

### All splits pooled

| Method | Claims | Coverage | Accuracy when decided | Wrong flags | Missed errors |
|---|---|---|---|---|---|
| all_tools | 1000 | 78.4% [75.1%, 81.7%] | 95.9% [94.4%, 97.4%] | 4.4% [2.4%, 6.6%] | 0.9% [0.2%, 1.7%] |
| fixed_order | 1000 | 82.4% [79.1%, 85.7%] | 95.9% [94.4%, 97.3%] | 3.6% [1.8%, 5.5%] | 1.9% [0.9%, 3.3%] |
| informed (main) | 1000 | 81.4% [77.9%, 84.9%] | 96.1% [94.6%, 97.5%] | 4.1% [2.2%, 6.2%] | 1.1% [0.2%, 2.2%] |

Report ids are unique across splits, so the interval resamples whole reports of all splits together.

