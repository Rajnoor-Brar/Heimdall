---
id: live-stats-catalogue
summary: the opt-in metrics and means of framework/stats, off until named
affects: plots
issue: I-120
---

**Now holds:** `stats.metrics.REGISTRY` has 27 metrics: the five defaults and, opt-in, `chi2_z`, `poisson`, `tail`, `area_ratio`, `ratio_mean`, `wmape_yield`, `ratio_dev`, `rel_abs_area`, `wmape_axis`, `L4`, `consensus` (pooled), `js`, `ad`, `rho1`, `cvar`, `roughness`, `n_eff`, `holes`, `r_int`, `chi2_smooth`, `r2_ln`, `lambda`. Each has a purpose, a direction (`lower`, `higher`, `one`, `none`), a note, thresholds with the reason (`why`), and `Metric.loss` (hinged: 0 at `good`, 1 at `bad`). `centres_mode="barycentre"` is a setting of `tilt` and `roughness`. `stats.means.REGISTRY` has 22 means: the power family (`linear`, `rms`, `cubic`, `geometric`, `harmonic`, `min`, `max`, `power`), `lehmer`, `contraharmonic`, `logsumexp`, `median`, `trimmed`, `trimmed_geometric`, `winsorized`, `midhinge`, `trimean`, `hodges_lehmann`, `huber`, `tukey`, and two ensemble means of whole histograms, `wasserstein` and `scale_aligned`. Each has a guard that refuses what it cannot work on, and an error rule marked `exact`, `first order` or `approximate` (a seeded 200-draw spread). Tests: `test_stats_metrics.py`, `test_stats_means.py`, `test_stats_registry.py`.

**No longer holds:** `power_mean` taking |x| for every p: p = 1 and odd integers now keep the sign (set-merge averages signed densities). The log ratio is `ln(max(y, eps*ref)/ref)`, not `ln((y + eps*ref)/ref)`.

**Decisions:** thresholds were set from 60 to 400 draws of a true curve as noisy as its reference. That moved `worst` from the notes' (2, 9) to (7, 25), since a true curve's top-4-of-40 squared pulls have median 4.1 and p97 6.6, so good = 2 charged it. `tail` is (2.5, 6), not (1, 3) (half-normal). `poisson` is (3.5, 9) because a true curve as noisy as its reference reads 2. `chi2_smooth` divides by neighbours' variance plus their mean variance as the bin's own (about 1 for a smooth curve), not the notes' 2·V_n. The Jeffreys floor in `poisson` is 0.5/s in weighted content. Fairness methods (3c) wait for the scoring engine.

**Stable pages need:** `guide/plots-statistics.md` (the metrics and their thresholds), `internals/extending.md` if means are extended.
