# Phase 7: marginals and baselines

Status: done 2026-11-07. Blocked by: phase 5.

### Step 7.1: `[score].by` (Size: S)
- Acceptance: for each axis named (default: every varied axis with at least 2 values), a table of value × score, the `mean` over every point having that value. When the other axes' values are not balanced across this axis's values (for example pdf1 only with py8), the table says which values confound it. Merged curves (set-merge) never enter a marginal: it is a mean of members' losses, not the loss of a mean curve.
- Files: `framework/stats/score.py`, the summary and report sections, `tests/runner/test_stats_score.py`.
- Check: `taskset -c 0-5 nice -n 10 python -m pytest -q tests/runner/test_stats_score.py`
- Blocked by: 5.2.

### Step 7.2: `[score].baseline` (Size: S)
- Acceptance: `baseline = { filter }`. Each point's Δloss per page and Δscore is taken against the baseline point equal on every other axis. A point without a partner is listed as unmatched, not dropped quietly.
- Files: as 7.1.
- Check: as 7.1, plus a hand-computed fixture.
- Blocked by: 7.1.

## Log

2026-11-07: 7.1 and 7.2 done in `stats/score.py` (`marginals`, `baseline`), the summary's Marginals and Baseline sections, `statistics.json` `axes`, `statstable.point_axes`, the report's `marginals` and `baseline` names (default Standings holds them). Tests: test_stats_score (confounded fixture; hand-computed baseline Δ), test_summary_layout, test_statstable. Checked on a real table by hand.
