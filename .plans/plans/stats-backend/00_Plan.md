# Statistics backend: measure, score, compare

Issue: I-120. Status: planned 2026-11-07, not started. Implement only on the developer's order.

## Context

Verified at `cd6ceac` (2026-11-07):

- **Paint computes every page statistic in C++** (`src/Apps/Paint/Transform.hh:251` `statistics`). It works on the reference's bins, with the curve rebinned onto them, after voiding, alignment and normalisation, over the auto-range span. It writes totals only (`main.cc:82` `statisticsJson` → `<page>.toml.stats.json`): `bins, area, area_err, ref_area, cmp_area, ratio_area, ratio_sum, ratio_width, abs_area, compared, chi2, ndf, reference`. Python never sees a bin.
- **`framework/runner/statstable.py`** derives `rel_abs_area, area_ratio, ratio_mean, ratio_dev, chi2_ndf` (`statistics_of`) and writes and reads `results/…/statistics/<set>/statistics.csv`. Its callers are `plot._tables`, `plot.measure` (`heimdall stats`) and `report.py`.
- **Scoring and drawing share `framework/plot/figures/bars.py`** (876 lines):
  - `POINTS = (5,4,3,2,1)` per place over `SCORED` (chi2_ndf, rel_abs_area, area_ratio, ratio_mean, ratio_dev), with the ratios scored by \|log10 r\|.
  - Head to head through `_head_to_head` and `_rates`.
  - The RMS over pages through `_rms` and `_mean` (`docs/live/stats-rms.md`).
  - Prose in `DEFINITIONS`, `FORMULAS`, `SCORE_TEXT` and `H2H_TEXT`, which the summary and the report both print.
  - Summary sections `top5*`, `scoreboard*`, `head-to-head*`, `<stat>-ranking|crossed|table` (`summary_model`, `_standings`).
- **No weights exist** anywhere: not per page, object, figure or set.
- **`report.py`** (2408 lines) re-renders sections by key. `HEADLINE` is at :55, `_part` at :1456 and `chosen` at :1404. The allowed names are in `config.py:1407` `STATISTICS`/`SUMMARY` and `framework/schema/report.toml:146`.
- **`[stats]`** (`framework/schema/run.toml:1013-1056`, applied in `plot.measured`, `plot.py:1808`) has `sets`, `objects`, `reference`, `normalise`, `void_empty`, `min_entries`, `auto_range`, `range_pad`.
- **The runner core is standard-library only** (`docs/rules/code.md`). numpy is imported lazily in `cli.py:2413`. numpy is in `recipes/settings.toml` `python_packages` and in the base's `pixi.toml`. scipy is not.
- **Tests that pin today's scoring:**
  - `tests/runner/test_statstable.py`, `test_summary_layout.py` (76 points in 38 cells), `test_report.py`:159 and :210-245, `test_report_build.py`:162.
  - The slow `tests/integration/test_plot_stage.py`:928-993.
- **Collinear pairs.** `rel_abs_area` and `ratio_dev` move together, as do `area_ratio` and `ratio_mean`. Summing five statistics double-counts.

Reference notes, kept for the catalogue's definitions: [notes/histogram_metric.md](notes/histogram_metric.md) and [notes/scoring_fairness.md](notes/scoring_fairness.md). The notes' claims are hypotheses. Each formula is re-derived and tested at its pickup, never copied on trust. Their Python sketch is not code to paste.

## Design

**One seam:** Paint measures (bins), `framework/stats/` computes (metrics, means, scores), and `bars.py`, `report.py` and the CLI only present. Paint stays the one place that decides what a page "as drawn" is, so every backend agrees with the numbers.

**`framework/stats/`** is a package beside `runner/` and `plot/`. It uses numpy, the standard library and `runner.errors`. It never draws.

| Module | Holds |
|---|---|
| `bins.py` | reads `measured` from `<page>.toml.stats.json` into arrays per curve: `lo, hi, y, err, ref_y, ref_err` |
| `metrics.py` | `REGISTRY: name → Metric(fn, purpose, better="lower", thresholds=(good, bad), needs_reference, default, note)` |
| `means.py` | `REGISTRY: name → Mean(fn, error_rule, guards, note)`, with `power_mean(x, w, p)` as the family's core |
| `score.py` | normalise (thresholds by default), page loss, aggregate over pages, marginals, baselines, head to head for one page |
| `table.py` | today's `statstable`, moved; statistics.csv format 2 and its `statistics.json` sidecar |
| `merge.py` | bin-wise means of YODA histograms, written for set-merge (the plan `set-merge`) |

**Purposes.** Every metric has one. The summary and the default report get a section per purpose that has a metric on. A page's loss is the RMS over purposes of each purpose's RMS of normalised metrics, so four shape metrics turned on do not outvote one normalisation metric.

| # | Purpose (section title) | Default on | Opt-in |
|---|---|---|---|
| 1 | Statistical compatibility | `chi2_ndf` | `chi2_z` (Wilson–Hilferty), `poisson` (Baker–Cousins, reference-anchored), `tail` (\|Z_tail\|) |
| 2 | Normalisation | `norm` = \|ln(cmp_area/ref_area)\| | `area_ratio`, `wmape_yield` (= `rel_abs_area`) |
| 3 | Shape accuracy, bin by bin | `shape` = Σ Δx·s·\|ℓ\| / Σ Δx, with s = τ²/(τ²+σ_ℓ²), τ = 0.10 | `ratio_dev`, `rel_abs_area`, `wmape_axis`, `L4` |
| 4 | Shape similarity, as distributions | (none) | `js`, `ad` |
| 5 | Trend | `tilt` = \|weighted slope of ℓ against x\| × span | `rho1` |
| 6 | Local defects | `worst` = mean of the k largest pulls², k = max(3, ⌈0.1 N⌉) | `cvar` (k settable), `roughness` |
| 7 | Monte Carlo quality, without a reference | (none) | `n_eff` (Kish), `holes`, `r_int`, `chi2_smooth`, `lambda` + `r2_ln` |

Here ℓ = ln((max(y,0) + ε·y_ref)/y_ref), ε = 0.01. On a log-x page, x is log10 x. `centres = "mid" | "barycentre"` (Lafferty–Wyatt) sets the x of `tilt`, `rho1` and `roughness`. `consensus` (a metric against the median curve) is opt-in under purpose 3 and its note says it is pool-dependent. Differential entropy is dropped: it describes a width and has no better or worse.

**Normalisation** (`[score].normalise`). The default is `thresholds`: m̃ = max(0, (m − good)/(bad − good)). It is pool-independent, so a score is comparable across Runs and the library. Opt-in: `median` (floored median ratio), `mad` (robust z, softplus), `minmax`, `surprisal`. Also `[score].weights_by = "critic"`, the aggregators `aggregate = "fisher" | "topsis" | "promethee"`, and a `dominated` (Pareto) column. Each note says what it costs, for example "pool-dependent: adding a curve changes the others' scores".

Default thresholds (good, bad) are the Mode B row of the notes' table: chi2_ndf (1, 3), norm (0.02, 0.15), shape (0.02, 0.15), tilt (0.03, 0.25), worst (2, 9). Opt-in metrics get theirs at their step, written into their registry entry with the reason.

**Score.** L_page = RMS over purposes. A point's score = `mean` (default `rms`) of its L_page, weighted by page weights. Beside it go `worst` (its maximum L_page, the page named) and `veto` (worst > `[score].veto`, default off).

**Weights** (normalised to sum 1 in the backend):
- `[score.weights]`, keyed by object glob: `"d01-*" = 2`.
- A figure's `weight`.
- A set's `score = { weights = … }`.
- Precedence: a figure's weight, then the set's weights, then `[score.weights]`, then 1.

**Settings.** `[stats]` says what is measured: today's keys plus `metrics = [...]` (default: the five) and `centres`. `[score]` says how it is scored: `metrics = { name = weight }`, `normalise`, `thresholds`, `weights`, `mean`, `by`, `baseline`, `veto`, `aggregate`, `dominated`. A set's `score = {…}` lays over `[score]`.

**Retired** (developer, 2026-11-07): places 5–1, scoreboards, win rates, `top5-h2h`. **Kept as an opt-in view:** head to head for a chosen page, its curves pairwise with each metric's normalised difference and the loss difference, with no wins counted.

## Phases

Test command, with the stack loaded (`source gjallarhorn.sh`): `taskset -c 0-5 nice -n 10 python -m pytest -q <files>`. ⏸ = stop for the developer.

| # | Phase | Verified when | Blocked by | Size |
|---|---|---|---|---|
| 1 | [Paint writes measured bins](P1_paint_bins.md) | Python's sums of `measured` equal Paint's totals to 1e-12 on every page of the plot-stage fixture | none | M |
| 2 | [stats core](P2_core.md) | each default metric's test spectrum raises its own metric most; test_imports holds the package's rule | 1 | M |
| 3 | [the opt-in catalogue](P3_catalogue.md) | the registry test: every entry has purpose, note, test; only the five are `default` | 2 (3c also 5) | L, split into 3a–3d |
| 4 | [statistics.csv format 2](P4_table.md) | round-trip with the sidecar; an old CSV still reads | 2 | S |
| 5 | [settings and the scoring engine](P5_engine.md) | schema tests; `heimdall explain score`; the purpose-share test | 2, 4 | M |
| 6 | [⏸ summary and report by purpose](P6_present.md) | summary, report and slow plot-stage tests green with their fixtures; the developer reads one summary | 5, retire-yoda-backend 2 | L, split into 6a–6b |
| 7 | [marginals and baselines](P7_marginals.md) | the confounded fixture says so; baseline Δ matches by hand | 5 | S |
| 8 | [`heimdall score`](P8_cli.md) | a CLI test on the scratch work dir; `stats` refused with its new form | 7 | S |

Frontier at the start: 1. After 2: 3, 4 and 5 can run in parallel.

## Decision log

| Decision | Chosen | Why |
|---|---|---|
| Where metrics are computed | Python from Paint's measured bins | One definition of "as drawn" (Paint's), and metrics free of C++ rebuilds |
| Library | numpy in `framework/stats/` (developer: the faster and more reliable) | Already in the base; vectorised bin arithmetic; scipy not needed (Wilson–Hilferty) |
| Default normalisation | hinged thresholds (developer) | Pool-independent: cross-Run scores and the library need it |
| Catalogue | every metric, mean and fairness method with a use, opt-in; five on (developer) | The developer's call: available when someone needs it, quiet otherwise |
| Double counting | loss is RMS over purposes of RMS within | Fixes collinearity structurally without data-hungry CRITIC |
| Places and win rates | retired; head to head per page kept (developer) | Scores are continuous; a pairwise look at one page still helps |
| Weights | object globs and a figure's weight, not a positional list | A list in page order breaks silently when objects change |
| Report sections | by purpose (developer) | A reader asks "is it compatible, is the shape right, are there spikes", not "what is metric 4" |
| Dropped | differential entropy | A width descriptor with no better or worse |

## Not yet specified

- Phase 1: whether `measured` sits inside `stats.json` or in its own `<page>.toml.bins.json`. Decide by size on the plot-stage fixture's largest page (more than 1 MB means a file of its own).
- Phase 3: the thresholds of each opt-in metric, set from its note with the reason written beside it.
- Phase 6: the summary's A4 layout for purpose sections (`docs/stable/guide/plots-statistics.md`, test_summary_layout). This is fog, researched at the phase's pickup.
- Phase 8: whether `heimdall stats` becomes `plot --stats-only` (I-45, decided) in this phase or stays an alias for a release. Decided: refused for a release, with the hint, per I-45.

## Always / Never

- Always: Paint's totals are kept until phase 6 proves Python's equal; old CSVs stay readable; each phase's live doc in its commit; fixtures change only with the test that needs them.
- Never: change an identity or a seed; touch `tests/reference/`; rebuild anything but Paint; edit stable docs (live docs only); name a real study.

## Progress

| Phase | Status |
|---|---|
| Plan | approved 2026-11-07 |
| 1 | done 2026-11-07 |
| 2 | done 2026-11-07 |
| 3 | done 2026-11-07 (3c with 5.2) |
| 4 | done 2026-11-07 |
| 5 | done 2026-11-07 |
| 6 | done 2026-11-07; stopped for the developer's read of one summary |
| 7 | done 2026-11-07 |
| 8 | done 2026-11-07 |
