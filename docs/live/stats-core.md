---
id: live-stats-core
summary: framework/stats computes metrics and means from Paint's measured bins
affects: plots
issue: I-120
---

**Now holds:** `framework/stats/` (imports as `stats`; numpy, the standard library and `runner.errors` only; runner modules import it inside functions only, held by `tests/runner/test_imports.py`) computes from the `measured` bins of a page's stats.json. `bins.Curve` is one curve's arrays (lo, hi, y, err, ref_y, ref_err; `drawn` is the width on the page as drawn, log10 on a log-x page); `bins.read(path, logx)` loads a page. `metrics.REGISTRY` maps a name to a `Metric` (function, purpose in `PURPOSES`, direction, `(good, bad)` thresholds, default flag, note): the five defaults `chi2_ndf` (compatibility), `norm` (|ln yield ratio|), `shape` (mean |ln ratio|, a noisy bin counted less), `tilt` (the ratio's change across the page) and `worst` (mean of the k largest squared pulls), and the four old columns `rel_abs_area`, `area_ratio`, `ratio_mean`, `ratio_dev`. The log ratio is floored at ε = 1 % of the reference, so a hole costs a finite amount and an exact curve costs nothing. `means.REGISTRY` has `linear` and `rms` (the power mean, p = 1 and 2, scaled against overflow, with weights and an error rule each). The old five columns equal `statstable.statistics_of` on every curve of the plot-stage fixture (`tests/integration/test_paint_bins.py`) and on a hand-made page (`tests/runner/test_stats_metrics.py`); each default metric is raised most by its own defect on a built spectrum and a noisy true curve stays under every `good` threshold.

**No longer holds:** the only statistics being Paint's five totals.

**Decisions:** the thresholds (`good`, `bad`) are first values chosen on the built spectra, to be tuned on real studies in the scoring phase; nothing yet reads this package, so statistics.csv and the bar graphs are unchanged.

**Stable pages need:** `stable/internals/paint.md` and `stable/internals/statistics.md` (where the statistics come from), once the package is used by the table.
