# Phase 2: integrity gates

Status: done (2.1, 2.2). Blocked by: phase 1. Sources: [03 §1.1, §1.4, §3a](../plans/grand-ranking/03_Math.md), [02](../plans/grand-ranking/02_Metrics.md) (the three new metrics and their thresholds). Names in code: [Tables](Tables.md) T1, T5–T8.

**Today:** the only veto is a loss threshold that flags and reorders nothing (`ranking.py`, was `score.py:315`). A curve does not know its page is normalised (`bins.py:15`).

### Step 2.1: the gate metrics (Size: S)
- Acceptance:
  - `Curve.normalised` and `bins.curves(…, normalised)` as R4; `table._add_metrics` passes it at its one call of `bins.curves` (`table.py:87`). The test below proves the key: a page drawn with `[plot] normalise = "area"` has a truthy `page.document["page"]["normalise"]` (`plot.py:1491`). If it does not, the value is read from where the test finds it, and that is an Implementation_Notes line.
  - `peak_bin_ratio`, `yield_sign`, `negative_share`, each as 02's row and 03 §1.1, in the categories `integrity`, `integrity`, `quality`. `Metric.gate` and `Metric.shown` as R5 and R20, the sidecar's `shown` and `gate` as T5. `yield_sign` is NaN on a normalised page. `peak_bin_ratio` is NaN when no compared bin has a positive reference.
  - `table.default_metrics()` returns scored, shown and gate metrics, so a table written from now on has the gate columns.
- Files: `framework/stats/bins.py`, `framework/stats/metrics.py`, `framework/stats/table.py`, `tests/runner/test_stats_metrics.py`, `tests/runner/test_stats_registry.py`, `tests/runner/test_statstable.py`.
- Test: built spectra. A clean curve: `peak_bin_ratio` < 1, `yield_sign` 0, `negative_share` 0. One bin at 10⁴ × its reference: `peak_bin_ratio` = 4 to 1e-12. A curve of negative yield: `yield_sign` 1 on a cross-section page, NaN on a normalised one. In `test_statstable.py`, a page built as that file builds its pages, with `normalise` on: its row's `yield_sign` is NaN. Half the yield in negative bins: `negative_share` 0.5. Fails first (no such metric).
- Check: `taskset -c 0-5 nice -n 10 python -m pytest -q tests/runner/test_stats_metrics.py tests/runner/test_stats_registry.py tests/runner/test_statstable.py`.
- Seam: `metrics.evaluate` on a built `Curve`.
- Blocked by: 1.7.

### Step 2.2: `ranking.rank`, the veto and the method record (Size: M)
- Acceptance:
  - **The entry** is `ranking.rank` (R3), its shapes T7's fields marked 2.2 or unmarked. `ranking.score` and `Scores` are gone, and every caller of T8 calls `rank` (`page_weights` stays `None` until 3.3). `settings_of` loses `over` and gains `flags` and `sources` (R8).
  - **The gates.** `[ranking].gates` is `true` (every metric with a `gate`), `false`, or a list of gate metric ids; `[ranking].veto_loss` is G3. A page fails by R20's test on each gate in use, or when its page loss is above `veto_loss`. `PointLoss` gains `vetoed`, `failed_pages`, `gate_reason` (the gate, the page count over the pages, the largest value: "a bin 10^10.7 × reference on 12 of 12 pages"), and `rank` (None for a vetoed point).
  - **The order** is R21's key, ties as R13, flat or banded as R10.
  - **A missing column** is R6.
  - **The record.** `ranking.Method` is a frozen dataclass of stages, each a tuple of `Choice(name, value, source, note)`; `Method.as_dict()` is what `--json` and the sidecar hold; `Method.lines(*stages)` gives stages as sentences (T7). This step fills the Gates and Order stages (03 §3a's rows) and leaves the others empty tuples. `Settings.sources` as R8. `rank --json` carries `"method"`.
  - The summary and `rank`'s terminal table show a vetoed point last, with its reason. Nothing else of the layout changes here.
- Files: `framework/stats/ranking.py`, `framework/plot/figures/bars.py`, `framework/runner/rankcmd.py`, `framework/runner/report.py`, `framework/runner/statstable.py`, `framework/runner/config.py` (`check_ranking`), `framework/schema/run.toml` (`gates`, `veto_loss`), `tests/runner/test_stats_ranking.py`, `tests/runner/test_rank_cli.py`, `tests/runner/test_ranking_settings.py`.
- Test:
  - **Property 3** (03 §3): over 200 random tables (a fixed seed), every vetoed point is after every passing point, whatever the losses.
  - Among the vetoed (R21): a point with 1 failed page is before one with 3, whatever their losses; of two with 2 failed pages, the smaller loss is first. A point with no scored page is after every passing point and before every vetoed one.
  - Ties: losses 1, 2, 2, 3 rank 1, 2, 2, 4.
  - `gates = false` vetoes none and the record says "gates: off (`[ranking]`)"; `gates = ["peak_bin_ratio"]` leaves a negative-yield page unvetoed.
  - A table without the gate columns: no veto, and the record's Gates stage says "not evaluated", naming the column.
  - Each fails first on the old code.
- Check: `taskset -c 0-5 nice -n 10 python -m pytest -q tests/runner/test_stats_ranking.py tests/runner/test_rank_cli.py tests/runner/test_ranking_settings.py tests/runner/test_summary_layout.py`, then the fast suite.
- Seam: `ranking.rank(rows, settings)`.
- Blocked by: 2.1.

## Log
- **2.1 · done 2026-11-10.** `bins.Curve.normalised` and `bins.curves(made, logx, normalised)`; `table._add_metrics` passes `bool(page.document["page"].get("normalise"))`. `peak_bin_ratio` (integrity, thresholds (1, 3), gate 3), `yield_sign` (integrity, gate 1, no thresholds, NaN on a normalised page), `negative_share` (quality, thresholds (0, 0.25), opt-in), each with 02's title and note. `Metric.shown` and `Metric.gate`; the sidecar's `shown` and `gate`; `describe` says "a gate only" for `yield_sign`. `table.default_metrics()` is every metric with `default`, `shown` or `gate`, so a table has the two gate columns from now on.
  - Fails first: `HeimdallError: no metric 'peak_bin_ratio'` (and `yield_sign`, `negative_share`).
  - The key R4 names is the one the measured page carries: `test_a_stats_table_measures_otherwise_than_the_pages_draw` (`[stats] normalise = "area"`) now asserts every row's `yield_sign` is NaN, and `test_statistics_are_a_table_and_a_legend_may_show_them` that a cross-section page's gates read 0 and under 3.
  - The registry test lets a gate-only metric have no thresholds, and every category now has a metric (1.4's exclusion of `integrity` ends here).
  - Check: the three step files, 169 passed. Fast suite, 2363 passed, 11 skipped, and the two named reds (a third, a section cited in a comment of `metrics.py`, was removed). `tests/integration/test_plot_stage.py` alone: 53 passed.
  - A reader may rely on: the three metrics and their columns in every new table; a gate's level in the registry and the sidecar.
- **2.2 · done 2026-11-10.** `ranking.rank(rows, settings, page_weights, values) -> Ranking` (settings, points in rank order, cells, flat, method, weights, notes, marginals, baseline; `of(cell)`); `score` and `Scores` are gone. `Settings.gates` and `Settings.sources`; `settings_of(table, flags, sources)` and `gates_of`. `PointLoss` gains `rank`, `failed_pages`, `gate_reason`. A page fails by R20 on each gate in use, or by its loss above `veto_loss`; the order is R21's key, ties R13, flat or banded R10. `Choice` and `Method` (`as_dict`, `lines`), with the Gates and Order stages filled. Callers moved: `statstable.write_set` ranks once and passes `ranking=` to `bars.draw`; `bars.summary_model(rows, heading, ranking)`, `summary_of`, `draw`; `rankcmd.ranked` and `report._ranked`; `statstable.metric_names` adds the gate metrics in use. `rank --json` has `flat`, `method`, and a row's `failed_pages`, `gate_reason`; the terminal table and the summary put a vetoed point last with its reason. `[ranking].gates` in `run.toml`, checked by `config.check_ranking`.
  - Fails first: `AttributeError: module 'stats.ranking' has no attribute 'rank'`; `KeyError: 'failed_pages'` (rank --json); `unknown key 'gates'` (config).
  - Tests: property 3 over 200 seeded tables; R21's vetoed order and the no-loss group; ties 1, 2, 2, 4; `gates = false` and its record line; `gates = ["peak_bin_ratio"]`; `veto_loss` as G3; a table without gate columns says "not evaluated"; the sources of flags and sidecar; flat and banded cells; the summary's vetoed row and note; the CLI's JSON and terminal table.
  - Check: the four step files, 154 passed. Fast suite: 2375 passed, 11 skipped, the two named reds, and two callers missed, each fixed and rerun green: `test_statstable.py`'s `metric_names` (now with the gate metrics, T8), 13 passed, and `test_plot_stage.py::test_the_summary_is_scored_by_category` (it called `ranking.score`; em and ep are now one order by R10). `test_plot_stage.py` alone, before that fix: 52 passed, that 1 failed.
  - A reader may rely on: `rank` as the one entry; a vetoed point after every passing one; `[ranking].gates`; `rank --json`'s `method`, `flat`, `failed_pages`, `gate_reason`.
