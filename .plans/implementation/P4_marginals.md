# Phase 4: quantity marginals

Status: in progress (4.1). Blocked by: phase 3. Source: [03 §2](../plans/grand-ranking/03_Math.md), all of it. Names in code: [Tables](Tables.md) T6, T7.

**Today:** a marginal is `over_pages` (RMS) of a slice's losses, sorted by it (`ranking.marginals`, was `score.py:473–497`); it is not gated, trimmed or matched. `_confounded` (was :456) writes the confounding sentences.

### Step 4.1: the trimmed mean and its error (Size: XS)
- Acceptance: `means.trimmed_se(values, alpha=0.2) -> Trimmed(mean, se, n, g)` (R2), 03 §2.3: g(n), the mean of the kept values, the Tukey–McLaughlin SE from the winsorised SD, `se = nan` when n − 2g < 2. NaN values are dropped before n is counted. `alpha` outside [0, 0.5) is a `HeimdallError`.
- Files: `framework/stats/means.py`, `tests/runner/test_stats_means.py`.
- Test (property 8): α = 0 gives the mean and the SE s/√n; for n = 5, α = 0.4 gives g = 2 and the median; a ten-value sample with α = 0.2 gives the mean and SE worked by hand in the test's comment; n = 0, 1, 2 give g = 0. Fails first (no such function).
- Check: `taskset -c 0-5 nice -n 10 python -m pytest -q tests/runner/test_stats_means.py`.
- Seam: the function.
- Blocked by: 3.3.

### Step 4.2: gated, matched marginals (Size: M)
- Acceptance:
  - `ranking.marginals(points: list, values: dict, settings: Settings) -> tuple[list, tuple]`: the `Marginal`s, a quantity each, and the record's Marginals stage as a tuple of `Choice`. `points` are `PointLoss`es, `values` is `{point: {quantity: value}}`. `rank` calls it when `values` is given and stores both. `Marginal` and `MarginalRow` are T7's, the fields 03 §2.4's. Rows are ordered by `effect`, rows without one last; the row with the smallest is the best. `same_as_best` is true when |`vs_best`| ≤ 2 × `vs_best_se`, false when the SE is NaN.
  - Sets, statistics, the trim and the paired test are 03 §2.1–2.3, with δ = 0.01 and `[ranking].trim` (default 0.2, checked 0 ≤ α < 0.5).
  - A quantity with no matched stratum shows levels alone and keeps today's confounding sentence. A quantity's `headline` is 04 §2's line: the best value, its ratio to the next, the strata, and the values indistinguishable from the best.
  - `[ranking].by` chooses the quantities (default: every varied one, in the sweep's order).
  - The record's Marginals stage is filled (03 §3a): α, g(n), δ, the log scale, which statistic orders the table, the strata's quantities, per row n, g, vetoed, unmatched, and that the test is paired and uncorrected for multiplicity.
  - `rankcmd` and `bars._marginals` show the new rows in their existing tables; the note "the mean of the scores" is deleted. The layout proper is phase 5's.
- Files: `framework/stats/ranking.py`, `framework/runner/config.py`, `framework/schema/run.toml` (`trim`), `framework/runner/rankcmd.py`, `framework/plot/figures/bars.py`, `tests/runner/test_stats_ranking.py`, `tests/runner/test_ranking_settings.py`.
- Test, on built designs (losses given, so no metric is involved):
  - **Balanced, 3 × 4:** `effect` = `level` − a constant, the same order.
  - **Property 6:** adding a constant to ln(δ + L) of every point of one stratum leaves every `effect` unchanged, and moves a `level`.
  - **A slice half vetoed:** the vetoed are out and counted; the stratum left with one value is `unmatched`.
  - **The confounded case of 03 §2.2:** one value's only survivor sits in the easy stratum. Its `level` is the best and its `effect` is not.
  - **Property 7:** n = 0, 1, 2, 3, 5 give the marks and g of 03 §2.4.
  - **Paired:** two values that differ by a constant ratio over 10 strata are distinguishable; with noise larger than the difference they are `same_as_best`.
  - Each fails first.
- Check: `taskset -c 0-5 nice -n 10 python -m pytest -q tests/runner/test_stats_ranking.py tests/runner/test_ranking_settings.py -k "marginal or trim"`, then the fast suite.
- Seam: `ranking.marginals` on `PointLoss`es built with given losses.
- Blocked by: 4.1.

## Log
- **4.1 · done 2026-11-10.** `means.trimmed_se(values, alpha=0.2) -> Trimmed(mean, se, n, g)`, a NamedTuple, and `means.trim_count(n, alpha)`; NaN dropped before n; `se` NaN when n − 2g < 2; α outside [0, 0.5) refused. `means.trimmed` and `REGISTRY` untouched.
  - Fails first: `AttributeError: module 'stats.means' has no attribute 'trimmed_se'`.
  - Tests: α = 0 is the mean and s/√n; n = 5, α = 0.4 is the median (g = 2, no SE); ten values at α = 0.2 by hand (6.4/6, √(2.84/9)/(0.6√10)); n ≤ 2 untrimmed, n = 3 trims one; a bad α refused.
  - Check: `test_stats_means.py`, 47 passed.
