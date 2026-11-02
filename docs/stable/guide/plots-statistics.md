---
id: plots-statistics
summary: the numbers behind each page: statistics.csv's columns, [stats], bar graphs, the summary and how points are scored
code: framework/runner/statstable.py, framework/plot/figures/bars.py, framework/plot/figures/paper.py, framework/plot/figures/webpage.py, src/Apps/Paint/Transform.hh
---

# Statistics of the pages

Every page's curves get numbers, computed by Paint on the page (after voiding, alignment and normalisation, over the x span auto-range and gutters give), so every backend agrees with them. They go in `results/…/statistics/<set>/statistics.csv`, a row per page and curve.

- **With each drawing.** `[plot] statistics = false` stops it; `[errand] stats = false` or `--no-stats` for a job's follow-up.
- **Alone:** `heimdall stats <A>/<E>/<R>` measures without drawing, in a fraction of the time.

**`[stats]`** measures otherwise than pages draw; what it leaves unset is the pages' own. [Its keys](../../reference/settings/plot.md).

```toml
[stats]
sets      = ["totality"]
objects   = ["d01-*", "d02-*"]
normalise = "area"                                     # compare shapes, whatever the pages draw
reference = { generator = "py8", pdf = "NNPDF23lo" }   # against this curve ("data": the default; "curves": each page's first)
```

| Column | Holds |
|---|---|
| `page`, `cell`, `object`, `curve`, `point` | which page, the curve's label, its point |
| `reference`, `is_reference` | what it is compared with: the data, else the page's first curve |
| `bins`, `area`, `area_err` | its finite bins in the range; Σ y·Δx and its error |
| `ref_area`, `cmp_area` | on the reference's bins the curve covers (the *compared bins*): each one's area there |
| `abs_area`, `rel_abs_area` | Σ \|y − y_ref\|·Δx, and over `ref_area`: shape and normalisation both count |
| `area_ratio` | `cmp_area` / `ref_area`: the normalisation; bins above and below cancel |
| `ratio_mean` | Σ (y/y_ref)·Δx / Σ Δx: the ratio pad's mean height (Δx in log10 x on a log-x page) |
| `ratio_dev` | Σ \|y/y_ref − 1\|·Δx / Σ Δx: the ratio pad's area about one. 0.1: 10% off on average |
| `chi2`, `ndf`, `chi2_ndf` | Σ (y − y_ref)² / (σ² + σ_ref²) over bins with an error, their number, the ratio |

`legend_statistic = "chi2_ndf"` puts one after each legend entry. A [`statistic` figure](plots-figures.md) draws one as a page per object.

## Bar graphs

`statistics/<set>/bars/<cell>/<object>.<fmt>`: A4 portrait, six panels (χ²/ndf, |Δ|/reference, area/reference, mean ratio, mean |ratio − 1|, area). A bar 20 times the others' median or more is cut at the panel's end, its value written beside it. Colours above and below the base: blue and orange as drawn; violet and yellow when cut; pink and red when absurd (a million times the median, or infinite).

## The summary

`statistics/<set>/summary.pdf`, A4, with `summary/summary_<NN>.png`, and `summary.html`: the same facts as one page, each table scrolling alone, sortable by clicking a header, with nothing to fetch.

**Front pages** say what it holds, list contents, and write every note once, numbered. **Standings** say what is best on the most pages, where the means further on say what is best on average:

- **Scoring:** each page ranks its curves in χ²/ndf, |Δ|/reference, area/reference, the mean ratio and mean |ratio − 1| (ratios by how far from 1 either way). 1st scores 5, down to 5th 1. Equal numbers share the better place. Only pages against data count, when any has data.
- **Head to head:** on every page, in each statistic, each pair plays a match. A point's **win rate** is the share it won. Unlike points it counts every place, and does not depend on a page's curve count.
- **Tables:** the top five per scoreboard; scoreboards page by page and by cell; each cell's head to head. Sorted by total, then wins, then mean rank.

**Then a section per statistic:** a ranking (mean over pages, the two ratios by geometric mean; the area has none, as each object has its own units); page cells against curves; a table per point and object with a mean, the reference saying `ref`, a missing number `–`. Tables wider than a page split into column blocks.
