# Phase 2: integrity gates

Status: not started. Blocked by: phase 1. Sources: [03 §1.1, §1.4, §3a](../plans/grand-ranking/03_Math.md), [02](../plans/grand-ranking/02_Metrics.md) (the three new metrics and their thresholds). Names in code: [Tables](Tables.md) T1, T5–T8.

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
