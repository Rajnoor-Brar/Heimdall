---
id: plots-statistics
summary: the numbers behind each page: statistics.csv's columns and sidecar, [stats], [score], the summary and how points are scored
code: framework/stats/, framework/runner/statstable.py, framework/runner/scorecmd.py, framework/plot/figures/bars.py, src/Apps/Paint/Transform.hh
---

# Statistics of the pages

Every page's curves get numbers, computed on the page (after voiding, alignment and normalisation, over the x span auto-range and gutters give), so every backend agrees with them. Paint writes the bins it measured, in each curve's `stats.json`; `framework/stats/` computes the metrics from them. They go in `results/…/statistics/<set>/statistics.csv`, a row per page and curve.

- **With each drawing.** `[plot] statistics = false` stops it; `[errand] stats = false` or `--no-stats` for a job's follow-up.
- **Alone:** `heimdall plot <A>/<E>/<R> --stats-only` measures without drawing, in a fraction of the time. `heimdall stats` is retired, and says so.
- **Read, not measured:** `heimdall score <A>/<E>/<R>` prints the standings, marginals and baseline of a table already measured; see below.

**`[stats]`** measures otherwise than pages draw; what it leaves unset is the pages' own. [Its keys](../../reference/settings/plot.md).

```toml
[stats]
sets      = ["totality"]
objects   = ["d01-*", "d02-*"]
normalise = "area"                                     # compare shapes, whatever the pages draw
reference = { generator = "py8", pdf = "NNPDF23lo" }   # against this curve ("data": the default; "curves": each page's first)
metrics   = ["chi2_ndf", "norm", "shape", "tilt", "worst", "poisson"]   # the columns computed
centres   = "mid"                                      # or "barycentre", for tilt and roughness
```

## The table

`statistics.csv` has these columns first, in this order; a metric that is on and is not among them follows, a column each (by default `norm`, `shape`, `tilt`, `worst`). A bin-less page has them empty.

| Column | Holds |
|---|---|
| `page`, `cell`, `object`, `curve`, `point` | which page, the curve's label, its point; `run` after `point` when Runs are together |
| `reference`, `is_reference` | what it is compared with: the data, else the page's first curve |
| `bins`, `area`, `area_err` | its finite bins in the range; Σ y·Δx and its error |
| `ref_area`, `cmp_area` | on the reference's bins the curve covers (the *compared bins*): each one's area there |
| `abs_area`, `rel_abs_area` | Σ \|y − y_ref\|·Δx, and over `ref_area`: shape and normalisation both count |
| `area_ratio`, `ratio_mean`, `ratio_dev` | `cmp_area` / `ref_area`; the ratio pad's mean height; its area about one |
| `chi2`, `ndf`, `chi2_ndf` | Σ (y − y_ref)² / (σ² + σ_ref²) over bins with an error, their number, the ratio |

**The sidecar.** `statistics.json` beside it holds `format = 2`, the columns, and for each metric column its purpose, direction, thresholds, default flag, note and the reason for the thresholds, then the `[score]` the table was scored with and the sweep's `axes` (`{point: {axis: tag}}`) and, for a merged curve, `merged`. A csv with no sidecar is format 1 and reads as before. A table of Runs together has a `run` column; one without has none.

`legend_statistic = "chi2_ndf"` puts one after each legend entry. A [`statistic` figure](plots-figures.md) draws one as a page per object.

## Metrics

`heimdall explain score` lists them by purpose, with the means; `heimdall explain score.<name>` shows one in full: its direction, thresholds and why, and what it needs. A metric asks one of the purposes (compatibility, normalisation, shape, …) and has two thresholds, `good` and `bad`: its cost is 0 at or inside `good`, 1 at `bad`, linear beyond, so a cost depends on the metric alone.

- **On by default:** `chi2_ndf` (compatibility), `norm` (|ln yield ratio|), `shape` (mean |ln ratio|, a noisy bin counted less), `tilt` (the ratio's change across the page), `worst` (the mean of the k largest squared pulls). The log ratio is floored at 1 % of the reference, so a hole costs a finite amount and an exact curve nothing.
- **Opt in, with `[stats].metrics`:** 22 more, among them `chi2_z`, `poisson`, `tail`, `js`, `ad`, `L4`, `roughness`, `holes`, `consensus`. Some need a null distribution or other pages (their note says).
- **Thresholds** are set from draws of a true curve as noisy as its reference, then to be tuned on real studies; each says why.

## Bar graphs

`statistics/<set>/bars/<cell>/<object>.<fmt>`: A4 portrait, a panel for each metric that is on (`bars.panels`). A bar 20 times the others' median or more is cut at the panel's end, its value written beside it. Colours above and below the base: blue and orange as drawn; violet and yellow when cut; pink and red when absurd (a million times the median, or infinite).

## Scoring

`[score]` says how the table is scored, beside `[stats]`, which says what is measured: an errand file's keys `metrics` (those that count; the five defaults when none), `normalise`, `thresholds`, `weights`, `weights_by`, `mean`, `by`, `baseline`, `veto`, `aggregate`, `dominated`, `head_to_head` ([keys](../../reference/settings/plot.md)). A set's `score = { … }` lays over it for the set's pages, and a figure's `weight` weighs its page. Names are checked when the file is read. A Run's plot document keeps the `[score]` it was written with (`--style-sync` takes the config's).

A point's **score** is built in three steps, from rows alone, so it is the same whatever else is in the pool:

1. each metric becomes a **cost** by its thresholds;
2. a purpose's value is the weighted root mean square of its metrics' costs, a page's **loss** the RMS over the purposes that have a metric, so four shape metrics weigh one purpose;
3. the score is the `mean` (RMS by default) of its page losses, a page weighted by its figure's `weight`, else the first `[score].weights` glob matching the object, else 1.

A missing metric is skipped; a point with nothing to score has no score and ranks last. A page's reference curve is not scored, and when some pages are against data and others against a curve, only the data pages count. A merged curve scores as any curve: a mean can beat every member.

Choices that cost something say so in their notes: `normalise = "median" | "mad" | "minmax"` use the curves on the page, so adding a curve moves everyone; `surprisal` needs a null (`chi2_ndf`, `chi2_z`, `tail`); `weights_by = "critic"` refuses fewer than 15 curves; `aggregate = "fisher"`, `"topsis"`, `"promethee"` score otherwise, the last two pool dependent. A `veto` fails a point on a page by a metric's `bad`.

## The summary

`statistics/<set>/summary.pdf`, A4, with `summary/summary_<NN>.png`, and `summary.html`: the same facts as one page, each table scrolling alone, sortable by clicking a header, with nothing to fetch. It shades a metric by its cost, so a colour means the same on every table.

**Front pages** say what it holds, list contents, and write every note once. Then:

- **Standings:** a table, ranked within each page cell, of each point's `score`, its `worst page` and loss, a `veto` column when asked, a column a purpose, a `dominated` column when asked; and the purposes with their metrics under each.
- **A section a purpose** with a metric on: a ranking of the points' value for the purpose, then for each of its metrics a ranking (each point's mean over the pages where it was compared), the page cells against the curves, and a table (a row a point, a column an object). Missing is `–`; a table wider than a page splits.
- **Marginals:** a table per axis of the points' mean score for each value, their number and a column a purpose; a confounded axis says what confounds it.
- **Baseline:** `[score].baseline` (`{ axis = "tag" }` or a point's name): each point against the point equal to it on every other axis, Δscore and Δloss per object, negative better; points with no partner are listed with the reason.
- **Head to head,** only for the pages `[score].head_to_head` names (`"<cell>/<object>"` or `"all"`): each pair of a page's curves, the row's loss less the column's. No wins are counted.

A metric with no number has no section. Marginals and baseline need the sweep's `axes`, so a curve merged from several points never enters either.

## `heimdall score`

```bash
heimdall score Demo/jets/01_pdf --by pdf --baseline pdf=NNPDF23lo   # the standings, marginals and baseline; nothing drawn
heimdall score Demo/jets                                            # a row a Run, with its serial
```

`--set S`, `--by AXES`, `--baseline FILTER` (`axis=tag[,axis=tag]` or a point's name), `--json`. It scores with the `[score]` the table's sidecar carries, `--by` and `--baseline` over it; a table measured before the sidecar held the axes reads them from the Run's `plot.toml`. For `<A>/<E>` the row of a Run is the mean of its points' scores over the pages every Run of the errand has; `--across` reads the errand's own folder.
