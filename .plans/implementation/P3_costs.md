# Phase 3: compressed costs, the default set, figure weights

Status: in progress (3.1). Blocked by: phase 2. Sources: [03 §1.2, §1.3, §3a](../plans/grand-ranking/03_Math.md), [02 §Defaults](../plans/grand-ranking/02_Metrics.md). Names in code: [Tables](Tables.md) T1 (flags), T5, T7, T8.

Every loss changes in this phase, on purpose. A test's expected number is rewritten in the step that changes it, computed by hand in the test's own comment, never copied from the new code's output.

**Today:** `Metric.loss` is a linear hinge (`metrics.py:104`); a category's value and a page's loss are RMS (`ranking.py`, was `score.py:261–262`); five metrics are on by default and two tests assume one a category (`test_stats_registry.py:42`, `test_stats_ranking.py`, was `test_stats_score.py:80`).

### Step 3.1: orientation and compression (Size: M)
- Acceptance:
  - `Metric.oriented(value) -> float` is 03 §1.2's q: T(m) for `lower`, −T(m) for `higher`, |log₁₀ m| for `one` (m ≤ 0 → +∞), T by `scale` (`log`: log₁₀ m, and m ≤ 0 → NaN). It replaces `Metric.scored`. `Metric.excess(value, thresholds=None) -> float` is z, the thresholds oriented the same way. `Metric.cost(value, thresholds=None) -> float` is log₂(1 + z). NaN stays NaN; a non-finite q is +∞. `Metric.loss` goes. A `descriptor` metric raises `HeimdallError` in all three.
  - `[ranking].cost` other than `thresholds` is R19: `_cost_column`'s four branches stay as they are, `m.scored` → `m.oriented`, `m.better in ("higher", "none")` → `m.polarity in ("higher", "descriptor")`. Their numbers do not change in this step, and a test holds one of each to its value before the step.
  - The method record's Metrics, Cost, Category, Page loss and Opt-in aggregators stages are filled (03 §3a): per scored metric its polarity, scale, thresholds with source and `why`, weight with source; per computed metric not scored, why; the compression with its fixed points; each mean named; a pool-dependent choice says it is pool-dependent, and an opt-in transform says it is not compressed (R19). The Opt-in stage has a `Choice` for each of `aggregate`, `dominated`, `weights_by`, `baseline`, `head_to_head`, whether on or at its default.
  - `metrics.describe` says "cost 0 at g, 1 at b, compressed beyond: log₂(1 + excess)".
- Files: `framework/stats/metrics.py`, `framework/stats/ranking.py`, `tests/runner/test_stats_metrics.py`, `tests/runner/test_stats_ranking.py`, and each test whose expected loss changes (`test_summary_layout.py`, `test_rank_cli.py`, `test_report.py`).
- Test (03 §3):
  - **5:** c = 0 at good, 1 at bad, 2 at z = 3; c(z₂) − c(z₁) < z₂ − z₁ for 1 < z₁ < z₂.
  - **2:** raising one metric's value past good never lowers the point's loss, over random tables.
  - **1:** adding a point to a table changes no other point's loss (under `cost = "thresholds"`).
  - **4:** n metrics of one category weigh as one category (today's test, kept).
  - `higher` on a log scale with thresholds (1000, 100): a value of 316.2 has z = 0.5.
  - Each new assertion fails first on the linear hinge.
- Check: `taskset -c 0-5 nice -n 10 python -m pytest -q tests/runner/test_stats_metrics.py tests/runner/test_stats_ranking.py`, then the fast suite.
- Seam: `Metric.cost`, then `ranking.rank`.
- Blocked by: 2.2.

### Step 3.2: the curated defaults (Size: M)
- Acceptance:
  - `default` is on for 02's nine: `chi2_sigma`, `poisson_dev`, `log_yield_ratio`, `log_dev_shrunk`, `log_dev_l4`, `tilt`, `pull_autocorr`, `peak_pull2`, `log_ratio_roughness`, and off for `chi2_ndf`, which stays a fixed column of every table. `shown` for `n_eff`, which keeps its thresholds (1000, 100): it is scored only when `[ranking].metrics` names it.
  - `PointLoss.values` (T7) is filled: per default and shown metric, the median over the point's pages of its value, NaN-skipping.
  - `test_every_purpose_has_a_metric_and_the_defaults_cover_all_but_two` (`test_stats_registry.py`, about :42) is rewritten: the defaults are exactly these nine, the gates exactly two, the shown exactly `n_eff`, and every category but `similarity`, `integrity` and `quality` has a default. The test that takes `[0]` of a category's defaults (`test_stats_ranking.py`, was `test_stats_score.py:80`) is rewritten for a list.
  - `[stats].metrics`'s and `[ranking].metrics`'s docs in the schema say "the registry's defaults" and list none by hand.
- Files: `framework/stats/metrics.py`, `framework/schema/run.toml`, `tests/runner/test_stats_registry.py`, `tests/runner/test_stats_ranking.py`, `tests/runner/test_summary_layout.py`, `tests/runner/test_statstable.py`, the fixtures those read, with them.
- Test: the registry test above; a default table has 9 + 2 + 1 metric columns beyond the fixed ones; the summary model's category tables hold two metrics where 02 pairs them. Fails first.
- Check: `taskset -c 0-5 nice -n 10 python -m pytest -q tests/runner/test_stats_registry.py tests/runner/test_stats_ranking.py tests/runner/test_summary_layout.py tests/runner/test_statstable.py`, then the fast suite, then `tests/integration/test_plot_stage.py` alone.
- Seam: the registry and the summary model.
- Blocked by: 3.1.

### Step 3.3: a figure's weight reaches the loss (Size: S)
- Acceptance:
  - **The weight reaches the page.** `plot.Figure` gains `weight: float | None = None`, read in `figures()` as `table.get("weight")`, and `plot.Page` gains `weight: float | None = None`. `Figure(...)` in `figures()` and `Page(...)` in `written()` are built by keyword (R22). `written()` gains a keyword `weight=None` and passes it to the `Page`; its two callers (`plot.py:1032`, :1076) pass `figure.weight if figure else None`, the figure being the one whose table they already pass as `override` (:1005, :1044).
  - **The set is ranked once.** `statstable.write_set` builds `page_weights` as T8 gives it, builds the rows once, calls `ranking.rank` once, and writes the sidecar with `page_weights`, `ranking`, `ranking_sources`, `values` and `method` (R7). `ranking_sources` is `{key: "set <name>"}` for a key the set's `ranking = {…}` gave and `{key: "[ranking]"}` for a key of the errand's table; `write_set` takes the two tables apart for this (a new keyword `over: dict | None = None, set_name: str = ""`, its callers found by `grep -n "write_set(" framework`). The summary it draws is given that same `Ranking`: it does not rank again.
  - `rankcmd` and `report` read `page_weights` and `ranking_sources` from the sidecar and pass them to `rank`.
  - The record's Pages stage is filled: each page's ω with its source (`figure <name>`, the glob that matched, or 1), `over_pages`, the pages left out and why.
- Files: `framework/runner/statstable.py`, `framework/runner/plot.py`, `framework/plot/figures/bars.py` (`summary_model`, `summary_of`, `draw` take `ranking=`, T8), `framework/stats/table.py`, `framework/stats/ranking.py`, `framework/runner/rankcmd.py`, `framework/runner/report.py`, `tests/runner/test_statstable.py`, `tests/runner/test_stats_ranking.py`, `tests/runner/test_rank_cli.py`.
- Test: two pages, one from a figure with `weight = 3`: the point loss is the ω-weighted RMS by hand; the sidecar's `method` equals `rank --json`'s `method` for the same folder; the Pages stage names the figure as the source. A glob in `[ranking].weights` over the same page loses to the figure's weight, and the record says which won. Fails first (the weight has no effect today).
- Check: `taskset -c 0-5 nice -n 10 python -m pytest -q tests/runner/test_statstable.py tests/runner/test_stats_ranking.py tests/runner/test_rank_cli.py`, then the fast suite.
- Seam: `statstable.write_set` and the sidecar.
- Blocked by: 3.2.

## Log
- **3.1 · done 2026-11-10.** `Metric.oriented`, `excess`, `cost` (log₂(1 + z)); `scored` and `loss` are gone, and a descriptor refuses all three. `_cost_column`'s hinge calls `cost`, its pool branches `oriented`, and their numbers are those of before (a test holds one point of each). `bars._fraction` shades by `cost`. The record's Metrics, Cost, Category, Page loss and Opt-in stages are filled; an opt-in cost says it is pool-dependent (but surprisal) and not compressed. `describe` names the compression.
  - Fails first: `AttributeError: 'Metric' object has no attribute 'excess'`; the record's stages empty; the hand numbers of the linear hinge.
  - Hand numbers rewritten in their tests' comments: the RMS test (log₂ 1.5), the worst page (log₂ 5), the three points on two pages, `veto_loss` as G3 (2.32), `sweep_rows` (χ²/ndf = 1 + 2(2^c − 1) so a page costs c), `hole_fraction` (log₂ 1.25).
  - Check: the two step files, 108 passed. Fast suite: 2358 passed, 11 skipped, the two named reds, and `test_stats_registry.py`'s 26 cases of `describe`'s exact ending, which now names the compression; rewritten, that file with `test_report_build.py` and `test_summary_layout.py`, 154 passed.
  - A reader may rely on: a metric's cost 0 within good, 1 at bad, log₂(1 + z) beyond; the opt-in costs unchanged; the method record's stages but Pages and Marginals.
- **3.2 · done 2026-11-10.** `default` on 02's nine (`chi2_sigma`, `poisson_dev`, `log_yield_ratio`, `log_dev_shrunk`, `log_dev_l4`, `tilt`, `pull_autocorr`, `peak_pull2`, `log_ratio_roughness`), off for `chi2_ndf` (a fixed column still); `n_eff` `shown`, its thresholds kept. `PointLoss.values`: the median over a point's pages of each default and shown metric, NaN skipped. The schema's `[stats].metrics` and `[ranking].metrics` docs say "the registry's defaults" and list none.
  - Fails first: the registry's defaults are the old five; 6 columns where 12; `'PointLoss' object has no attribute 'values'`; the summary's category sections hold one metric.
  - Tests: the registry test (nine, two gates, `n_eff` shown, the categories without a default); a default table's 9 + 2 + 1 columns; the summary's categories with 02's pairs; `values`; the weight test over the accuracy pair (√0.75 by hand).
  - Check: the four step files, 223 passed. Fast suite: 2376 passed, 11 skipped, the two named reds, and nine tests of three fixtures that ranked χ²/ndf rows with the defaults (`test_rank_cli.py` 4, `test_report_build.py` 4, `test_stats_metrics.py` 1); fixed as Implementation_Notes says, those three files 64 passed. `tests/integration/test_plot_stage.py` alone: 53 passed.
  - A reader may rely on: the nine defaults, `n_eff` shown, `chi2_ndf` a column and not a default; a point's `values`.
