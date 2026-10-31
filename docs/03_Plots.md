# 03 — Plots and figures

How the pages are made and how to get the ones you want: the plot stage, `[plot]` in practice,
reference data, curves and bands, the style, the seven figure classes, what can be drawn, the
backends, and overlays of any files. Every key is in [04 §11](04_Config_Reference.md#11-plot) and
[04 §12](04_Config_Reference.md#12-the-style); how the stage works inside is
[06 §13](06_Internals.md#13-the-plot-stage-inside).

---

## 1. Objects, figures and pages

Three words carry the whole chapter:

- An **object** is data: a histogram, estimate or scatter in a point's YODA
  (`/ZEUS_2012_I1116258/d01-x01-y01`), one copy per point.
- A **page** is output: one drawn file, a frame with curves, a legend, perhaps a ratio pad.
- A **figure** is a recipe for pages:
  - which objects;
  - how the pages are built (its **class**);
  - what is drawn (its **type**);
  - how it looks (any `[plot]` page key, and a style layer).

  One figure gives a page per `plot_points` cell, and per object when it names a glob.

`[plot].objects` is an **implicit figure**: every object it matches (by default, every 1D and 2D
object) gets its own page. A run that declares no figure draws the analysis's histograms, one page
each per cell, and that is often all you need. Figures are for the pages you want *besides* or
*instead of* those.

```toml
[plot]                                # what every page shares
ratio = true

[plot.figures.eta_algorithms]         # one more page per cell: three objects of each point
class   = "overlay"
objects = ["d02-x01-y01", "d11-x01-y01", "d12-x01-y01"]
labels  = ["$k_{T}$", "anti-$k_{T}$", "SISCone"]
style.ratio.range = [0.8, 1.1]        # any [plot] page key or style key, for these pages only
```

---

## 2. The plot stage

The plot stage runs after the points and the stages. It first writes the run's **plot document**,
`results/<P>/<name>/<cfg>/plot.toml` (§2.2), and then draws every page from that document alone. The pages
are drawn from the points whose **record is complete** (their `.complete` is there). A point that ran with
other inputs than the config gives now is drawn as recorded, and named. It also runs on `heimdall run …
--only plot` and on `heimdall plot`, which redraw without running anything (§2.2). A configuration whose
run TOML has no `[plot]` draws nothing; `--plot FILE` draws with another file's.

1. **The sweep in one file.** Every complete point's YODA is merged into
   `.cache/<P>/plots/<name>/<cfg>/<cfg>.root`, with a directory per point and the raw entries. It is
   rebuilt only when a point's YODA changed.
2. **One page document per page**, in `.cache/<P>/plots/<name>/<cfg>/<set>/[<cell>/]<object>.toml`. It holds:
   - the labels from the analysis's Rivet `.plot` file;
   - the `[plot]` values and the page's figure's own;
   - the curves;
   - the mapped data;
   - what the style layers change.
3. **Draw**: Paint on every page, then any other backend on the same documents (§9). A failed page
   is counted, and the run exits 1, but the others are drawn. What Paint said is kept in the record's
   `logs/plot/<set>.root.log` (a failed conversion's in `convert-<point>.log`), and the failure names
   the file.

The pages go to `results/…/plots/<set>/<backend>/[<cell>/]<object>.<fmt>`. With no `sets`, the set is
`totality`, the `plot_points` cells. Each set and backend has an `index.html` (a section per cell, each page
shown and linked to every format drawn), and `results/…/plots/index.html` links them all. **Drawing a set
replaces its own folders**, `plots/<set>/` and `statistics/<set>/`; other sets' stay as they were.

**Where each tree's files are:**
- **`results/<P>/<name>/<cfg>/`** holds what matters once a run is done: `points/` (the products),
  `plots/<set>/` (the pages) and `statistics/<set>/` (their numbers, §3.2).
- **`records/`** holds what a run needs while it runs or is launched, and what traces it back. It holds
  nothing a drawing reads.
- **`.cache/<P>/plots/`** holds the drawing's working files: page documents, the merged sweep, derived and
  merged YODAs, converted data. They are rebuilt when missing, and `rm -rf .cache` is always safe.

**What a page is made of.**
- **Curves:** its curves are the cell's complete points (or combined groups). A point whose YODA
  holds several variants of the object (a swept analysis option) gives one curve per variant,
  labelled `… [R=0.4]`.
- **Curve labels:** a curve's label is the curve quantities' labels joined with `, `, or the run's
  name when nothing is swept.
- **Not pages:** weight variations (`/x[…]`), `/RAW`, `/TMP` and the run counters never get pages.

**Labels.**
- **Where they come from:** titles and axis labels come from the analysis's `.plot` file (our
  plugins' copies in `build/Rivet/`, then Rivet's data directory): `Title` (else `LegendTitle`),
  `XLabel`, `YLabel`, `ZLabel`, `LogX`, `LogY`, `LogZ`, `RatioPlot`, later blocks winning.
- **They are LaTeX**, and Paint draws them through TLatex, with math letters set italic (`$E_T$` →
  `#it{E}_{#it{T}}`).
- **Line breaks:** YODA's macros (`\GeV`, `\TeV`, `\pT`) work in every backend, and `\newline` (or
  `\\`) breaks a title into lines. A `$…$` left open across the break is closed and reopened for
  you.
- **The ratio pad** is labelled `MC/Data` with data, and `Ratio` without.

### 2.1 What a drawing makes

All of it is in `results/<P>/<name>/<cfg>/` (`<s>` is a set) unless said:

| Output | Made from | By | When | Where |
|---|---|---|---|---|
| object pages | the points' 1D objects | Paint; mpl; rivet-mkhtml | always (`[plot].objects` narrows) | `plots/<s>/<backend>/[<cell>/]<object>` |
| a defined figure's pages | the same, with the figure's keys | the same | declared (§7.1) | the same |
| overlay pages | several objects of a point | the same | declared (§7.2) | `…/<cell>/<name>` |
| derived pages | a new object per point | derive.py, then the same | declared (§7.4) | `…/<cell>/<name>` |
| merged pages | points merged over an axis | rivet-merge, then the same | declared (§7.3) | `plots/totality/<backend>/<cell>/<name>/<object>` |
| scan pages | a number per point against a quantity | derive.py, then the same | declared (§7.6) | `plots/totality/<backend>/…/<name>` |
| heat maps | a 2D object, a page per point | Paint only | always, for 2D objects | `…/<cell>/<object>/<point>` |
| compare pages | several configurations | Paint; mpl; rivet-mkhtml | declared (§7.5) | `results/<P>/<name>/compare/<figure>/<backend>/` |
| sheets | drawn pages, tiled | pdflatex, pdftoppm | declared (§7.8) | `plots/<s>/<backend>/sheets/<name>` |
| indexes | drawn pages | Heimdall; rivet-mkhtml's own | always | `plots/<s>/<backend>/index.html`, `plots/index.html` |
| legend numbers | each page's statistics | Paint, a first pass | declared (`legend_statistic`) | in the page |
| the statistics table | each page's statistics | Paint | always (`statistics = false` stops it) | `statistics/<s>/statistics.csv` |
| bar graphs | the table | matplotlib | with the table | `statistics/<s>/bars/…`, `statistics/<s>/summary` |
| statistic pages | the table, a bin per curve | Paint | declared (§7.9) | `statistics/<s>/figures/<backend>/<cell>/<name>/<object>` |
| the merged sweep, page documents, working YODAs | the points' YODAs | App_yd2rt, Heimdall | always | `.cache/<P>/plots/<name>/<cfg>/` |
| the plan | the sets' cells and curves | Heimdall | `heimdall plot … --plan` | the terminal |

### 2.2 The plot document: `<cfg>/plot.toml`

Every drawing reads one file, `results/<P>/<name>/<cfg>/plot.toml`, and the folder's `points/`. It needs no
run TOML, snapshot, tool folder or stack beyond Paint. A run writes it before it draws, and the folder can
be copied anywhere and drawn there (`heimdall plot <folder>`). It holds two kinds of table:

- **What the run knows**, rewritten by every run of the folder:
  - `[source]`: the config, the configuration, the folder, its tag (when it has one: from its record, 05 §1.1), Heimdall's revision, when;
  - `[axes]`: the sweep's axes, `plot_points`, `combine` and the fixed values;
  - `[quantities.<q>]`: its points in its order, as a run TOML writes them, `points = [{ tag, value, label }]`
    (with `style` on a point that has one);
  - `[members.<point>]`: each point (or combined group) the pages draw, with its value indices, its YODA
    under the folder, the identity it ran with, whether it was complete, and the texts its tools give.
It is written as a run TOML is written by hand: a header for `[source]`, `[axes]`, each `[quantities.<q>]`,
`[plot]` (and `[plot.data]`, `[plot.style]`, each `[plot.sets.<set>]`, `[plot.figures.<figure>]`,
`[plot.looks.<q>]`), `[stats]` and each `[members.<point>]`, last; everything below those is inline (a member's
`choice = { … }` and `values = { … }`, a set's `pages` and `curves`).

- **What you choose**, `[plot]` (and `[stats]`). It is written once, from the run TOML's: its imports and
  `--set`s applied, `root_style` laid into `[plot.style]`, and the data file's path made absolute. After
  that it is kept. **Edit it to restyle that run alone.** A later run of the folder keeps it. When the
  config's `[plot]` differs from it, the run says so and gives the command that takes the config's,
  `heimdall plot <P>/<name>/<cfg> --style-sync <config>`.

**Which document `heimdall plot` draws:**

| `heimdall plot …` | Draws |
|---|---|
| `<P>/<name>/<cfg>`, or a path into its folder of `records/` or `results/` | that run's document, as it is |
| a folder holding a `plot.toml` (anywhere) | that document; its working files go to `.cache/<P>/plots/elsewhere/` |
| `CONFIG [CFG]` | each configuration's latest run (its newest folder), from its document; the config's `[plot]` differing from the document's is said |

**Taking the config's `[plot]` into runs:**

```bash
heimdall plot eic/zeus/04_generator_pdf --style-sync eic/zeus --plan   # what would change, written nowhere
heimdall plot eic/zeus/04_generator_pdf --style-sync eic/zeus          # the document's [plot] and [stats] become the config's
heimdall plot eic/zeus --style-sync eic/zeus --replot                  # every run of eic/zeus, then drawn
```

What the run knows is never touched, and its `totality` set stays its own: it follows the run's axes (the
`plot_points` it ran with), only the picks (`draw`) are the config's. A run whose configuration the config lacks, or whose points the config's
`[plot]` cannot page (a set naming a quantity or a tag it has not), is left, and said; the others are synced.
Nothing is drawn unless `--replot`.

Nothing is planned and no tool is read. A run made before plot documents gets one, written from its snapshot
the first time it is drawn; `heimdall migrate --plot-docs [<P>/<name>/<cfg>…]` writes every record's (a dry run
unless `--apply`). A compare figure's other configurations are drawn from their own documents: the newest
folder of the same run TOML's configuration, a record, or `"<config>:<cfg>"`'s newest.


---

## 3. `[plot]` in practice

```toml
[plot]
backend     = "root"              # "mpl", "yoda", or a list of them; "both" is root and yoda
formats     = ["pdf", "png"]
objects     = ["/photo_eic/d0*"]  # which objects get their own pages (default: every one)
ratio       = true
y_gutter    = 0.5                 # the y axis reaches 1.5 × the largest value; "native": ROOT decides
x_gutter    = "default"           # no x gutter; 0.1 widens x by 10 %
x_range     = ["default", 100]    # keep the calculated minimum; cap the maximum at 100
y_range     = ["default", 1e4]    # keep the calculated minimum; cap y at 10⁴ (a log axis takes no 0)
auto_range  = true                # trim x to the filled bins …
range_pad   = 1                   # … keeping one bin either side
void_empty  = true                # blank bins empty in every curve
min_entries = 10                  # blank bins fewer raw entries went into, in any curve
normalise   = "area"              # every curve, and the data, to unit area: compare shapes
title       = "{cell}"            # placeholders cite the points (04 §10)
root_style  = "talk"              # configs/<P>/talk.toml, over the base style
```

**Placeholders.** Every page text may cite the points it is drawn from:
- `{cell}`, the page's `plot_points` values;
- `{q:<quantity>}`, the label of its value;
- what a tool folder gives, such as Rivet's `{opt:NAME}`, an analysis option at the point.

A page text's placeholder must have one value across the page's curves; a curve label's is its own
point's. A cited name the points don't have is refused at plan time.

**`"default"` is the layer below; `"native"` is the drawing tool's own.** A key left out of `[plot]`,
or `"default"` there, takes the runner's default from the schema: a missing `y_gutter` is 0.5. In a
figure, either is `[plot]`'s value. `"native"` sets nothing, in `[plot]` or a figure, and the drawing
tool does what it does by itself: no gutter, no voiding, the `.plot`'s log axes and ratio. (A v2
file wrote that as `"default"` in `[plot]` itself; `heimdall migrate --v3` rewrites it.) The full table is
[04 §11](04_Config_Reference.md#11-plot).

**The order on a page** (load-bearing, inherited from v1): void across the page → align the data to
the MC bins → normalise → auto-range over curves and data → gutters → `x_range` → y-range over the
visible x span → `y_range` → draw. Each range is `[minimum, maximum]`, and each end is resolved on its
own: `"default"` at one end is the layer below's end, so a figure's `["default", 10]` keeps `[plot]`'s
minimum, and in `[plot]` it is the end the steps before calculate. The ranges only show: the
statistics (§3.2) are taken over the range before them. A range that leaves no increasing span, or
an explicit minimum ≤ 0 on a log axis, fails that page (exit 1); an axis without an explicit end is
never refused for its calculated range, so an empty log-y page still draws.

### 3.1 Pages of chosen points: `sets` and `split`

Run once, then page the points as you like, whatever `plot_points` says. A set is a folder of pages,
`plots/<set>/`, with its numbers in `statistics/<set>/`.

**The totality set.** Every run's plot document holds a set named `totality`, first, unless the config
defines one of that name: every point, nothing left out. Its pages and curves:
- **With `plot_points`:** pages along them, curves along the rest.
- **Without:** curves along the axis whose number of values is in 4–7 and closest to 5. When no axis has 4–7
  values, the one closest to 5; a tie goes to the earlier in `vary`. Pages along every other axis that takes
  several values.

The choice is written into the document as the set's `pages` and `curves`, so the file says what it draws,
and a later run keeps it.

**Which sets are drawn.** By default, every set. `[run] plot` (or a configuration's own `plot`) chooses
after a run:
- `true` draws every set;
- `false` draws none (the document is still written, for `heimdall plot` later);
- a list draws those sets, `plot = ["totality", "pdf_by_generator"]`. It is written into the document as
  `[plot].draw`, which `heimdall plot` draws by default.

So sets are defined once for the file, and each configuration draws those that fit it.
`heimdall plot … --sets a,b` draws others for one drawing; `heimdall run … --no-plot` draws nothing for one
run. A name no set has is refused.

**Named sets**, `[plot.sets.<name>]`, are the form to pick from. Each is a set table, or selectors, named by
its key; the list form (`[[plot.sets]]`, `sets = [...]`) is named as below and works the same. The full form
names a set's page axes and its curves, each a filter of quantities whose values combine as an outer product:

```toml
[[plot.sets]]                       # a run sweeping generator × energies × events × pdf
name   = "beams"                    # its folder: plots/beams/<backend>/<cell>/<object>
pages  = { generator = "all", energies = ["10x20", "15x60"] }   # py8_10x20, py8_15x60, sh3_10x20, sh3_15x60
curves = { events = ["10M", "100M", "100k"], pdf = "all" }      # on each: every count × every pdf

[[plot.sets]]
name   = "pdf_picks"
pages  = { events = "all" }          # a page per event count
curves = [                           # a list: the union, in order (6 curves, not 2 × 5)
  { generator = "py8", pdf = ["pdf1", "pdf2", "pdf5"] },
  { generator = "sh3", pdf = ["pdf1", "pdf3", "pdf4"] },
]
reference = { generator = "py8", pdf = "pdf1" }   # moved first: the ratio's reference on a page without data
look      = { colour = "pdf", line = "generator" } # the colour follows the pdf, the line the generator
objects   = ["d0[1-4]-*"]                          # and any [plot] page key, for this set's pages alone
ratio     = true
```

- **A filter** is `{ quantity = what }`. Its quantities are any swept or fixed ones, `events` and
  `threads` included when they are quantities (04 §8.3). What it takes for each:
  - `"all"`;
  - a tag, a glob of tags (`"NNPDF*"`), or a list of those;
  - `"!tag"` to leave a value out: a list of only these is every other value;
  - a number, for a quantity of numbers (`events = 10_000_000`).

  One table is every combination of its quantities' values; a point matches when each matches. A list of
  tables is the union of their products, in order. A combination no point has is simply absent.
- **The pages:** a page cell per combination of the `pages` quantities among the set's points, in the
  order the values are written (`"all"`: the quantity's order). Each is named by its tags joined with
  `_`, as `plot_points` cells are, and `{cell}` gives their labels. With no `pages`, there is one cell
  (`<set>/<object>`), unless an axis the set does not name pages (below). `pages = "none"` (or `[]`, `{}`)
  says no axis pages at all: one page per object, every curve the set chooses on it, even across
  generators:

  ```toml
  [plot.sets.all_few]
  pages  = "none"
  curves = [{ generator = "py8", pdf = ["NNPDF23nlo", "PDF4LHC21"] },
            { generator = "sh3", pdf = ["MSTW08lo", "NNPDF23lo"] }]   # 4 curves, one page an object
  ```
- **The curves:** each `curves` table in turn, its values in the order written (the first quantity
  outermost), then point order. A point two tables match is drawn once. With no `curves`, every point of
  the cell is drawn, and its other quantities are the curve axes. A curve is labelled by the curve axes
  that differ on its page.
- **An axis the set does not name:** a swept quantity named in neither `pages` nor `curves`, which takes
  several values among the set's points, pages too (a page per value). The plot stage says so: curves
  never quietly mix what the set did not ask for. Name it, with one value or `"all"`, to choose; with
  `pages = "none"` it joins the curves instead (and their labels name it).
- **The look:** `look`'s colour quantity takes the style's palette and its line quantity solid, dashed,
  dotted and dashdot (at most 4 values). A value keeps its colour or line on every page of the set.
  With no `look`, if the curves vary along exactly two quantities and one has at most 4 values, that one
  takes the line and the other the colour. `look = "palette"` turns this off; a quantity's own `styles`
  fill what `look` leaves unset. The style's palette has 5 colours: a colour quantity of more values
  repeats them, and when two curves of a page then look alike the stage says so. Give them colours of
  their own (below), or the set a longer palette, `style = { curves = { palette = ["#rrggbb", …] } }`.
- **A value's own look:** in a `curves` table, a value may be a table that gives the curves this table
  draws with it their look, over the set's `look`:

  ```toml
  curves = [
    { generator = "py8", pdf = [{ tag = "NNPDF23lo", colour = "#d62728", line = "dashed" }, "MSTW08lo"] },
    { generator = "sh3", pdf = { all = true, colours = ["#1f77b4", "#2ca02c", "#9467bd", "#8c564b", "#e377c2"] } },
  ]
  ```

  `{ tag = "…", colour, line, width }` is one value (`value = <number>` in place of the tag), and the tag
  may be a glob. `{ tags = "all" | [...] | "<glob>", colours = [...], lines = [...], widths = [...] }`
  is several values with a look each, in their order (`all = true` is `tags = "all"`). A list of looks
  shorter than its values is refused, rather than repeating. `color` and `colors` are accepted for
  `colour` and `colours`. Colours are `"#rrggbb"`, ROOT names (`"kBlue+1"`) or numbers; lines are solid,
  dashed, dotted or dashdot. The same value in another table keeps the set's look.
- **The page keys:** a set's own (`objects`, `ratio`, `normalise`, `split`, `legend_statistic`, `title`
  with `{cell}`, `style`, …) lay over `[plot]`'s for its pages, and a figure's over the set's (the figure
  is about the object: its axes and its scales).
- **Checked at plan time:** an unknown quantity, a tag no value has (the refusal lists the tags), a
  value no point of the configuration has, a quantity in both `pages` and `curves`, a `look` quantity
  that is not a curve axis, or a line quantity of more than 4 values. A record half-run draws the
  complete points it has.
- **Before drawing:** `heimdall plot CONFIG|RECORD --plan` prints each set's cells and their curves'
  labels, and what it would say, without drawing. Write a set against the real points this way.

**The short forms** pick points without axes, in the order named:

```toml
[plot]
sets  = [[1, 4, 6, 8], [1, 2, 4, 9], "all"]   # a page folder each: set1/, set2/, all/
split = 8                                     # at most 8 points a page: all-1/, all-2/, all-3/ of 24
```

- **A short set** is a list of selectors (`set<k>`, its place), one selector (its folder: `"pdf=X"` →
  `pdf-X`), or `{ name = "lo", points = [...] }`. A selector is a 1-based index (as `point i/n`
  counts), a point's name, a glob of names (`"sh3_NNPDF40*"`), a tag of any quantity's (`"py8"`:
  every point with it), `"quantity=tag"`, or `"all"`. Its curves are in the order named: the first is a
  ratio's reference when the page has no data. A table's `points` takes the same selectors, as a filter
  before its `pages` and `curves`.
- **`split = N`** cuts each cell (a `plot_points` cell, a set, or a set's cell) into pages of at most N
  points, in order: `<cell>-1`, `<cell>-2`, … (`part1`, … with one cell). 24 points and `split = 3` are
  8 pages.
- **The labels:** a short set's or a cut's curves are labelled by the quantities that differ on it;
  `{cell}` is the set's name.
- **Where:** `[plot]` for every page; a defined or overlay figure may set its own. merged, scan and
  compare figures page by `plot_points` only. A selector no point matches is refused at plan time.
- **On the command line:** `heimdall plot … --points 1,4,6,8` (one set, `points/`), or
  `--set 'plot.sets=[[1,4],"all"]'`. Sets may also live in a file of their own, `heimdall plot … --plot
  FILE`. With a record (`heimdall plot <P>/<run>/<NN_cfg>`) none of this touches the configs. A set's name is
  its folder, so it may not be `root`, `mpl`, `yoda` or `statistics`. Drawing a set replaces `plots/<set>/`
  and `statistics/<set>/`; the folders of sets no longer drawn stay until you remove them.

### 3.2 Statistics of the pages

Every page's curves get numbers, computed by Paint on the page (after voiding, the data's alignment and
normalisation, over the x range auto-range and the gutters give: `x_range` and `y_range` only show,
and narrow nothing), so every backend's page agrees with them. Each set's go into
`results/…/statistics/<set>/statistics.csv`, beside `plots/<set>/` and never in it, a row per page and curve.
They are made two ways:

- **With each drawing:** a set's pages give `statistics/<set>/`. `[plot] statistics = false` stops it,
  `[run] stats = false` (or `--no-stats`) for a run's follow-up.
- **Alone:** `heimdall stats <P>/<name>/<cfg>` (a folder with a `plot.toml`, `<P>/<name>` for each of its
  runs, or a run TOML for its configurations' newest) measures a run without drawing a page: the same page
  documents, read by Paint with `--ranges-only`, in a fraction of the time. `--sets a,b` measures those sets.
  A run with `[run] plot = false` and `stats = true` does this after its points.

**`[stats]`** (in the run TOML, kept in the plot document) measures otherwise than the pages draw. What it
leaves unset is the pages' own:

```toml
[stats]
sets      = ["totality"]                           # the sets measured (default: [plot].draw, else every set)
objects   = ["d01-*", "d02-*"]                     # the objects measured
normalise = "area"                                 # compare shapes, whatever the pages draw
reference = { generator = "py8", pdf = "NNPDF23lo" }   # against this curve, data or not ("data": the default; "curves": each page's first)
```

With a `[stats]` table, or `[run] stats = [sets]`, the numbers come from a pass of their own over the pages'
documents (in the working folder's `stats/`), even after a drawing, so `statistics/<set>/` always holds the
same kind of numbers, whoever made them. The columns:

| Column | Holds |
|---|---|
| `page`, `cell`, `object`, `curve`, `point` | which page (its name in the set), the curve's label and its point |
| `reference`, `is_reference` | what it is compared with: the data, else the page's first curve |
| `bins`, `area`, `area_err` | its finite bins in the range, Σ y·Δx and its error (σ in pb; 1 when normalised) |
| `ref_area`, `cmp_area` | on the reference's bins the curve covers exactly (the *compared bins*, the curve's own bins summed onto them): the reference's area there and the curve's |
| `abs_area`, `rel_abs_area` | Σ \|y − y_ref\|·Δx on those bins, and over `ref_area`: the area between the two, a fraction of the reference's; shape and normalisation both count, nothing cancels |
| `area_ratio` | `cmp_area` / `ref_area`: MC over data, the normalisation (1: the same; bins above and below cancel) |
| `ratio_mean` | Σ (y/y_ref)·Δx / Σ Δx on those bins with y_ref ≠ 0: the ratio pad's mean height (Δx in log10 x on a log-x page, as the pad draws it). Every x counts alike, the tails as much as the peak, where `area_ratio` weighs each bin by y_ref |
| `ratio_dev` | Σ \|y/y_ref − 1\|·Δx / Σ Δx on the same bins: the ratio pad's area about its line at one, over the width compared. 0.1: 10% off on average across x. Beside `ratio_mean`: \|ratio_mean − 1\| ≈ `ratio_dev` when the curve is off one way throughout (normalisation), smaller when it crosses the reference (shape) |
| `chi2`, `ndf`, `chi2_ndf` | Σ (y − y_ref)² / (σ² + σ_ref²) over those bins with an error, their number, the ratio |

**As bar graphs:** beside the table, `statistics/<set>/bars/<cell>/<object>.<fmt>` draws each page's curves
as bars, one panel each for χ²/ndf, |Δ|/reference, area/reference, the mean ratio, mean |ratio − 1| and the area
(matplotlib; the formats of `[plot]` that it writes: png, pdf, svg). Each is an A4 portrait page, its six panels
in the grid that gives each bar the most height (2 × 3, 3 × 2 or 6 × 1); more curves than a page holds continue
on further pages (one PDF, `<object>_NN.png`). A bar runs left of 0 for a negative value (a mean ratio can be),
and one 20 times the others' median or more (a curve gone wild) is cut at the panel's end, its value written
beside it after » (or before « on the left), so the others keep their scale; the rankings (from 1, for a ratio)
and `summary.html` do the same. **Colours**, above the base and below it: blue and orange as drawn; violet and
golden yellow when cut (too big); pink and red when absurd (a million times the median or more, or infinite).
A page or a ranking with a cut bar says so in a line.
`statistics = false` turns them and the summary off.

**The summary:** `statistics/<set>/summary.pdf`, every page A4 portrait (and `summary/summary_<NN>.png`, a
page each), headed by the run's folder, the set and the section, and numbered ("page 3 of 21"). Its **front
pages** say what it holds (its points, page cells, objects and pages; what they are compared against), list its
contents with the page each part starts on, and write every note once, numbered: what each number is, its
formula, the compared bins, the scoring. Each later page's footnote is one line, the numbers of the notes it
needs. Then the **standings**, what is best on the most pages (as a mode is), where the means further on say
what is best on average:
- **Scoring:** each page ranks its own curves in each of χ²/ndf, |Δ|/reference, area/reference, the mean ratio
  and mean |ratio − 1| (the two ratios by how far from 1 either way, |log10 r|). 1st scores 5 points, 2nd 4,
  3rd 3, 4th 2, 5th 1, the rest nothing; equal numbers share the better place. Only pages compared against
  data count, when any page has data (a page compared against its first curve cannot rank that curve).
- **Head to head:** on every page counted, in each statistic, each pair of its curves plays a match: the one
  closer to agreement wins it, equal numbers draw (half each). A point's **win rate** is the share of its
  matches it won (75%: it beats the others 3 times in 4). Unlike points, which stop at 5th, it counts every
  place, and it doesn't depend on how many curves a page has.
- **The top five:** a small table per scoreboard (all five statistics together, then each), its first five
  with their points and wins (1st places), and one of the first five by win rate with their matches; `=2nd`:
  sharing that place.
- **Scoreboards:** all five statistics page by page (a row per point, a column per object's page, its points
  there, at most 25), the same by page cell (a row per point placed within its cell, a column per statistic),
  then one a statistic, page by page. Each ends with the total, the wins, the win rate (over that board's
  statistics) and the mean rank (the mean of its places), is sorted by total, then wins, then mean rank, and
  has its top three in bold. Points of different page cells never meet on a page. The board by page cell
  groups its rows under each cell's band, each row its place and its curve.
- **Each page cell's head to head:** a row per point, sorted by win rate, a column per opponent: the matches
  it won against that one of those they played (`31/40`), blue where it won most, orange where it lost most.
  The cell is named in the table's title, so its rows name the curves alone.

Then a section for each of χ²/ndf, |Δ|/reference, area/reference, the mean ratio, mean |ratio − 1| and the
area:
- **a ranking:** each point's mean over the pages it was compared on, as bars, lowest first; the number of
  pages in brackets. The two ratios take the geometric mean (2 and 0.5 average to 1), rank closest to 1
  first, and their bars grow from 1, blue above and orange below. The area has no ranking: each object has
  its own units, so a mean across objects says nothing.
- **page cells against curves** (but the area's): each point's mean, as its ranking's, its page cell one way
  and its curve the other, the longer list down the rows (19 PDFs × the four QED shower and lepton PDF
  settings; the PDFs × py8 and sh3), with a mean column and a mean row and each row's best in bold; `–` where
  a cell has no such curve. Left out with one page cell, or when no curve is in two cells.
- **a table:** a row per point, a column per object (d2 before d10), each cell that point's number on that
  object's page, then the row's mean (geometric for the ratios). The reference curve's cell
says `ref` (it is compared with nothing; the area table shows its area), a missing number `–`. Cells are
shaded by value: χ²/ndf on a log scale, the area within each column (each object has its own units), the
area ratio and the mean ratio blue above 1 and orange below. With two page cells or more, a band names each
cell above its rows, and a row names its curve alone (one cell: its label as it is).

**On the page** (`framework/plot/figures/paper.py`): each section starts a page, and its tables and rankings
follow one below another (so the head-to-head tables of many small cells share pages). A table wider than the
page is cut into column blocks, the fewest that fit, its columns split evenly and stacked under one another on
the same page, each block with the row labels and the last with the mean or the totals. A long table or
ranking continues on the next page, titled "(continued)". A long label wraps, at its " · " or between words,
when that makes the table shorter overall. No page leaves fewer than three rows of a table to the next.

**As a page:** `statistics/<set>/summary.html`, beside the PDF whatever `formats` says, holds the same facts,
contents, tables, rankings and notes, without pages: each table whole, scrolling on its own with its header row
and label column kept in view. A click on a column's header sorts the table by it (again: the other way; `–`
and `ref` last), a table grouped by page cell within each cell, a mean row staying last; the label column's
header puts the order back. It is one file, with nothing to fetch, and `plots/index.html` links it from each
set's line.
Every summary page ends with a footnote: what its number is and how it is computed. A PNG or SVG is a file
a page in `statistics/<set>/summary/`, numbered in the PDF's order (`summary_01.png`, `summary_02.png`, …).

`legend_statistic = "chi2_ndf"` (or `area`, `abs_area`, `rel_abs_area`, `area_ratio`, `ratio_mean`, `ratio_dev`, `chi2`) puts one of them after
each curve's legend entry, `MSTW 2008 LO (χ²/ndf 1.31)`; the reference curve gets none. A `statistic`
figure (§7.9) draws one of them as a page per object.

### 3.3 The runs together: `[plot.across]`

Sets put one run's points on pages. To put the points of several runs of a run TOML on one page (the same
points at 10k, 100k and 10M events, or two configurations side by side), declare sets across them:

```toml
[plot.across.events_by_pdf]          # each run's points, by their event count
pages  = { generator = "all", pdf = ["NNPDF23lo", "MSTW08lo90cl"] }
curves = { "@events" = "all" }       # a curve per run's event count: 10k, 100k, 10M

[plot.across.pdf_by_events]
pages  = { generator = "all", "@events" = "all" }
curves = { pdf = "all" }
```

- **The members** are every run's points (each run's plot document's), named `<run>__<point>`, with their
  quantities matched by tag across the runs, and three attributes:
  - `@events`: the run's event count, tags like `10M`, labels `10M events`; it is an axis, so a set that does
    not name it gets a page per event count;
  - `@run`: the run's folder (`04_generator_pdf`);
  - `@configuration`: its configuration.

  The last two are not paged by themselves; name them to use them.
- **Where:** `results/<P>/<name>/plot.toml`, written by a run of the run TOML when it has none, holds
  `[from]` and the run TOML's `[plot]` with these sets. The pages go to `results/<P>/<name>/plots/<set>/`, their
  numbers to `statistics/<set>/`.
- **`[from]`:** `runs = ["04_*", "0[5-7]_*"]` names the runs, by folder globs (every run by default).
  `prefer = "last"` (the default) draws a point two runs have (every tag and the event count the same) from
  the later one that completed it, and says so; `"all"` keeps both.
- **Drawn by** `heimdall plot <config> --across` (or `heimdall plot results/<P>/<name>`), measured by
  `heimdall stats <config> --across`. `--style-sync <config>` with `--across` takes the config's `[plot]` and
  `[plot.across]` into it. A compare figure (§7.5) still draws configurations side by side from one run's
  plot stage; `@configuration` here is the same over any runs.

---

## 4. Reference data and ratios

```toml
[plot]
ratio = true                              # MC/Data in a ratio pad

[plot.data]
file   = "rivet:ZEUS_2012_I1116258"       # Rivet's own reference data; a bare name is under datasets/
legend = "ZEUS 2012"

[plot.data.map]                           # explicit: never matched by name
"d01-x01-y01" = "/REF/ZEUS_2012_I1116258/d01-x01-y01"
"d09-x01-y01" = "/REF/ZEUS_2012_I1116258/d09-x01-y01"
```

- **Where the data are drawn:** only on the pages the map names, **aligned** to the MC's bins. They
  are cut to their longest run of bins whose edges line up, or dropped with a warning.
- **Why the map is explicit:** ZEUS's `d08` and `photo_eic`'s `d08` are different observables, so
  the map is never inferred.
- **The ratio pad:** each curve over the data.
- **Without data, or with `use_data = false`** (the table stays but is not drawn), each curve is
  divided by the page's first curve: the first value of its curve axis.

→ `jets`, `validation`.

---

## 5. Curves: labels, looks and bands

A curve is labelled by its points' `label`s, and drawn in the next colour of the style's palette. A
quantity can give each of its points a look of its own, its row's `style`, which it keeps on every
page:

```toml
[[quantities.pdf.points]]          # a row as a table of its own: the same as points = [{ … }, …]
tag   = "MSTW08lo"
value = "LHAPDF6:MSTW2008lo68cl"
label = "MSTW 2008 LO"
style = { colour = "#EE3311" }

[[quantities.pdf.points]]
tag   = "NNPDF23lo"
value = "LHAPDF6:NNPDF23_lo_as_0130_qed"
label = "NNPDF 2.3 LO"
style = { colour = "kBlue+1", line = "dashed", width = 1.5 }
```

A row's `style` belongs to the run (its plot document keeps it with the quantity), so a run made before the
style was written does not have it. **`[plot.looks]`** gives values their looks in `[plot]` instead, by tag,
so `--style-sync` carries them into every run, and a value commented out of the quantity keeps its look:

```toml
[plot.looks.pdf]                      # each PDF the same colour on every page, in every run
NNPDF23lo    = "#0067A5"
MSTW08lo90cl = "#F99379"
HERAPDF20JetsNLOEig = { colour = "#008856", line = "dashed" }
```

A look is a colour or `{ colour, line, width }`, over the quantity's own `style`. A set's `look` and a curves
filter's styled values go over it, and a set's automatic look leaves an axis with looks alone.

**A band** folds a curve axis into an envelope:

```toml
[plot]
band = ["scale"]          # per value of the other curve axes, one curve (the scale's first value),
                          # with the min–max of all its values shaded around it: the usual scale band
```

The legend entry ends `(scale envelope)`. A band must be a curve axis of the configuration: varied,
not `plot_points`, and not combined. Every backend draws it.

---

## 6. The style

Every ROOT page starts from `src/Apps/Paint/base.toml`, which gives it rivet-mkhtml's look:
- serif text;
- ticks inside, on all four sides;
- steps with error bars at the bin centres;
- black data points;
- a frameless legend;
- a ratio pad a third of the height.

Edit base.toml to change every page. Over it, key by key:

1. the machine root's `style.toml` (`~/Himinbjorg/style.toml`): every study's on this machine;
2. the work dir's `style.toml`: its studies';
3. `[plot].root_style`: a style file of the run, under `configs/<P>/`;
4. `[plot.style]`, inline;
5. a figure's `style`, for its pages.

Each layer names **only what it changes**, in base.toml's tables (the labels' LaTeX → TLatex table,
`framework/schema/latex.toml`, takes a work dir's `latex.toml` over it too: its own macros):

```toml
# configs/Demo/talk.toml       (root_style = "talk")
[page]
dpi = 300                 # PNG resolution; the PDF stays vector
[text]
title  = 12.0             # points
legend = 9.0
[legend]
position = "top-left"     # a corner, "best", or [x, y]: its top-right corner, in fractions of the frame
[curves]
errors = "band"
```

**Outside the frame, and apart from the ratio pad:**

```toml
[plot.style]
legend = { position = "out-right" }     # out-right | out-left: a column beside the frame
                                        # out-top | out-bottom: as many columns as fit its width
ratio  = { gap = 6.0 }                  # points between the main frame and the ratio's (0: joined)
```

- **Where an outside legend goes:** `out-right` right of the frame, `out-left` left of the y axis's
  labels and title, `out-top` between the titles and the frame, `out-bottom` under the x axis's title
  (under the ratio pad, when there is one). `legend.inset` is its distance from what it sits beside.
- **Who makes room:** Paint (`root`) keeps the page's size and shrinks the frame, guessing the labels'
  widths; `mpl` keeps the frame and grows the page to hold the legend. A long legend beside the frame
  takes much of a small page: a wider `page.size` gives it room.
- **mkhtml** (`yoda`) cannot draw either: they are refused for it, and drawn by `root` and `mpl`.

- **Misspelt keys:** an unknown key, or a value of another kind, is refused at plan time, with the
  nearest spelling.
- **Seeing the merged style:** `$HEIMDALL_APPS/Paint.exe <page>.toml --dump-style` prints a page's whole
  style; the page documents are in `.cache/<P>/plots/<name>/<cfg>/<set>/`.
- **The reference:** every key and its default is [04 §12](04_Config_Reference.md#12-the-style).
- **Ratio ticks:** denser or sparser ratio-pad ticks are `ratio = { divisions = 508 }` (0.2 apart)
  or `515`.

---

## 7. Figures

### 7.1 Declaring a figure

```toml
[plot.figures.tails]          # the figure's key
class   = "defined"           # how its pages are built (the default)
type    = "Hist1D"            # what is drawn; left out, from the objects
# name  = "…"                 # its pages' file stem, default the key (an overlay's page, a merged figure's folder)
objects = ["d04-*"]           # globs: the short name, the option-free path, or a variant's path
# any [plot] page key, x_label, y_label, and style.<…>: for these pages only
```

**What a figure inherits.** A figure takes **every page key of `[plot]`**:
- the titles and `legend_header`;
- `logx`, `logy`, `logz`;
- the gutters and `x_range`, `y_range` (but a heat map and a statistic figure take these from
  their own figure alone);
- `ratio`, `normalise`, `auto_range`, `range_pad`, `void_empty`, `min_entries`;
- `use_data`, `band`.

It also takes `x_label`, `y_label` and `style`. Each means what it means in `[plot]`, for the
figure's pages only; left out, or `"default"`, it is `[plot]`'s, and `"native"` is the drawing tool's own. What concerns the whole run stays
in `[plot]` alone: `backend`, `formats`, `objects`, `data`, `root_style`.

**When it is checked.** A figure is checked twice:
- **when the file is read:** its class's keys, and the keys it may not take;
- **at plan time:** the axes it names, and the configurations it compares.

A glob that matches no object of the points is refused at the plot stage. The old
`[plot.overlay.<name>]` and `[plot.object."<glob>"]` tables are refused with the figure to write,
and `heimdall migrate` rewrites them.

| Class | Built from | Pages |
|---|---|---|
| `defined` | an analysis object | `<cell>/<object>` |
| `overlay` | several objects of each point | `<cell>/<name>` |
| `merged` | the points merged over an axis, for this figure only | `<cell>/<name>/<object>` |
| `compare` | the same objects across configurations, of this or other run TOMLs | `<run>/compare/<name>/<cell>/<object>` |
| `derived` | a new object per point: a ratio, difference, sum or projection | `<cell>/<name>` |
| `scan` | one number per point against a swept quantity | `<cell>/<name>` |
| `sheet` | drawn pages, tiled in a grid | `plots/<set>/<backend>/sheets/<name>` |
| `statistic` | one statistic per point, of each drawn page | `statistics/<set>/figures/<backend>/<cell>/<name>/<object>` |

### 7.2 `defined`: an object's own pages

```toml
[plot.figures.tails]
objects  = ["d04-*"]
logy     = true
y_gutter = 2.0
style.legend.position = "bottom-left"
```

The objects' own pages, with this figure's keys. A defined figure **takes over** the pages of the
objects it matches, also those `[plot].objects` leaves out. Two declared defined figures that match
the same object are refused: there is one recipe per page, so narrow a glob, and put what every page
shares in `[plot]`. A defined figure takes no `labels` or `name`: its pages are the objects' own.

### 7.3 `overlay`: several objects on one page

```toml
[plot.figures.eta_algorithms]
class   = "overlay"
objects = ["d02-x01-y01", "d11-x01-y01", "d12-x01-y01"]
labels  = ["$k_{T}$", "anti-$k_{T}$", "SISCone"]
style.ratio.range = [0.8, 1.1]
```

One page per cell, `<cell>/eta_algorithms`, with a curve per object and point:
- **labels:** each curve is labelled by `labels` (default: the objects' names), followed by the
  point's own label when the page has several points;
- **the ratio:** it divides by the first curve;
- **a band:** it folds the points into each object's envelope.

The page's titles are the first object's. Objects must be 1D.

### 7.4 `merged`: points merged for this figure

```toml
[plot.figures.avg]
class   = "merged"
objects = ["d01-*", "d05-*"]
over    = ["replica"]            # curve axes merged away
title   = "five seeds merged"
```

The objects' pages, under the figure's folder (`<cell>/avg/<object>`). For each value of the other
curve axes, the points' YODAs are merged by the combine folder's command (`rivet-merge -e`:
statistics add, σ averaged), into `.cache/…/merged/avg/`, merged again only when a member's YODA changes.

The run keeps its points apart, and only this figure merges them; `combine` merges them for the
whole configuration ([02 §7.3](02_User_Guide.md#73-replicas-merged)). `over` must name curve axes,
and the figure may not also `band` them.

### 7.5 `compare`: configurations side by side

```toml
[plot.figures.statistics]
class          = "compare"
objects        = ["d0*"]
configurations = ["default01", "default1", "default4"]   # default: the sweep_runs ones
labels         = ["1M", "10M", "40M"]                    # default: each configuration's folder name

[plot.figures.chains]
class          = "compare"
objects        = ["d01-*"]
configurations = ["default", "Demo/inproc_validation:default"]   # another run TOML's
```

**The pages.** These are the objects' pages across configurations, in this run's
`compare/<name>/<cell>/<object>`, a folder per backend. Each curve is a configuration and a point (or
a combined group), labelled by the configuration first, then the point's curve axes.

**What it needs.**
- **Configurations:** two or more, and at least one of this file. They must have the same page and
  curve axes, which is checked at plan time.
- **Another run TOML:** `"<Project>/<config>:<cfg>"` names a configuration of it. Its points are
  read as its last run left them, labelled `<its run> <its label>` by default, and by its own
  quantities. Its page axes must have this run's tags.

**When it is drawn.** It is drawn by the plot stage of each of this file's configurations it names,
once every configuration has complete points; until then the stage says what it waits for.
`heimdall plot` draws it too.

### 7.6 `derived`: a new object per point

```toml
[plot.figures.r15]
class   = "derived"
op      = "ratio"                         # ratio, difference, sum (two objects); projection-x, -y (one 2D)
objects = ["d01-x01-y01", "d05-x01-y01"]
y_label = "d01 / d05"
ratio   = false
```

**The new object.** It is `/FIGURES/<name>` in every point, and `/FIGURES:R=0.4/<name>` per
analysis-option variant.
- **The ops:**
  - `ratio`, `difference` and `sum` of its two objects (histograms made estimates first), on the
    same binning, else refused naming both;
  - `projection-x` and `projection-y` of one 2D object: summed over the other axis, as a Scatter2D
    whose x ranges are the bins.
- **Where it is written:** it is appended to a copy of each point's YODA
  (`.cache/…/derived/`), remade when the product or
  the figures change, by
  `framework/plot/figures/derive.py` with YODA's Python (`gjallarhorn`).

**Using it.** It is then an object like any other:
- its pages are `<cell>/r15`;
- its labels are its first object's `.plot` ones (set `y_label`);
- an overlay, merged or compare figure may name it (`"r15"`).

### 7.7 `scan`: one number per point

```toml
[plot.figures.sigma_vs_pt0]
class = "scan"
x     = "pt0ref"                  # a curve axis whose values are numbers
y     = "sigma"                   # sigma, entries, integral, mean, bin:N
# objects = ["d01-x01-y01"]       # integral, mean, bin:N read one object; entries may name one
```

**What it reads.** One number per point, against `x`:
- `sigma`: the point's `/_XSEC`;
- `entries`: its events, or its object's raw entries;
- `integral`, `mean` and `bin:N`: of its one object.

**The pages.** A page per cell, `<cell>/<name>`, with a curve per value of the other curve axes. Each
curve is a Scatter2D: a point per `x` value, with an x range halfway to its neighbours, centred on
it. So every backend can draw it as a bin; it is drawn as markers. The axis titles are the
quantity's name and the number read, until you set `x_label` and `y_label`.

**The limits.** `x` cannot be a page axis, nor banded. A quantity of names (PDF sets) cannot be an
`x` yet.

### 7.8 `sheet`: drawn pages in a grid

```toml
[plot.figures.paper_fig3]
class   = "sheet"
pages   = ["18x275/d02-x01-y01", "18x275/eta_algorithms", "*/r15"]   # globs of page names, in order
columns = 3                                                         # default: up to 3
```

- **What it makes:** after the configuration's pages are drawn, in each set the pages the globs name (by
  their names in the set) are tiled `columns` wide into `plots/<set>/<backend>/sheets/<name>.pdf` and
  `.png`; a set none of the globs names is passed over. Each pad is its page exactly
  as it was drawn alone:
  - pdflatex places the PDFs, as vectors (a page's PNG where it has no PDF), in cells of the
    largest page's size;
  - the `.png` is that PDF rendered by pdftoppm, so no page needs a PNG of its own; when
    every page has one, the sheet's PNG is as many of their pixels wide and high.
- **Which backends:** Paint's and mpl's pages.
- **What it takes:** a sheet takes no page keys; its pages' figures set those.
- **When it fails:** a glob that names no page fails the sheet.
- **Its limits:** it has no shared y title or legend, and it does not take compare figures' pages.

### 7.9 `statistic`: the points ranked

```toml
[plot.figures.rank]
class     = "statistic"
statistic = "chi2_ndf"            # area, abs_area, rel_abs_area, area_ratio, ratio_mean, ratio_dev, chi2, chi2_ndf (§3.2)
objects   = ["d01-*", "d02-*"]
sort      = true                  # the smallest first; default: the curves' order
```

- **The pages:** per cell (or set) and object its globs match among the drawn pages, a page
  `<cell>/rank/<object>`: the page's curves as bins 1, 2, …, each labelled under the axis by its curve's
  label, y its statistic against the page's reference, drawn as markers (`area` with its error). The
  reference curve of a page without data is left out.
- **When:** after the configuration's pages are drawn, from the numbers just computed; its own pages
  add nothing to `statistics.csv`. The object's title stays; set `y_label`, `logy` or any page key on it.
- **Backends:** Paint writes the points' names under the axis (`x_labels`); mpl draws the bins by number.

---

## 8. Types: Hist1D, Scatter2D, HeatMap

| `type` | Drawn as | Default for |
|---|---|---|
| `Hist1D` | steps per curve, error bars at the bin centres (or a band, or none: `curves.errors`) | a 1D object |
| `Scatter2D` | a marker per bin at its centre with its error bar, in the curve's colour (`data.marker`, `data.marker_size`), as Paint draws data; the legend shows the marker | a scan |
| `HeatMap` | one 2D object coloured by value, its scale on the right (`z_label`, `logz`: from the `.plot`'s `ZLabel` and `LogZ`) | a 2D object (`Histo2D`, `Estimate2D`) |

**Scatter2D on other backends.** For a Scatter2D page, the page document says `markers = true`, and
mkhtml and mpl draw its curves as they draw points (`ConnectBins=0`, with their x bars).

**HeatMap pages.** A heat map is drawn per point of the cell, as `<cell>/<object>/<point>`. It has
no ratio, data, voiding or calculated range. Its `x_range` and `y_range` are its own figure's alone
(`[plot]`'s and a set's are the 1D pages', whose y is not the heat map's), kept within the histogram,
and each end widens to the edge of the bin that holds it; a range that misses the histogram fails
that page (exit 1). **Paint alone draws heat maps**: mkhtml and mpl draw the 1D pages,
and the plot stage says so.

**What is refused:** a 1D object as a HeatMap, a 2D object as a Hist1D or Scatter2D, and a 2D object
in an overlay. To see a 2D object in 1D, project it with a derived figure.

---

## 9. Backends

| `backend =` | Draws with | Pages in | Honours |
|---|---|---|---|
| `"root"` (default) | `$HEIMDALL_APPS/Paint.exe`, up to 200 pages per process | `plots/<set>/root/` | every `[plot]` key, every figure and type, the whole style |
| `"mpl"` | matplotlib in this process, a pool of workers (`framework/plot/mpl/backend.py`) | `plots/<set>/mpl/` + `index.html` | **mkhtml's pages, pixel for pixel** (until the user has verified it), about 18× faster than mkhtml; 1D pages only |
| `"yoda"` | `rivet-mkhtml`, one call per page set (`framework/plot/yoda/backend.py`) | `plots/<set>/yoda/[<cell>/]<analysis>/<object>.{pdf,png}` + `index.html` | deprecated |
| `["root", "mpl"]`, `"both"` | each, from the same page documents | each tree | as each; `"both"` is root and yoda |

**Overflow marks.** A numeric end of `y_range` holds in Paint and mpl even when a curve passes it:
the curve is clipped at the frame, and each bin past the end gets a thinner line in the curve's colour
and line style, 2 px beyond that frame edge, over the part of the bin within x. Where the page has
less room beyond the edge than the mark needs (a ratio pad joined to the frame, `ratio.gap = 0`, the
default), the lower marks are drawn 2 px inside the frame's bottom edge instead. Curves past the same
end in the same bin divide its width, the nearest the end first; the split is per shared bin, so
curves of different binnings mark their own bins and may overlap. Only the curves are marked: data
off the scale get no mark, and neither does a value ≤ 0 on a log axis (an empty bin). The mpl marks
are an intentional exception to pixel-for-pixel mkhtml matching; the deprecated yoda backend draws
none.

**What the other backends honour.** They draw the same page documents with the ranges and voided
bins Paint computed, so every backend shows the same window. They keep mkhtml's look, so only these
carry over:
- a `legend.position` corner (or `best`); `mpl` also takes the four outside ones and `ratio.gap`;
- `text.legend`;
- `text.header`;
- `ratio.divisions`;
- `ratio.range` with `ratio.limits`.

**What is refused.** Alone, they refuse `root_style` and every other style key. Beside the root
backend those are Paint's to honour, and are allowed. A legend at `[x, y]` is still refused, because
the two page sets would disagree about it.

**How the yoda backend draws.** It writes per page set:
- copies of the point YODAs, with the voided bins blanked;
- `reference.yoda`: the mapped reference objects cut to their aligned span, renamed
  `/REF/<analysis>/<object>` (mkhtml's own reference lookup is off: explicit only);
- `pages.plot`, which per object holds:
  - `XMin`/`XMax`/`YMin`/`YMax` (left out where a `"native"` gutter leaves the range to the
    tool);
  - `LogX`, `LogY`, `RatioPlot`;
  - the legend corner;
  - label overrides.

It then runs `rivet-mkhtml --no-rivet-refs -o <dir> -c pages.plot <yodas…> [reference.yoda
--reflabel …]`, with `-f SVG`/`-f EPS` for those formats. Last, it writes `ratio.divisions`' locators
into each page's script just before it saves, and runs the script again: YODA's generator has no key
for the ratio pad's ticks.

**How the mpl backend draws.** It draws the pages mkhtml would, without mkhtml:
- rivet's `get_plot_configs` reads the `.plot` files and the yoda backend's block for the page;
- the yoda backend's transforms (void, normalise, envelope, the cut reference) run in memory;
- YODA's own helpers give every number, with its `default.mplstyle`;
- mkhtml's generated script's calls are made directly, with the yoda backend's fixes applied before
  saving.

`tests/integration/test_plot_stage.py` checks every page and overlay PNG against mkhtml's, pixel for
pixel.

Writing a backend is [06 §18](06_Internals.md#18-adding-a-plot-backend).

---

## 10. Any files, overlaid: `heimdall overlay`

```bash
heimdall overlay a.yoda b.yoda --labels "Tune A,Tune B" --ratio --objects "/MC_JETS/*"
heimdall overlay .cache/Demo/plots/jets/01_pdf/pdf.root            # a sweep: a curve per point
```

**No run TOML is needed.** You get one page per object any file holds, with one curve per file, or
one per point of a merged sweep file, labelled from its `points.json`.

**Options:**
- `-o DIR`: where the pages go (default `results/plots/<first file>/`);
- `--formats pdf,png`;
- `--style FILE`: a style file over base.toml.

The pages are Paint's, with an `index.html` beside them. The options are in
[05 §1.2](05_Commands_and_Tools.md#12-heimdall-plot-and-heimdall-overlay).

---

## 11. Reports, `heimdall report`

A **report** is a quick, informal account of runs' pages and numbers, the kind you send a colleague or a
supervisor after a run: one A4 PDF, a page to browse, and every figure it shows in its own folder. It is
made only when you ask: no run, plot or stats step makes one. (A run writes one small file for it, a folder's
`report.toml`, §11.2.)

```bash
heimdall report eic/zeus_validation/02_generator_pdf          # its report.toml: what its config asks for
heimdall report eic/zeus_validation                           # the default report of the run's configurations
heimdall report eic/weekly.toml                               # a recipe of its own, over its from
heimdall report eic/weekly.toml 'eic/zeus_validation/0[2-4]_*' # the recipe over other sources
heimdall report eic/zeus.toml eic/zeus_validation/02_generator_pdf   # the run TOML's [report], as it reads today
heimdall report eic/zeus_validation/02_generator_pdf --list   # what it would hold; nothing is written
heimdall report eic/weekly.toml --init eic/zeus_validation/02_generator_pdf   # write that recipe, once
```

A recipe is always named with its `.toml` (`<P>/<name>.toml` under `configs/`, `./…`, or a path); anything
else is a source. Each report is a folder:

| File | What it is |
|---|---|
| `report.pdf` | A4: a front page (its sources, where they came from, any flags) and the contents; then what was run, how the numbers are made (§11.4), and the results, each section from a new page |
| `report.tex` | its LaTeX, naming only files in the folder: it compiles there as it is, or on Overleaf (upload the folder) |
| `figures/` | every page it shows, copied as drawn, or drawn for the report (§11.3): `<NN>_<section>/<MMM>_<source>_<page>.pdf`, its `.png`, and its `.csv`: each curve's bins (`curve`, `label`, `xlow`, `xhigh`, `y`, `err_down`, `err_up`) as its point's YODA holds them, before the page's normalisation, and the data's, so a figure can be drawn again without reading a PDF |
| `stats/` | the numbers of the statistics it shows, which are typeset in the report itself, not pictures: `<NN>_<section>/<MM>_<source>__<set>.csv` (the `statistics.csv` they come from) and `.html` (the same tables as one page); a bar table's rows, `<NN>_<section>/<MM>_<source>/<NNN>_<page>.csv`; `summaries/`, each source's `summary.html` |
| `tools/` | what each tool was given (§11.2): `<NN>_<section>/<MM>_<source>/<tag>.baseline.<ext>`, the card's lines every point had, and `<tag>.varied.csv`, what varied point by point |
| `index.html` | the same grids to browse (2, 3 or 4 columns, ← →), the tools' cards and tables as text, its sources up front |

**A rebuild makes only what changed.** A page whose source changed is copied again (its CSV when its page
document or a YODA changed), what was drawn for the report is drawn again only when its source or its keys changed,
and `report.pdf` is remade only when something it shows changed (`.stamps.json` keeps what each file was made
from). What no section shows any more is removed.

**Where it came from, up front.** For each source: its address, its configuration, when its pages were drawn and
by which Heimdall, its points complete of all, its events, and what it is compared against (data, or each page's
first curve). It flags points that are not complete, and points newer than their pages (`heimdall plot
<source>` redraws them).

### 11.1 Where it is built, and the default report

**`reports/` mirrors `results/`.** A report is built where `results/` has its sources:

| Its sources | Its folder |
|---|---|
| one configuration's folder, `eic/zeus_validation/02_generator_pdf` | `reports/eic/zeus_validation/02_generator_pdf/` |
| a run's, `eic/zeus_validation` (each configuration's) | `reports/eic/zeus_validation/` |
| several runs' of a project | where their addresses meet: `reports/eic/` |

The folders nest as in `results/`: a run's report and its configurations' sit together, each touching only its
own files. A recipe's `output` (a folder under `reports/`, or `./…`, `/…`) or `-o DIR` builds it elsewhere,
never into `results/`; sources of two projects, or outside `results/`, need one of them. A recipe over a
folder builds into that folder's place unless it says otherwise, replacing what was built there.

**The default report**, of a folder with no `report.toml` and of several sources at once, holds a Tools section
first: what each tool was given (`[report].tools` picks them; every tool given a card or options when it is left
out, none with `tools = []`); then the statistics' headline (the top five and each statistic's ranking) on the
first set measured, then the pages of every set the sources' documents draw (`[plot].draw`, else every set of
`[plot].sets`), a grid per page cell. A set a source has not drawn is drawn for the report
(§11.3); one it cannot draw (no complete point in it, as where a generator failed) is left out, and said. A scan
of many points or cells makes many pages: `--list` says how many first, and a recipe picks fewer.

### 11.2 A recipe: of its own, a run's, a folder's

A recipe is a `[report]` table and its `[[report.section]]`s
([04 §15](04_Config_Reference.md#15-a-reports-recipe-report)): a title, a subtitle, its sources, and its
sections, each one kind of item.

```toml
# configs/eic/weekly.toml
[report]
title    = "ZEUS photoproduction: {configuration}"
subtitle = "for the group, 30 Oct 2026"
from     = ["eic/zeus_validation/02_generator_pdf"]

[[report.section]]
title = "Standings"
stats = ["top5", "ratio_dev"]

[[report.section]]
title = "Spectra"
pages = ["d01-*", "d02-*"]
note  = "Pythia 8.318 and Sherpa 3.0.5 against ZEUS 2012"

[[report.section]]
title  = "Run by run"
from   = ["eic/zeus_validation/0[2-4]_generator_pdf"]
pages  = ["d01-x01-y01"]
layout = "sources"
```

- **`pages`:** globs of a set's page names (`d01-*`, `18x275/d0*`). `layout = "pages"` shows each source's in
  turn, a grid per page cell; `layout = "sources"` puts the sources side by side, a grid per page, a panel per
  source labelled by its folder (`02_generator_pdf`, the serial kept where two would share a name) or its
  events (`label = "events"`).
- **`compare`:** a compare figure's pages (§7.5), from each source's run.
- **`stats`:** sections of the statistics summary (`top5`, `scoreboard`, `head-to-head`, `chi2_ndf`, …), or one
  part of a statistic's (`chi2_ndf:ranking`, `:crossed`, `:table`), each source's with its facts and notes.
- **`bars`:** globs of page names, each page's bar graph of its curves' numbers.
- **`files`:** your own PDF or PNG files, relative to the recipe (`extras/*.png`).
- **`tools`:** what each tool was given (below): tool tags (`[tools.<tag>]`) or globs, `"*"` every tool given a
  card or options; `hide` leaves varied lines out by their key (`"Random:seed"`).
- **`optional = true`:** a source that neither has the section's set drawn (or measured) nor can draw it is
  passed over, and the section left out when none has it.
- **`plot = { … }`:** `[plot]` keys over each source's own, for a `pages`, `stats` or `bars` section: its pages
  and numbers are then drawn for the report (§11.3).
- **`{project}`, `{run}`, `{configuration}`, `{title}`** in a title or subtitle are filled in from the sources.

The sources on the command line replace `[report].from`, so one recipe serves many runs; a section's own
`from` stays. **What is refused:** a set a source has neither drawn nor can draw (naming the sets it has), a
glob that names nothing, two side-by-side panels of one label, an unknown key (with the nearest one).

**What the tools were given.** A `tools` section reads each source's records, never today's `configs/`: each
complete point's `context.toml` names its tools, and its `cards/` hold each tool's card as it read it. For each
tool:
- **its card, alike in every point:** the lines every point had (comments too, where alike), in the card's order,
  as the card writes them (`tools/…/<tag>.baseline.cmnd`, shown with long lines broken);
- **its options alike** (Rivet's `analyses`, …): the context's keys other than the card;
- **what varied, point by point:** each point's other lines, comments left out. When they are all `key = value`
  or `key: value` lines, it is a table, a row a point labelled as its curve is, a column a key (`PDF:pSet`,
  `Random:seed`), carried on in a further table past five keys; otherwise each point's lines in turn. Both are
  in `tools/…/<tag>.varied.csv`.

A point whose record is gone (results copied without `records/`) is named, not guessed.

```toml
[[report.section]]
title = "What the generators were given"
tools = ["pythia", "sherpa"]
hide  = ["Random:seed", "RANDOM_SEED"]
```

**The run's own.** A run TOML's `[report]` says what its folders' reports show, so a report needs no
arguments after a run. Its `template` names a recipe shared by several configs, which its own keys and
sections are laid over:

```toml
# configs/eic/zeus.toml
[report]
template = "weekly"                  # configs/eic/weekly.toml: its title, subtitle and sections first
title    = "ZEUS validation: {configuration}"

[[report.section]]
title = "Jets"
pages = ["d0[3-4]-*"]
```

Each time the run writes a folder's `plot.toml` it writes `report.toml` beside it: that table resolved (the
template's, then the config's, the placeholders filled in), or the default report written out when it gives no
sections. `heimdall report <folder>` builds it. It is rewritten from the config every time, never merged with
edits: to change a folder's report, change the config or its template (then `heimdall report <config>.toml
<folder>` builds it as the config reads today), or copy `report.toml` into `configs/` as a recipe of your own.

### 11.3 Drawn for itself

A report does not need what `heimdall plot` and `heimdall stats` left on disk. It draws for itself, with the same
code, when:
- a source has not drawn a set a section shows (a run with `--no-plot`, a plot stage that failed), or drew it as
  PNG alone (the report shows vectors);
- a source has not measured the numbers a `stats` or `bars` section shows;
- a section has `plot = { … }`: any `[plot]` key over the source's own (`normalise = "area"`, a
  `legend_statistic`, a style, a set of its own, `sets = { mine = { pages = …, curves = …, objects = […] } }`).
  Its pages and numbers are always drawn for the report.

```toml
[[report.section]]
title = "Shapes"
set   = "all_few"
pages = ["d0[1-4]-*"]
plot  = { normalise = "area" }
```

What it draws goes into the report's cache, `.cache/<P>/reports/<its place>/.drawn/<source>[-<keys>]/`: the
source's plot document read with its outputs sent there (its pages and numbers in `results/`, its working files,
a failure's log in `records/logs/plot/`). Only the sets the report needs are drawn, in PDF and PNG, without the
source's compare, sheet or statistic figures. **The source is only read:** neither its `results/` folder nor its
records is written. A drawing is done again only when the source's document or points, the section's keys or the
drawing's code (Paint, the plot stage) changed. `--list` and the front page say what was drawn for the report and
why, and statistics drawn with a section's keys say "as this report measures it". Drawing needs what
`heimdall plot` needs: Paint, and the backend's own.

### 11.4 What was run, and how the numbers are made, first

A report gives its context before its results. Its **tools sections** (what each tool was given) come first, in
the recipe's order, whatever their place in it; then **How the numbers are made**, an unnumbered section in the
contents, whenever it shows statistics or bar tables:
- **How a page is compared:** a page as drawn, against its reference (its data, else its first curve), over the
  bins they share;
- **the statistics** it shows, a paragraph each: the statistic's name, its formula set out, then what it sums over
  and what it says (χ²/ndf, |Δ| / reference, area / reference, the mean ratio, mean |ratio − 1|, the area);
- **How points are scored** and **Head to head**, when it shows the standings.

Then every other section, in the recipe's order. The statistics parts no longer repeat these definitions as
notes: each keeps only the notes on reading its own tables, and its line under its title points to the page
that defines them. (Each part's HTML page in `stats/` keeps every note: it stands alone.)

```toml
[report]
context = "last"     # what was run and How the numbers are made after the results, as an appendix
method  = false      # no How the numbers are made: each statistics part keeps its own notes
```

### 11.5 Its look

Every report has one look, set once in `report.tex`'s preamble and used by everything in it:

- **Fonts:** TeX Gyre Heros (Helvetica's metrics, as the pages Paint draws) for titles, text, tables and labels,
  math set in it too; Latin Modern Typewriter for code, addresses and keys.
- **Sizes:** the title 22 pt, sections 15, a set's name 11, the body 9.5 (on 13.5), tables 8 (on 10.5), captions
  8.5, notes, panel labels and code 7.5. Bold for titles, table headers and totals, and code's keys; italic only
  for notes on what is missing and for comments in code.
- **The page:** A4, 18 mm left and right, a running header (the report's title, the section) 8 mm over the body,
  "page n of N" under it. Each section starts a page; its note is muted, in wide lines; tables have light rules
  and rows of 1.3 lines, and a table of a few rows starts on a page that holds it whole.
- **A set's sub-header**, once over a source's grids of a set: the set's name and its source, then its *Pages*
  (its page axes and their values, as labels), its *Curves* (a line a curves filter) and what is *Fixed* (each
  quantity the configuration does not vary). Each grid under it is captioned by its page cell's labels
  (`Pythia 8.318`), and a grid is placed a row of panels at a time, so pages break between rows.
- **Code:** a tool's card and options, highlighted: keys bold in the accent, `=` and `:` muted, numbers and words
  (`on`, `off`, `true`, …) coloured, comments muted italic; `index.html` the same.

`[report]` changes a little of it ([04 §15](04_Config_Reference.md#15-a-reports-recipe-report)):

```toml
[report]
font     = "serif"      # the body in TeX Gyre Termes; titles, tables and labels stay sans
size     = 10.5         # the body's pt, 8 to 12
accent   = "#0b6e4f"    # section numbers, kickers, code's keys
columns  = 3            # a grid's columns when its section names none
contents = false        # no contents on the front page
```

### 11.6 Talks and papers

A report is not a talk, a thesis or a paper, and Heimdall makes none of them. Take what it made into your own
tools: the figures as vector PDFs from `figures/` (their curves' numbers in the CSV beside each), the statistics'
numbers from `stats/`, and `report.tex` as a start for Overleaf (its preamble holds the whole look).
