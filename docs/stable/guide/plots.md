---
id: plots
summary: how a run's pages get made, and how to get the ones you want; objects, figures, pages and sets
for: driver client dev agent
code: framework/runner/plot.py, framework/runner/plotdoc.py
---

# Plots

A run ends by drawing pages from its complete points. You often need nothing: a `[plot]` table with no figures draws every histogram of the analysis, one page per cell. An errand file with no `[plot]` draws nothing.

To redraw without running anything, use `heimdall plot`, or `heimdall run … --only plot`. Plot settings are not part of what a point computes, so changing them never reruns a point. Every key is in the [settings reference](../../reference/settings/plot.md).

## Three words

- An **object** is data: one histogram, estimate or scatter in a point's YODA (`/ZEUS_2012_I1116258/d01-x01-y01`), one copy per point.
- A **page** is output: one drawn file, a frame with curves, a legend, perhaps a ratio pad.
- A **figure** is a recipe for pages: which objects, how the pages are built (its `class`), what is drawn (its `type`), how it looks.

`[plot].objects` is an implicit figure: every object it matches gets its own page. Declare a figure for the pages you want besides those, or instead of them.

```toml
[plot]                                # what every page shares
ratio = true

[plot.figures.eta_algorithms]         # one more page per cell: three objects of each point
class   = "overlay"
objects = ["d02-x01-y01", "d11-x01-y01", "d12-x01-y01"]
labels  = ["$k_{T}$", "anti-$k_{T}$", "SISCone"]
style.ratio.range = [0.8, 1.1]        # any [plot] page key or style key, for these pages only
```

## Cells and sets

A **cell** is a group of points that share a page. `plot_points` on a configuration names the swept quantities that page: each combination of their values is a cell, and the other swept quantities become curves on it. A **set** (`[plot].sets`) chooses cells and curves by hand instead. With no sets there is one, `totality`, made of the `plot_points` cells.

Each cell draws one page per object. A curve is a complete point, or a combined group. A point whose YODA holds several variants of an object (a swept analysis option) gives one curve per variant.

Weight variations (`/x[…]`), `/RAW`, `/TMP` and the run counters never get pages.

## What happens

1. The Run's plot document is written: `results/<A>/<E>/<R>/plot.toml`. Every drawing reads this and the records, so a run replots even after its source cards change. A point that ran with other inputs than the config now gives is drawn as recorded, and named.
2. Each complete point's YODA is merged into one file in `.cache/<A>/plots/<E>/<R>/`, rebuilt only when a point's YODA changes.
3. One page document is written per page, with its labels, `[plot]` values, curves, mapped data and style.
4. Each backend draws them. A failed page is counted and the job exits 1, but the others are still drawn. What Paint said is in the record's `logs/plot/`.

## Where things go

| Tree | Holds |
|---|---|
| `results/<A>/<E>/<R>/plots/<set>/<backend>/` | the pages, with an `index.html`; `results/…/plots/index.html` links them all |
| `results/<A>/<E>/<R>/statistics/<set>/` | each page's numbers |
| `.cache/<A>/plots/` | working files: page documents, the merged sweep, derived YODAs. `rm -rf .cache` is always safe |

Drawing a set replaces its own `plots/<set>/` and `statistics/<set>/`; other sets' stay as they were.

## Labels

Titles and axis labels come from the analysis's Rivet `.plot` file, under a figure's own (`x_label`, `y_label`). They are LaTeX: Paint draws them through TLatex with math letters set italic. YODA's macros (`\GeV`, `\pT`) work in every backend, and `\newline` or `\\` breaks a line. The ratio pad reads `MC/Data` with data, and `Ratio` without.
