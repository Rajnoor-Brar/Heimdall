# Phase 2: the `framework/stats/` core

Status: done 2026-11-07. Blocked by: phase 1 (done).

### Step 2.1: package, registries, import rule (Size: S)
- Acceptance: `framework/stats/{__init__,bins,metrics,means}.py`. The `Metric` and `Mean` registries have the fields of 00_Plan's Design. `test_imports` holds the rule: stats imports numpy, the standard library and `runner.errors` only, and runner modules import stats only inside functions.
- Files: `framework/stats/*`, `tests/runner/test_imports.py`, `recipes/pth.py` if `stats` is not importable as it is: `framework/` is on the path (`tests/conftest.py:29`, `pth.py`), so `framework/stats/` imports as `stats`. Check that nothing in the stack's site-packages is named `stats`, else name it `hdstats`.
- Check: `taskset -c 0-5 nice -n 10 python -m pytest -q tests/runner/test_imports.py`
- Blocked by: none within the phase.

### Step 2.2: today's statistics in Python (Size: S)
- Acceptance: `rel_abs_area`, `area_ratio`, `ratio_mean`, `ratio_dev` and `chi2_ndf` come from `measured` and equal `statstable.statistics_of` on the fixture.
- Files: `framework/stats/metrics.py`, `tests/runner/test_stats_metrics.py` (new).
- Check: `taskset -c 0-5 nice -n 10 python -m pytest -q tests/runner/test_stats_metrics.py`
- Blocked by: 2.1.

### Step 2.3: the five defaults (Size: M)
- Acceptance: `chi2_ndf`, `norm`, `shape`, `tilt` and `worst` follow 00_Plan's definitions. On built spectra (an exponential with a +20 % normalisation; with a tilt; with one bin ×20; with one bin zero; a true curve with Poisson noise in the tail) each defect raises its own metric most, and the noisy true curve stays under every `good` threshold.
- Files: `framework/stats/metrics.py`, `tests/runner/test_stats_metrics.py`.
- Check: as 2.2.
- Blocked by: 2.2.

### Step 2.4: `linear` and `rms` means (Size: XS)
- Acceptance: `power_mean(x, w, p)` with weights and overflow scaling, `linear` = p 1 and `rms` = p 2, each with its error rule.
- Files: `framework/stats/means.py`, `tests/runner/test_stats_means.py` (new).
- Check: `taskset -c 0-5 nice -n 10 python -m pytest -q tests/runner/test_stats_means.py`
- Blocked by: 2.1.

## Log

2026-11-07: 2.1: `framework/stats/{__init__,bins,metrics,means}.py`; `stats` imports as is (nothing in the stack is named `stats`: `framework/` is on the path, `pth.py` untouched). `test_imports.py` gains two rules: stats imports numpy, the standard library and `runner.errors` only, and no runner module imports stats at module level. 2.2: the four old columns and `chi2_ndf` are in `REGISTRY`; they equal `statstable.statistics_of` to 1e-9 on every curve of the plot-stage fixture (`test_paint_bins.py`, slow) and to 1e-12 on a hand-made page. 2.3: five defaults on built spectra (+20 % yield, tilt, one bin x20, one bin zero, Poisson-noisy true curve): each defect raises its own metric past `bad`, the noisy true curve stays under every `good`. One correction to the plan's formula while testing: the log ratio is floored as `ln(max(y, eps*ref)/ref)`, not `ln((y + eps*ref)/ref)`, which gave an exact curve a cost of ln 1.01 in every bin and made `norm` unequal for a curve 1.2 x high and 1/1.2 low. 2.4: `power_mean`, `power_error`, `linear`, `rms` with weights, overflow scaling and error rules (`test_stats_means.py`). Thresholds are first values, to be tuned on real studies in the scoring phase. Live doc: `docs/live/stats-core.md`.
