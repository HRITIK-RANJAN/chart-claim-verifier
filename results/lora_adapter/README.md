# What is in this folder

- `summary.md`: accuracy, coverage, wrong flags and missed errors per method and split, with intervals; a table of truth against verdict; breakdowns; accuracy of every report.
- `all_claims_<split>.csv`: every claim of the split, one row each, with the truth, the verdict and the evidence.
- `examples/<report>/`: a few reports with their PDF and a per-claim results file. They are chosen by fixed rules, so failures are shown as well as successes:

  - `test_002`: the report with the most claims (test)
  - `holdout_018`: a wrongly flagged claim
  - `holdout_019`: a figure that exists was reported as NO_FIGURE
  - `holdout3_019`: a sentence that fits two figures
  - `test_004`: every decided claim is right (test)

Made by `python scripts/export_results.py` from the saved runs; no model is called.
