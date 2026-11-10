# 02 · The metric catalogue (Pillar 3, and Pillar 1.1's defaults)

## Polarity, everywhere a metric appears

The registry's `better` becomes `polarity`, one of four. Each value has a glyph, a phrase, and an ASCII form for a terminal that is not UTF-8.

| `polarity` | Glyph | Phrase (legends, sidecar) | ASCII | Orientation into a cost (03 §1.2) |
|---|---|---|---|---|
| `lower` | ↓ | lower is better | `[v]` | q = T(m) |
| `higher` | ↑ | higher is better | `[^]` | q = −T(m) |
| `one` | →1 | closest to 1 is better | `[=1]` | q = \|log₁₀ m\| |
| `descriptor` | ○ | a descriptor, not scored | `[o]` | none |

T is the metric's `scale`: `linear` (T(m) = m) or `log` (T(m) = log₁₀ m, for a metric that spans decades, such as `n_eff`).

**Where the glyph goes:**
- **Table headers:** `χ² significance ↓`, `point loss ↓`, `n_eff ↑`.
- **Every table's first footnote:** the legend line "↓ lower is better · ↑ higher is better · →1 closest to 1 · ○ not scored".
- **Bar panels:** in the title.
- **`heimdall explain ranking.<id>`:** its first line.
- **The sidecar:** each metric's `"polarity": "lower"` and its `"phrase"`.
- **`--json`:** each metric's `polarity`.

A Δ column says its own reading: `Δ loss ↓ (negative: better than the baseline)`.

## The catalogue · closed 1.1

**Default?** ● scored by default · ◆ a gate, on by default · ◇ shown by default, not scored · blank: opt-in. "Old id" is today's. "—" in Old id marks a metric this plan adds.

| Internal ID | Old id | Display name | Category | Polarity | Default? | Report description (one line) |
|---|---|---|---|---|---|---|
| `chi2_ndf` | chi2_ndf | χ²/ndf | compatibility | ↓ | ◇ (a column always) | Σ (y − ref)² / (σ² + σ_ref²) per bin with an error; 1 is a true curve. Blind to a bin whose error is as big as its excess. |
| `chi2_sigma` | chi2_z | χ² significance (σ) | compatibility | ↓ | ● | χ²/ndf as standard deviations (Wilson–Hilferty), so pages of 5 and 50 bins share one scale. |
| `poisson_dev` | poisson | Poisson deviance per bin | compatibility | ↓ | ● | Baker–Cousins deviance anchored to the reference's counts: a spike cannot hide in its own error bar. |
| `tail_excess_sigma` | tail | tail excess (σ) | compatibility | ↓ | | \|Z\| of the summed excess beyond 90 % of the reference's yield. |
| `log_yield_ratio` | norm | yield ratio, \|ln\| | normalisation | ↓ | ● | \|ln(Σ y Δx / Σ ref Δx)\|: off by a factor, either way alike; blind to where the yield goes. |
| `yield_ratio` | area_ratio | yield ratio | normalisation | →1 | | the curve's yield over the reference's on the compared bins. |
| `mean_bin_ratio` | ratio_mean | mean bin ratio | normalisation | →1 | | the ratio pad's mean height over the axis as drawn. |
| `log_dev_shrunk` | shape | mean \|ln ratio\|, precision-shrunk | shape accuracy | ↓ | ● | the log ratio's mean size over the axis, a bin less precise than 10 % counted less. |
| `log_dev_l4` | L4 | L4 \|ln ratio\| | shape accuracy | ↓ | ● | (mean \|ln ratio\|⁴)^¼: one bin off by 10× costs as much as thousands of 10 % ones. |
| `mean_abs_ratio_dev` | ratio_dev | mean \|ratio − 1\| | shape accuracy | ↓ | | the ratio pad's mean distance from 1 over the axis, every bin alike. (`wmape_axis` was this.) |
| `yield_weighted_abs_dev` | rel_abs_area | yield-weighted \|Δ\| | shape accuracy | ↓ | | Σ \|y − ref\| Δx / Σ ref Δx: shape and normalisation together, where the yield is. (`wmape_yield` was this.) |
| `consensus_dev` | consensus | deviation from the page's median curve | shape accuracy | ↓ | | `log_dev_shrunk` against the median of ≥ 3 curves, not the reference; pool-dependent. |
| `js_divergence` | js | Jensen–Shannon divergence (bits) | shape similarity | ↓ | | the two shapes as distributions; blind to normalisation and errors. |
| `ad_distance` | ad | Anderson–Darling distance | shape similarity | ↓ | | the cumulative shapes, a gap in the tail weighted up. |
| `tilt` | tilt | tilt, Δ ln ratio across the page | trend | ↓ | ● | the log ratio's fitted change from the first edge to the last. |
| `pull_autocorr` | rho1 | pull autocorrelation, lag 1 | trend | ↓ | ● | near 0 for scatter; near 1 when the curve sits on one side of the reference for stretches. |
| `peak_pull2` | worst | largest pulls², mean of the top k | local defects | ↓ | ● | the mean of the k = max(3, ⌈N/10⌉) largest squared pulls: a glitch χ² spreads thin. |
| `peak_deviance` | cvar | largest deviances, mean of the top k | local defects | ↓ | | `peak_pull2` on the Poisson deviance: a spike counts in full, whatever its error. |
| `log_ratio_roughness` | roughness | roughness of ln ratio | local defects | ↓ | ● | the RMS second difference of the log ratio: a spike or a hole, never a shift or a tilt. |
| `peak_bin_ratio` | — | largest bin ratio (decades) | integrity | ↓ | ◆ at 3 | log₁₀ of the largest \|y\| / ref of a bin: 3 is a bin 1000× its reference. |
| `yield_sign` | — | page yield ≤ 0 | integrity | ↓ | ◆ at 0 | 1 when the page's summed yield is not positive (a cross-section page), else 0. |
| `negative_share` | — | negative-weight share | MC quality | ↓ | | Σ max(−y, 0) Δx / Σ \|y\| Δx: how much of the curve is negative bins. |
| `n_eff` | n_eff | effective events | MC quality | ↑ (scale log) | ◇ | Kish's (Σ y Δx)² / Σ (σ Δx)²: how many equal-weight events the histogram is worth. |
| `hole_fraction` | holes | hole fraction | MC quality | ↓ | | the axis share of interior bins with y ≤ 0. |
| `log_roughness` | r_int | roughness of ln y | MC quality | ↓ | | the RMS second difference of ln y, no reference. |
| `smoothness_chi2` | chi2_smooth | smoothness χ² | MC quality | ↓ | | `log_roughness`'s jumps in units of what scatter explains. |
| `tail_nonlinearity` | r2_ln | tail non-linearity, 1 − R² | MC quality | ↓ | | how far the last quarter is from a straight line in ln y. |
| `tail_slope` | lambda | tail decay rate | MC quality | ○ | | the fitted decay rate of the last quarter; a descriptor. |

**Removed:** `wmape_yield` (identical to `rel_abs_area`, `metrics.py:324`) and `wmape_axis` (`ratio_dev`'s formula, `metrics.py:329`). An old table or setting naming either reads as its twin, through the alias table.

**Thresholds of the new metrics:**
- **`peak_bin_ratio`:** good 1.0, bad 3.0. Ordinary curves reach 2.01 at most in four Runs; the pathological median is 10.7. It is a gate first; scored, it is past bad only for a bin 1000× off.
- **`yield_sign`:** a gate only.
- **`negative_share`:** good 0.0, bad 0.25. Ordinary Sherpa curves reach 0.36 at most (p99 0.18), so it is not a gate.
- **The rest:** each keeps its registry thresholds (V254).

## Defaults: a curated set, one to two a category (Pillar 1.1)

| Category | Default | Why this pair (evidence in 05) |
|---|---|---|
| compatibility | `chi2_sigma` + `poisson_dev` | χ² is error-weighted, so a curve whose error bar is as big as its blow-up passes it: ranks 1–12 of 24 for the pathological points (B1). The reference-anchored deviance is blind to that excuse; together they put those points at 13–24. `chi2_sigma` rather than `chi2_ndf`, because pages here have 5 to 9 bins. |
| normalisation | `log_yield_ratio` | one number says it; `yield_ratio` and `mean_bin_ratio` are the same fact on other scales |
| shape accuracy | `log_dev_shrunk` + `log_dev_l4` | the shrunk mean is the central view but is mute on 10–20 % errors (median 0.04–0.12 against an unshrunk 0.3–0.5); L4 is unshrunk and outlier-sensitive (0.4–1.5 ordinary, about 20 pathological) |
| shape similarity | none | normalisation-blind shape is already shape accuracy's, once `log_yield_ratio` is apart; opt in for a normalised study |
| trend | `tilt` + `pull_autocorr` | the fitted slope, and whether misfit comes in stretches (a slope's or a kink's signature), which a slope alone misses |
| local defects | `peak_pull2` + `log_ratio_roughness` | pull-anchored peaks miss a spike hidden in its own error; the ratio's second difference catches it (0.15–0.6 ordinary, 14–20 pathological) |
| integrity | `peak_bin_ratio`, `yield_sign` (gates) | the clean separation of 05 §1 |
| MC quality | `n_eff` shown | Pythia's curves are worth 1500–20000 events, Sherpa's 2–60: the reader needs it beside a loss, not inside it |

So nine metrics are scored, two are gates, and two are shown. The leaderboard shows category costs, not nine columns (04).

## The alias table

`stats/metrics.py` gains `ALIASES = {old: new}` for every row above whose id changes.
- **Reading** an old `statistics.csv` or sidecar maps its columns, so a format-2 table reads as before.
- **Writing** uses only new ids, and the sidecar's `format` becomes 3.
- **Settings** (`[stats].metrics`, `[ranking].metrics`, `thresholds`, the report keys `<metric>:ranking`) refuse an old id with "renamed: `<old>` is `<new>`". `heimdall migrate` rewrites errand files and recipes.

The rows go into I-26's single table of retired names when it lands.
