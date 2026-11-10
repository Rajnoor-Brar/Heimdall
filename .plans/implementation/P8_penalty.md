# Phase 8: the veto optional, badness penalised

Status: done (8.1). Blocked by: phase 6. Runs before phase 7, whose acceptance it changes. Source: the second gate (00_Plan), answers 1 and 2.

**Today:** `[ranking].gates` defaults to true (`framework/schema/run.toml:1152`, `ranking.settings_of`'s `merged.get("gates", True)`, `Settings.gates = True`). A page that fails `peak_bin_ratio` ≥ 3 or `yield_sign` ≥ 1 vetoes its point, which ranks after every passing point. Neither metric is scored (`metrics.py:697–700`: `default` unset; `yield_sign` has no thresholds), so a point's loss says nothing of the failure.

### Step 8.1: gates opt-in; the integrity metrics scored by default (Size: S)
- Acceptance:
  - `[ranking].gates` defaults to false: no gate is applied unless a study sets `gates = true` or names gate metrics. `veto_loss` is unchanged (opt-in already).
  - `peak_bin_ratio` and `yield_sign` are default scored metrics of the Integrity category. `yield_sign` gains thresholds (0, 1): a page with a non-positive yield costs 1 ("bad"). Both go through the same hinge and log₂(1 + z) as every metric, so a bin 10^10.7 × its reference costs about 2.5, and the point's loss grows with how bad it is.
  - With `gates = true`, a gate metric both vetoes and is scored, and the record says both.
  - The record's Gates stage says, by default, "no gate is applied (default): a bad page is penalised through its cost", with its source.
  - The Integrity category's question says what it scores, not that its points are vetoed.
  - Tests: by default, a fixture point with a bin 10⁴ × its reference is not vetoed, has a rank, and ranks after every ordinary point by its loss; its loss grows with the ratio (10⁴ < 10⁸). With `gates = true`, it is vetoed as before. Existing tests that relied on the default veto set `gates = true`.
  - The live doc says it: Now holds, No longer holds ("a gate on by default"), a decision V286 replacing V276's default.
- Files: `framework/stats/metrics.py`, `framework/stats/ranking.py`, `framework/schema/run.toml`, `framework/runner/config.py` if it names the default; tests under `tests/runner/`; `docs/live/grand-ranking.md`; generated reference.
- Check: `taskset -c 0-5 nice -n 10 python -m pytest -q tests/runner -m 'not slow'`, then `tests/integration/test_plot_stage.py` and `tests/integration/test_report_draw.py`, each alone.
- Blocked by: 6.2.

## Log
- **8.1 · done 2026-11-11.**
  - `Settings.gates`, `settings_of` and the schema default to false. The Gates stage then says "gates: off (default). no gate is applied: a bad page is penalised through its cost".
  - `peak_bin_ratio` and `yield_sign` are `default`. `yield_sign` has thresholds (0, 1), so a page with a non-positive yield costs log₂ 2 = 1.
  - The Integrity question and the engine's module note say the metrics are scored and the gates opt-in.
  - The live doc: Now holds ("The order", "The metrics"), No longer holds, V276 reworded, and V286. It is 11 998 bytes of the cap.
  - Fails first: `test_by_default_a_broken_curve_is_ranked_by_its_cost_not_vetoed_and_costs_more_the_worse_it_is` and `test_gates_are_opt_in_and_the_record_says_where_that_came_from`, on the old code.
  - Tests that check the veto now set `gates = true`: the engine's six, `rank`'s, and the summary's vetoed row. The registry's tests hold the eleven defaults. The summary's values tests compare against the default metrics the fixture has a column for (`HAVE`). The report's method section reads "gates: off (default)".
  - Check: `tests/runner -m 'not slow'` 2315 passed, 11 skipped, the two named reds; `test_plot_stage.py` alone 53 passed; `test_report_draw.py` alone 2 passed.
  - A reader may rely on: no veto by default; a broken curve's loss grows with how broken it is; `gates = true` brings the veto back.

