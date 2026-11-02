---
id: plots-sets
summary: pages of chosen points: the totality set, named sets with page axes and curve groups, looks, short forms, split
code: framework/runner/sweep.py, framework/runner/plot.py, framework/runner/plotdoc.py
---

# Sets: pages of chosen points

Run once, then page the points as you like. A set is a folder of pages, `plots/<set>/`, with numbers in `statistics/<set>/`. Write one against the real points with `heimdall plot CONFIG|RECORD --plan`, which prints each set's cells and curves without drawing.

## `totality`

Every Run's document holds it first: every point. With `plot_points`, pages along them and curves along the rest. Without, curves along the axis whose number of values is in 4–7 and closest to 5 (else closest to 5; a tie goes earlier in `vary`), pages along every other axis with several values. The choice is written into the document.

## Which are drawn

By default, every set. `[errand] plot`, or a configuration's: `true` every set; `false` none, the document still written; a list those sets (`plot = ["totality", "pdf_by_generator"]`), written as `[plot].draw`. So sets are defined once, and each configuration draws those that fit it. `heimdall plot … --sets a,b` draws others once.

## Named sets

```toml
[plot.sets.beams]                    # a run sweeping generator × energies × events × pdf
pages  = { generator = "all", energies = ["10x20", "15x60"] }   # py8_10x20, py8_15x60, sh3_10x20, sh3_15x60
curves = { events = ["10M", "100M"], pdf = "all" }              # on each: every count × every pdf

[plot.sets.pdf_picks]
pages  = { events = "all" }          # a page per event count
curves = [                           # a list: the union, in order
  { generator = "py8", pdf = ["pdf1", "pdf2", "pdf5"] },
  { generator = "sh3", pdf = ["pdf1", "pdf3", "pdf4"] },
]
reference = { generator = "py8", pdf = "pdf1" }    # moved first: the ratio's reference without data
look      = { colour = "pdf", line = "generator" }
objects   = ["d0[1-4]-*"]            # and any [plot] page key, for this set's pages
```

- **A filter** is `{ quantity = what }`: `"all"`; a tag, glob or list; `"!tag"` to leave a value out; a number. One table is every combination of its quantities; a list is the union, in order. A combination no point has is absent.
- **Pages:** a cell per combination, named by tags joined with `_`. With no `pages`, one cell, unless an axis the set does not name pages. `pages = "none"` says no axis pages at all: one page per object, every curve on it.
- **Curves:** each table in turn, values as written, then point order. A point two tables match is drawn once. With no `curves`, every point of the cell.
- **An axis the set does not name** with several values among its points pages too, and the stage says so: curves never quietly mix what the set did not ask for.
- **Page keys:** a set's lay over `[plot]`'s, and a figure's over the set's. A set's name is its folder, so it may not be `root`, `mpl`, `yoda` or `statistics`.
- **Checked at plan time:** an unknown quantity, a tag no value has, a quantity in both `pages` and `curves`, a `look` quantity that is not a curve axis.

## Looks

`look`'s colour quantity takes the style's palette, and its line quantity solid, dashed, dotted, dashdot (at most 4). A value keeps its look on every page of the set. With no `look`, if curves vary along two quantities and one has at most 4 values, it takes the line. `look = "palette"` turns this off. The palette has 5 colours; more repeat, and the stage says so. Give a longer one: `style = { curves = { palette = ["#rrggbb", …] } }`.

A value in a `curves` table may carry its own look, over the set's:

```toml
curves = [
  { generator = "py8", pdf = [{ tag = "NNPDF23lo", colour = "#d62728", line = "dashed" }, "MSTW08lo"] },
  { generator = "sh3", pdf = { all = true, colours = ["#1f77b4", "#2ca02c", "#9467bd"] } },
]
```

`{ tags = …, colours, lines, widths }` is several values in order; a list of looks shorter than its values is refused. Colours are `"#rrggbb"`, ROOT names (`"kBlue+1"`) or numbers. For a value's look across every set and Run: [plots-curves](plots-curves.md).

## Short forms

```toml
[plot]
sets  = [[1, 4, 6, 8], [1, 2, 4, 9], "all"]   # a page folder each: set1/, set2/, all/
split = 8                                     # at most 8 points a page: all-1/, all-2/, …
```

A short set is a list of selectors, one selector, or `{ name = "lo", points = [...] }`. A selector is a 1-based index, a point's name, a glob of names, any quantity's tag, `"quantity=tag"`, or `"all"`. The first named is a ratio's reference without data. On the command line: `--points 1,4,6,8` or `--set 'plot.sets=[[1,4],"all"]'`. merged, scan and compare figures page by `plot_points` only. Folders of sets no longer drawn stay until you remove them.
