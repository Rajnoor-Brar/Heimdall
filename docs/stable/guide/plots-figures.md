---
id: plots-figures
summary: figure classes and what each builds, types, and how a figure inherits [plot]
code: framework/runner/plot.py, framework/plot/figures/derive.py, framework/plot/figures/layout.py
---

# Figures

```toml
[plot.figures.tails]          # the figure's key
class   = "defined"           # how its pages are built (the default)
type    = "Hist1D"            # what is drawn; left out, from the objects
objects = ["d04-*"]           # globs: the short name, the option-free path, or a variant's path
logy    = true                # any [plot] page key, x_label, y_label, style.<…>: for these pages only
```

A figure takes every page key of `[plot]`, each meaning what it means there; left out or `"default"` it is `[plot]`'s, and `"native"` the drawing tool's own. What concerns the whole Run stays in `[plot]`: `backend`, `formats`, `objects`, `data`, `root_style`. Every key: [settings](../../reference/settings/plot.md).

| Class | Built from | Pages |
|---|---|---|
| `defined` | an analysis object | `<cell>/<object>` |
| `overlay` | several objects of each point | `<cell>/<name>` |
| `merged` | points merged over an axis, for this figure only | `<cell>/<name>/<object>` |
| `compare` | the same objects across configurations | `results/<A>/<E>/compare/<name>/<backend>/<cell>/<object>` |
| `derived` | a new object per point | `<cell>/<name>` |
| `scan` | one number per point against a swept quantity | `<cell>/<name>` |
| `sheet` | drawn pages, tiled | `plots/<set>/<backend>/sheets/<name>` |
| `statistic` | one statistic per point | `statistics/<set>/figures/<backend>/<cell>/<name>/<object>` |

## `defined`

Takes over the pages of the objects it matches, also those `[plot].objects` leaves out. Two that match one object are refused: one recipe per page. It takes no `labels` or `name`.

## `overlay`

```toml
[plot.figures.eta_algorithms]
class   = "overlay"
objects = ["d02-x01-y01", "d11-x01-y01", "d12-x01-y01"]
labels  = ["$k_{T}$", "anti-$k_{T}$", "SISCone"]
```

A curve per object and point, labelled by `labels` plus the point's when the page has several. The ratio divides by the first curve. Titles are the first object's. Objects must be 1D.

## `merged`

```toml
[plot.figures.avg]
class   = "merged"
objects = ["d01-*", "d05-*"]
over    = ["replica"]            # curve axes merged away
```

Per value of the other curve axes, the YODAs merged (`rivet-merge -e`: statistics add, σ averaged). The Run keeps its points apart, and only this figure merges them; `combine` does it for the whole configuration. `over` must name curve axes, and may not also be banded.

## `compare`

```toml
[plot.figures.chains]
class          = "compare"
objects        = ["d01-*"]
configurations = ["default", "Demo/inproc_validation:default"]   # "<A>/<E>:<cfg>": another errand file's
labels         = ["chain", "in one process"]
```

Each curve is a configuration and a point. It needs two or more configurations, at least one of this file, with the same page and curve axes (checked at plan time). Drawn by each named configuration's plot stage once all have complete points; until then the stage says what it waits for.

## `derived`

```toml
[plot.figures.r15]
class   = "derived"
op      = "ratio"                # ratio, difference, sum (two objects); projection-x, -y (one 2D)
objects = ["d01-x01-y01", "d05-x01-y01"]
y_label = "d01 / d05"
```

A new object `/FIGURES/<name>` in every point, in a copy of its YODA, made by `framework/plot/figures/derive.py` with YODA's Python. Two objects need the same binning. It is then an object like any: an overlay, merged or compare figure may name it.

## `scan`

```toml
[plot.figures.sigma_vs_pt0]
class = "scan"
x     = "pt0ref"                 # a curve axis whose values are numbers
y     = "sigma"                  # sigma, entries, integral, mean, bin:N
```

A curve per value of the other curve axes, drawn as markers. `integral`, `mean`, `bin:N` read one object. `x` cannot be a page axis nor banded, and a quantity of names cannot be an `x` yet.

## `sheet`

```toml
[plot.figures.paper_fig3]
class   = "sheet"
pages   = ["18x275/d02-x01-y01", "18x275/eta_algorithms", "*/r15"]   # globs of page names, in order
columns = 3
```

After a configuration's pages are drawn, tiled by pdflatex as vectors into `.pdf`, rendered to `.png` by pdftoppm. Paint's and mpl's pages. It takes no page keys, has no shared y title or legend, and does not take compare pages. A glob naming no page fails it.

## `statistic`

```toml
[plot.figures.rank]
class     = "statistic"
statistic = "chi2_ndf"
objects   = ["d01-*", "d02-*"]
sort      = true                 # the smallest first
```

The page's curves as bins, each labelled under the axis, y its statistic against the reference. Paint writes names under the axis; mpl draws bins by number.

## Types

| `type` | Drawn as | Default for |
|---|---|---|
| `Hist1D` | steps, error bars at bin centres (or a band, or none: `curves.errors`) | a 1D object |
| `Scatter2D` | a marker per bin with its error bar | a scan |
| `HeatMap` | one 2D object coloured by value, its scale on the right (`z_label`, `logz`) | a 2D object |

A heat map is per point of the cell, `<cell>/<object>/<point>`, Paint alone. No ratio, data or voiding; its ranges are its own figure's alone. A 1D object as a HeatMap, a 2D as a Hist1D or Scatter2D, and a 2D in an overlay are refused; to see a 2D object in 1D, project it with a `derived` figure.
