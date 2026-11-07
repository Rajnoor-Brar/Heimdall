# Phase 8: `heimdall score`

Status: done. Blocked by: phase 7.

### Step 8.1: the command (Size: S)
- Acceptance: `heimdall score <A>/<E>[/<R>] [--set S] [--across] [--by Q] [--baseline FILTER] [--json]` prints the standings, marginals and baselines from statistics.csv, without drawing. For an Errand it prints a row per Run: each Run's score over the pages its Runs share, with the serial shown (across-axes phase 2's labels when present). `heimdall stats` is refused for a release with `heimdall plot --stats-only` (I-45).
- Files: `framework/runner/cli.py` (parser and a thin handler), `tests/runner/test_one_cli.py` or a new `tests/runner/test_score_cli.py`.
- Check: `taskset -c 0-5 nice -n 10 python -m pytest -q tests/runner/test_score_cli.py`
- Blocked by: 7.2.

## Log

2026-11-07: 8.1 done: `runner/scorecmd.py`, the `score` parser and `plot --stats-only` in cli.py, `stats` refused, tests/runner/test_score_cli.py (11), the stats-CLI test in test_plot_stage now goes through `plot --stats-only`, docs/live/scoring.md. Checked on the real studies' tables by hand.
