# P1 · Names and polarity

Verified when: the registry carries the new ids, titles, polarity and category; an old format-2 table reads with every column mapped; settings that name an old id are refused with the new; `migrate` rewrites errand files and recipes; the fast suite is green.

### 1.1 The registry renamed (M)
- Acceptance: `Metric` gains `polarity`, `scale` and `category` (`better` and `purpose` go); every id, title and note as in 02; `ALIASES`; `wmape_yield` and `wmape_axis` gone; `CATEGORIES` and `QUESTIONS` replace `PURPOSES` and `ASKS`.
- Files: `framework/stats/metrics.py`, `framework/stats/score.py`, `framework/plot/figures/bars.py`, `framework/runner/report.py`, `tests/runner/test_stats_*.py`.
- Check: `source gjallarhorn.sh; cd tests; taskset -c 0-5 nice -n 10 python -m pytest runner/test_stats_registry.py runner/test_stats_metrics.py runner/test_stats_score.py runner/test_score_settings.py -q`
- Seam: the registry (`test_stats_registry`): every entry has a category, a polarity, a note, a test; every old id has an alias.
- Blocked by: none.

### 1.2 Tables and sidecars (S)
- Acceptance: `table.read` maps old columns through `ALIASES`; the sidecar writes `format = 3`, `category`, `polarity`, `phrase`; a format-2 sidecar reads.
- Files: `framework/stats/table.py`, `tests/runner/test_statstable.py`.
- Check: `source gjallarhorn.sh; cd tests; taskset -c 0-5 nice -n 10 python -m pytest runner/test_statstable.py -q`
- Seam: a format-2 fixture table read back with new names.
- Blocked by: 1.1.

### 1.3 Settings renamed: `[ranking]`, `heimdall rank`, categories (M)
- Acceptance: `[score]` → `[ranking]`, keys as 01's table; `heimdall score` refused naming `rank`; old metric ids and keys refused naming the new; `migrate` rewrites errand files and report recipes (`standings`, `purpose:`, `<old id>:ranking`); `legend_statistic` → `legend_metric`, figure kind `statistic` → `metric`.
- Files: `framework/schema/run.toml`, `framework/schema/report.toml`, `framework/runner/scorecmd.py`, `framework/runner/cli.py`, `framework/runner/migrate.py`, `framework/runner/statstable.py`, `framework/runner/sweep.py`, the tests that name them, fixtures together with them.
- Check: `source gjallarhorn.sh; cd tests; taskset -c 0-5 nice -n 10 python -m pytest -m "not slow" -q`
- Seam: `test_score_settings`, `test_migrate`, `test_score_cli` (a refusal test each, a migrate round-trip).
- Blocked by: 1.1.

## Log
