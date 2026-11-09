---
id: plots
summary: how a run's pages get made, and how to get the ones you want; objects, figures, pages and sets
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

A **cell** is a group of points that share a page. `plot_points` on a configuration names the swept quantities that page: each combination of their values is a cell, and the other swept quantities become curves on it. A **set** chooses cells and curves by hand instead: [plots-sets](plots-sets.md). Every Run's document holds a set named `totality`, every point.

Each cell draws one page per object. A curve is a complete point, or a combined group. A point whose YODA holds several variants of an object (a swept analysis option) gives one curve per variant.

Weight variations (`/x[…]`), `/RAW`, `/TMP` and the run counters never get pages.

## In practice

```toml
[plot]
formats     = ["pdf", "png"]
objects     = ["/photo_eic/d0*"]  # which objects get their own pages
ratio       = true
y_gutter    = 0.5                 # the y axis reaches 1.5 × the largest value; "native": ROOT decides
x_range     = ["default", 100]    # keep the calculated minimum; cap the maximum
auto_range  = true                # trim x to the filled bins …
range_pad   = 1                   # … keeping one bin either side
void_empty  = true                # blank bins empty in every curve
min_entries = 10                  # blank bins fewer raw entries went into, in any curve
normalise   = "area"              # every curve, and the data, to unit area: compare shapes
title       = "{cell}"            # placeholders cite the points
root_style  = "talk"              # talk.toml beside the errand file, over the base style
```

**The order on a page:** void across the page → align the data to the MC bins → normalise → auto-range → gutters → `x_range` → y-range over the visible x span → `y_range` → draw. Each range end is resolved on its own: a figure's `["default", 10]` keeps `[plot]`'s minimum. Ranges only show and only cut what is drawn: statistics are taken over the range before them, and ratios from the curves' own values. Each pad cuts at its own frame, so an MC bin off the top of the main pad may still show in the ratio pad. A range leaving no increasing span, or an explicit minimum ≤ 0 on a log axis, fails that page (exit 1); a calculated range is never refused, so an empty log-y page still draws.

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

## The plot document

Every drawing reads `results/<A>/<E>/<R>/plot.toml` and the folder's `points/`, with no errand file, tool folder or stack beyond Paint. So the folder can be copied anywhere and drawn there. It holds what the Run knows (`[source]`, `[axes]`, `[quantities.<q>]`, `[members.<point>]`), rewritten each run, and what you choose (`[plot]`, `[stats]`), written once from the errand file and then kept. **Edit it to restyle that Run alone.**

A member's `choice` and `values` and `[axes].fixed` name each value by its **tag** (`pdf = "MSTW08lo"`), not its place in `[quantities.<q>].points`, so those points may be reordered and every member keeps its value and label. A point taken out of `[quantities.<q>]` (commented out, removed) leaves the members with that value out of the drawing and the statistics, and `heimdall plot` says so once (`N member(s) left out, a value not in the document's [quantities]: …`); the others are drawn as before. The next job on the folder rewrites `[quantities]` and `[members]`, so a point taken out by hand comes back then: to leave a value out of every drawing, use a set's filter or `--points SEL`. A document that names values by place (`pdf = 2`) reads as before, a place past its list refused naming the member; `heimdall migrate --plot-docs --apply` rewrites it by tag.

| `heimdall plot …` | Draws |
|---|---|
| `<A>/<E>/<R>`, or a path into its folder | that Run's document, as it is |
| a folder holding a `plot.toml` | that document |
| `CONFIG [CFG]` | each configuration's latest Run, from its document; a differing `[plot]` in the config is said |

To take the config's `[plot]` into Runs:

```bash
heimdall plot Demo/validation/04_pdf --style-sync Demo/validation --plan   # what would change
heimdall plot Demo/validation --style-sync Demo/validation --replot                  # every Run of it, then drawn
```

What the Run knows is never touched. A Run whose points the config's `[plot]` cannot page is left, and said.

## Labels

Titles and axis labels come from the analysis's Rivet `.plot` file, under a figure's own (`x_label`, `y_label`). They are LaTeX: Paint draws them through TLatex with math letters set italic. YODA's macros (`\GeV`, `\pT`) work in every backend, and `\newline` or `\\` breaks a line. The ratio pad reads `MC/Data` with data, and `Ratio` without.

More: [plots-sets](plots-sets.md), [plots-figures](plots-figures.md), [plots-data](plots-data.md), [plots-curves](plots-curves.md), [plots-style](plots-style.md), [plots-statistics](plots-statistics.md), [plots-across](plots-across.md), [overlay](overlay.md), [reports](reports.md).
