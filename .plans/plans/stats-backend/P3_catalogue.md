# Phase 3: the opt-in catalogue

Status: done 2026-11-07 (3c with 5.2). Blocked by: phase 2. Everything here is off until named (`[stats].metrics`, `[score].normalise`, a mean's name). Each entry gets a definition note, its guards, thresholds where it is scored (with the reason), and a test on a spectrum built for it. A formula from `notes/` is re-derived, not copied.

### Step 3a: metrics (Size: M)
- Acceptance: `chi2_z`, `poisson`, `tail`, `wmape_yield`, `wmape_axis`, `L4`, `js`, `ad`, `rho1`, `cvar`, `roughness`, `consensus`, `n_eff`, `holes`, `r_int`, `chi2_smooth`, `lambda`/`r2_ln`, plus `centres = "barycentre"`. Each is in the purpose 00_Plan gives it.
- Files: `framework/stats/metrics.py`, `tests/runner/test_stats_metrics.py`.
- Check: `taskset -c 0-5 nice -n 10 python -m pytest -q tests/runner/test_stats_metrics.py`
- Blocked by: 2.3.

### Step 3b: means (Size: M)
- Acceptance: power means for any p (min, harmonic, geometric, cubic, max named), Lehmer p and contraharmonic, LogSumExp β, median, trimmed α, trimmed geometric α, winsorized α, midhinge, trimean, Hodges–Lehmann, Huber and Tukey (IRLS, MAD scale with the IQR fallback), Wasserstein (quantile barycentre on a grid), scale-aligned remapping. Each has an error rule (approximate ones say so) and a refusal where it cannot work (trimmed at α 0.25 with K < 4; harmonic with a zero and no floor).
- Files: `framework/stats/means.py`, `tests/runner/test_stats_means.py`.
- Check: `taskset -c 0-5 nice -n 10 python -m pytest -q tests/runner/test_stats_means.py`
- Blocked by: 2.4.

### Step 3c: fairness methods (Size: S)
- Acceptance: normalisations `median`, `mad`, `minmax`, `surprisal`; `weights_by = "critic"`; aggregators `fisher`, `topsis`, `promethee`; a `dominated` column. Each note names its cost: pool dependence, outlier compression, the sample size it needs.
- Files: `framework/stats/score.py`, `tests/runner/test_stats_score.py` (new).
- Check: `taskset -c 0-5 nice -n 10 python -m pytest -q tests/runner/test_stats_score.py`
- Blocked by: 5.2.

### Step 3d: the registry test (Size: XS)
- Acceptance: every entry has a purpose (metrics), a note, a test naming it, and `default = False` unless it is one of the five.
- Files: `tests/runner/test_stats_registry.py` (new).
- Blocked by: 3a, 3b, 3c.

## Log

2026-11-07: 3a done: 22 opt-in metrics in `stats/metrics.py` (see docs/live/stats-catalogue.md); thresholds set from true-curve percentiles. Finding: the notes' `worst`/`cvar` thresholds (2, 9) charge a statistically true curve about 0.3; `worst` is now (7, 25), `cvar` (14, 45); also `tail` (2.5, 6), `poisson` (3.5, 9). The phase 2 noisy fixture was too kind (reference error 2 % while the curve was noisy); it is now two independent samples. 3b done: scalar means (power family, Lehmer, LogSumExp, median, trimmed, trimmed geometric, winsorized, midhinge, trimean, Hodges–Lehmann, Huber, Tukey) and the ensemble means `wasserstein` (exact for the linear level mean) and `scale_aligned`, from set-merge/notes/mean_types.md; circular/EMA/log/Heronian dropped per set-merge. 3d done: `test_stats_registry.py`. 3c (fairness methods) waits for 5.2. Not run since: the full fast and slow suites.

2026-11-07: 3c done with 5.2 (normalise median/mad/minmax/surprisal, weights_by critic, aggregate fisher/topsis/promethee, `dominated`), in `stats/score.py`; costs named in `Scores.notes` and `docs/live/score-engine.md`.
