# Phase 6 ⏸: summary and report by purpose

Status: done 2026-11-07; stopped for the developer's read of one summary. Blocked by: phase 5, and retire-yoda-backend phase 2 (so only Paint and mpl draw). Stop at the end for the developer's read of one summary.

### Step 6a: summary (Size: M)
- Acceptance: bars.py draws only. `_page_rankings`, `POINTS`, `SCORED`, `_head_to_head`, `_rates` and `_standing` go, and their prose moves to the registries' notes. The front pages hold the standings (score, worst page, veto) and the purposes' list. Then comes a section per purpose with a metric on, holding what it asks, definitions, a ranking and tables per metric. A head-to-head section appears for a page only when asked (`[score] head_to_head = "<cell>/<object>" | "all"`). Bar images show the metrics on.
- Files: `framework/plot/figures/bars.py`, `framework/plot/figures/paper.py`, `webpage.py` if headers change, `tests/runner/test_summary_layout.py`, `tests/runner/test_statstable.py`.
- Check: `taskset -c 0-5 nice -n 10 python -m pytest -q tests/runner/test_summary_layout.py tests/runner/test_statstable.py`
- Blocked by: 5.2.

### Step 6b: report (Size: M)
- Acceptance: the default "Standings" plus a section per purpose. A recipe may name `standings`, `purpose:<name>`, `<metric>:ranking|table`, `head-to-head`. Old names (`top5*`, `scoreboard*`, `head-to-head-<n>` by cell) are refused with the new name. `config.STATISTICS`/`SUMMARY` and `schema/report.toml` follow.
- Files: `framework/runner/report.py`, `framework/runner/config.py`, `framework/schema/report.toml`, `tests/runner/test_report.py`, `tests/runner/test_report_build.py`.
- Check: `taskset -c 0-5 nice -n 10 python -m pytest -q tests/runner/test_report.py tests/runner/test_report_build.py`, then alone the slow `tests/integration/test_plot_stage.py`, updated together with its fixtures.
- Live doc: `docs/live/scoring.md` (affects plots, reports); `live/stats-rms.md` is superseded by it and says so.
- Blocked by: 6a.

## Log

2026-11-07: 6a and 6b done in one pass (the report reads the same document). `bars.py` draws only: `summary_model(rows, heading, settings)` builds Standings (score, worst page, veto, a column a purpose, `dominated`), a purposes table, a section per purpose with a metric on (a ranking, then each metric's ranking, cells against curves and table), and a Head to head only for `[score].head_to_head`. `_page_rankings`, `POINTS`, `SCORED`, `_head_to_head`, `_rates`, `_standing`, the scoreboards and `top5` are gone; prose is `metrics.ASKS`/`describe`. Page images show a panel a metric on. `statistics.json` and `plot.toml` carry the `[score]` used. The report: `standings`, `purpose:<name>`, `<metric>[:ranking|crossed|table]`, `head-to-head`; `top5*`, `scoreboard*`, `head-to-head-<n>`, `area` refused with the new name; the default Standings section holds the standings and every purpose. Live doc `docs/live/scoring.md`; `stats-rms.md` says it is superseded. Checks: test_summary_layout, test_report, test_report_build, test_statstable, the slow `test_plot_stage` (48 passed, its summary test rewritten with the new layout); off-plan decisions in `.plans/Implementation_Notes.md`. Milestone: the developer's read of one summary (see 00_Plan).
