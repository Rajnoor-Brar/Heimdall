---
id: settings-plot
summary: every key of [plot], [plot.figures.*], [plot.data], [plot.across_from], [stats]: type, default, accepted values, effect
for: driver client dev agent
code: framework/schema/run.toml
generated: true
---

# `[plot]` settings

Generated from `framework/schema/`; change it there. `heimdall explain <key>` says the same.

## [plot]: every page

[`backend`](#backend) · [`formats`](#formats) · [`band`](#band) · [`objects`](#objects) · [`ratio`](#ratio) · [`y_gutter`](#y_gutter) · [`x_gutter`](#x_gutter) · [`x_range`](#x_range) · [`y_range`](#y_range) · [`logy`](#logy) · [`logx`](#logx) · [`logz`](#logz) · [`auto_range`](#auto_range) · [`normalise`](#normalise) · [`void_empty`](#void_empty) · [`use_data`](#use_data) · [`min_entries`](#min_entries) · [`range_pad`](#range_pad) · [`sets`](#sets) · [`looks`](#looks) · [`across`](#across) · [`across_from`](#across_from) · [`draw`](#draw) · [`split`](#split) · [`statistics`](#statistics) · [`legend_statistic`](#legend_statistic) · [`root_style`](#root_style) · [`title`](#title) · [`title_left`](#title_left) · [`title_right`](#title_right) · [`legend_header`](#legend_header) · [`data`](#data) · [`style`](#style) · [`figures`](#figures)

### `backend`

**Type** string or list of strings · **Default** `"root"` · **Accepts** `"root"` · `"yoda"` · `"mpl"` · `"both"` · `"default"` (the layer below's value)

`"root"` (Paint), `"yoda"` (deprecated, rivet-mkhtml; frozen), `"mpl"` (matplotlib, mkhtml's pages drawn in-process), `"both"` (root and yoda) or an array of them, from the same pages

### `formats`

**Type** list of strings · **Default** `["pdf"]` · **Accepts** `"pdf"` · `"png"` · `"svg"` · `"eps"` · `"default"` (the layer below's value)

`pdf`, `png`, `svg`, `eps`. mkhtml writes pdf and png always. The root backend writes `plots/<set>/root/index.html`: a section per cell, each page by its PNG or SVG, else an embedded PDF, linked to every format; add `png` for thumbnails a browser shows at once

### `band`

**Type** list of strings · a figure may override it

curve axes drawn as an envelope: per value of the other curve axes, one curve, the band quantity's first value, with the min–max of all its values shaded around it in the curve's colour (the usual PDF or scale band). Its legend entry ends `(<q> envelope)`; its own statistical errors are not drawn. A name that is not a curve axis of the configuration (swept, not `plot_points`, not combined) is refused at plan time. The yoda backend draws the same envelope as mkhtml's error band

### `objects`

**Type** list of strings · **Accepts** `"default"` (the layer below's value)

matched against the option-free YODA path (`/photo_eic/d01-x01-y01`) or any variant's path. No object matching is an error.

### `ratio`

**Type** true or false · **Default** `false` · **Accepts** `"default"` (the layer below's value) · `"native"` (the drawing tool's own) · a figure may override it

a ratio pad: each curve over the data, or over the first curve when there are no data

### `y_gutter`

**Type** number · **Default** `0.5` · **Accepts** at least 0 · `"default"` (the layer below's value) · `"native"` (the drawing tool's own) · a figure may override it

the top of the y axis at (1 + g) × the largest drawn value (on a log axis, g of the decades shown); `0`: no headroom. `"native"`: no gutter, the tool's own range (a v2 file's [plot] says `"default"`)

### `x_gutter`

**Type** number · **Accepts** at least 0 · `"default"` (the layer below's value) · `"native"` (the drawing tool's own) · a figure may override it

widens x by g of its span, symmetrically (in decades on a log axis). `"default"`: the range the bins give

### `x_range`

**Type** list of numbers or strings · a figure may override it

the x axis limits, `[minimum, maximum]`, each end a number or `"default"`: the layer below's end (a figure's `["default", 10]` keeps `[plot]`'s minimum), and in `[plot]` the range the page calculates. They only show: the statistics are taken over the calculated range. A heat map and a statistic figure take them from their own figure alone; a heat map's are kept within its histogram and widened to whole bins, and a range that misses the histogram is refused

### `y_range`

**Type** list of numbers or strings · a figure may override it

the y axis limits, `[minimum, maximum]`, each end as in `x_range`. It only cuts what is drawn: the statistics and the ratios are the curves' own values, and the ratio pad cuts at its own range. A numeric end holds when a curve passes it: Paint and mpl clip the curve, and a point's bar or a band reaching in, at the frame, and mark each bin past it with a thin line in the curve's colour, 2 px outside the frame (inside where a joined ratio pad leaves no room); curves past it in one bin share its width. The data are never marked, nor a value <= 0 on a log axis

### `logy`

**Type** true or false · **Accepts** `"default"` (the layer below's value) · `"native"` (the drawing tool's own) · a figure may override it

log y (default: the .plot's)

### `logx`

**Type** true or false · **Accepts** `"default"` (the layer below's value) · `"native"` (the drawing tool's own) · a figure may override it

log x (default: the .plot's)

### `logz`

**Type** true or false · **Accepts** `"default"` (the layer below's value) · `"native"` (the drawing tool's own) · a figure may override it

a heat map's colour scale

### `auto_range`

**Type** true or false · **Default** `true` · **Accepts** `"default"` (the layer below's value) · `"native"` (the drawing tool's own) · a figure may override it

trim x to the bins with content, in curves and data

### `normalise`

**Type** string or true or false · **Default** `false` · **Accepts** `"area"` · `false` · `"default"` (the layer below's value) · `"native"` (the drawing tool's own) · a figure may override it

`"area"`: every curve, and the data, scaled to unit area, Σ value × bin width over the bins drawn (after voiding and the data's alignment), so pages compare shapes. Both backends scale the same way. The y label stays the `.plot`'s: set `y_label` (e.g. `"$1/\sigma\,\mathrm{d}\sigma/\mathrm{d}E_T$"`) on the pages it applies to. A figure may set it for its own

### `void_empty`

**Type** true or false · **Default** `false` · **Accepts** `"default"` (the layer below's value) · `"native"` (the drawing tool's own) · a figure may override it

blank a bin that is zero in **every** curve

### `use_data`

**Type** true or false · **Default** `true` · a figure may override it

`false`: the `[plot.data]` table stays in the file but is not drawn, and a `ratio` divides each curve by the page's first curve, the first value of its curve axis

### `min_entries`

**Type** integer · **Default** `0` · **Accepts** at least 0 · `"default"` (the layer below's value) · `"native"` (the drawing tool's own) · a figure may override it

blank a bin that fewer raw entries went into, in **any** curve (read from the `/RAW` twin; objects without one are not voided this way)

### `range_pad`

**Type** integer · **Default** `0` · **Accepts** at least 0 · `"default"` (the layer below's value) · `"native"` (the drawing tool's own) · a figure may override it

whole bins kept either side of the filled ones

### `sets`

**Type** list of integers or strings or lists or tables or table · a figure may override it

the pages' cells, instead of the `plot_points` grid. An entry is a selector, a list of them (`set<k>`, its place), or a table. A selector is a 1-based index (as `point i/n` counts), a point's name, a glob of names (`"sh3_NNPDF40*"`), a tag of a quantity's (`"py8"`: every point with it), `"quantity=tag"`, or `"all"`; a string entry names its folder (`"pdf=X"` → `pdf-X`); its points are its curves, in the order named. A table (`[[plot.sets]]`): `name` (its folder, default `set<k>`), `points` (selectors), `pages` (a filter whose quantities are the page axes: a cell per combination of their values among the set's points, `<set>/<cell>/<object>`), `curves` (a filter, or a list of them: the union, in order), `reference` (a filter: the curve moved first on each page), `look` (`{ colour = "<q>", line = "<q>" }`, or `"palette"`; with none, two varying curve axes: the one of at most 4 values the line), and any page key of `[plot]`, `objects` and `style` for its pages. A filter is `{ quantity = "all" | tag | glob | "!tag" | number | [those] }`: every combination of its quantities' values (an outer product). In `curves`, a value may carry its curves' look: `{ tag = "…", colour, line, width }`, or several values' in order, `{ tags = "all" | […] (or all = true), colours = […], lines = […], widths = […] }` (`color`, `colors` accepted). A swept quantity a table names in neither pages nor curves, taking several values, pages too, and the stage says so. A selector, tag or quantity no point has is refused at plan time. merged, scan and compare figures page by `plot_points` only

### `looks`

**Type** table

[plot.looks.<quantity>]: a value's look on every page and in every Run, by its tag: a colour (`"#rrggbb"`, a ROOT name or number) or `{ colour, line, width }`. A tag a Run does not have is unused, so a value commented out keeps its look. Over the quantity's own styles; a set's look, and a curves filter's styled values, over it; a set's automatic look leaves an axis with looks alone

### `across`

**Type** table

sets of the Runs of this errand together, as `[plot.sets.<name>]` are of one Run's points, with more axes: `@events` (each Run's event count, tags like `10M`), `@run` (its folder), `@configuration` and, when a Run is tagged, `@tag` (each Run's tag; an untagged Run's labelled `untagged`). `@events` and `@tag` each page a set that does not name it. Kept in `results/<A>/<E>/plot.toml`, drawn by `heimdall plot <A>/<E> --across` into `results/<A>/<E>/plots/<set>/` and `statistics/<set>/`; which Runs, and how, is `[plot.across_from]`

### `across_from`

**Type** table

the Runs together's `[from]`: written into `results/<A>/<E>/plot.toml` over its defaults (every Run, `prefer = "last"`) when a job writes that document, and by `heimdall plot … --across --style-sync`; without this table a sync leaves the document's `[from]` as it is. Its keys are `[plot.across_from]`'s

### `draw`

**Type** list of strings

the names of the sets `heimdall plot` draws when it is given none (`--sets`), every set by default; a job writes `[errand].plot`'s list here. A name no set has is refused

### `split`

**Type** integer · **Accepts** at least 1 · a figure may override it

at most this many points on a page: each cell (a `plot_points` cell, or a set) cut into pages in point order, `<cell>-<k>` (`part<k>` with no cell): 24 points, `split = 3`, 8 pages. A curve is labelled by the quantities that differ on its page

### `statistics`

**Type** true or false · **Default** `true` · **Accepts** `"default"` (the layer below's value)

each page's statistics, as Paint draws it (after voiding, alignment and normalisation, over the x span auto-range and the gutters give: `x_range` and `y_range` only show), into each set's `results/…/statistics/<set>/statistics.csv`: per curve `area` (Σ y·Δx) and its error; against the reference (the data, else the page's first curve), on the reference's bins the curve covers, `ref_area` and the curve's `cmp_area` there, `abs_area` (Σ |y − y_ref|·Δx), `rel_abs_area` (abs_area / ref_area), `area_ratio` (cmp_area / ref_area: MC over data), `ratio_mean` (the ratio pad's mean, Σ y/y_ref·Δx / Σ Δx, Δx in log x on a log-x page), `ratio_dev` (its area about one over the width compared, Σ |y/y_ref − 1|·Δx / Σ Δx), `chi2`, `ndf`, `chi2_ndf`. false: no table

### `legend_statistic`

**Type** string · **Default** `"none"` · **Accepts** `"none"` · `"area"` · `"abs_area"` · `"rel_abs_area"` · `"area_ratio"` · `"ratio_mean"` · `"ratio_dev"` · `"chi2"` · `"chi2_ndf"` · a figure may override it

one of the statistics (see `statistics`) after each curve's legend entry: `chi2_ndf` → `(χ²/ndf 1.31)`; the reference's own entry gets none

### `root_style`

**Type** string · **Accepts** `"default"` (the layer below's value)

a style file over base.toml. Refused by the yoda backend alone.

### `title`

**Type** string · **Accepts** `"default"` (the layer below's value) · `"native"` (the drawing tool's own) · a figure may override it

the main title, centred above the frame. Every page; a figure overrides it for its own

### `title_left`

**Type** string · **Accepts** `"default"` (the layer below's value) · `"native"` (the drawing tool's own) · a figure may override it

small text just above the frame's top-left and top-right corners, inherited the same way

### `title_right`

**Type** string · **Accepts** `"default"` (the layer below's value) · `"native"` (the drawing tool's own) · a figure may override it

small text just above the frame's top-left and top-right corners, inherited the same way

### `legend_header`

**Type** string · **Accepts** `"default"` (the layer below's value) · `"native"` (the drawing tool's own) · a figure may override it

the legend's first line, inherited the same way. Children inherit every key their parent has and a key means the same at both levels

### `data`

**Type** table

reference data and which object each maps to: `[plot.data]`'s keys

### `style`

**Type** table

style keys for these pages, over `base.toml` and any style file: `heimdall explain style`

### `figures`

**Type** table

`[plot.figures.<figure>]`: a recipe for pages, with every page key of `[plot]` for its own

## [plot.figures.<name>]: a figure

[`band`](#band) · [`ratio`](#ratio) · [`y_gutter`](#y_gutter) · [`x_gutter`](#x_gutter) · [`x_range`](#x_range) · [`y_range`](#y_range) · [`logy`](#logy) · [`logx`](#logx) · [`logz`](#logz) · [`auto_range`](#auto_range) · [`normalise`](#normalise) · [`void_empty`](#void_empty) · [`use_data`](#use_data) · [`min_entries`](#min_entries) · [`range_pad`](#range_pad) · [`sets`](#sets) · [`split`](#split) · [`legend_statistic`](#legend_statistic) · [`title`](#title) · [`title_left`](#title_left) · [`title_right`](#title_right) · [`legend_header`](#legend_header) · [`class`](#class) · [`type`](#type) · [`name`](#name) · [`objects`](#objects) · [`statistic`](#statistic) · [`sort`](#sort) · [`op`](#op) · [`x`](#x) · [`y`](#y) · [`pages`](#pages) · [`columns`](#columns) · [`over`](#over) · [`configurations`](#configurations) · [`labels`](#labels) · [`x_label`](#x_label) · [`y_label`](#y_label) · [`style`](#style)

### `band`

**Type** list of strings · **Accepts** `"default"` (the layer below's value)

curve axes drawn as an envelope: per value of the other curve axes, one curve, the band quantity's first value, with the min–max of all its values shaded around it in the curve's colour (the usual PDF or scale band). Its legend entry ends `(<q> envelope)`; its own statistical errors are not drawn. A name that is not a curve axis of the configuration (swept, not `plot_points`, not combined) is refused at plan time. The yoda backend draws the same envelope as mkhtml's error band

### `ratio`

**Type** true or false · **Accepts** `"default"` (the layer below's value) · `"native"` (the drawing tool's own)

a ratio pad: each curve over the data, or over the first curve when there are no data

### `y_gutter`

**Type** number · **Accepts** at least 0 · `"default"` (the layer below's value) · `"native"` (the drawing tool's own)

the top of the y axis at (1 + g) × the largest drawn value (on a log axis, g of the decades shown); `0`: no headroom. `"native"`: no gutter, the tool's own range (a v2 file's [plot] says `"default"`)

### `x_gutter`

**Type** number · **Accepts** at least 0 · `"default"` (the layer below's value) · `"native"` (the drawing tool's own)

widens x by g of its span, symmetrically (in decades on a log axis). `"default"`: the range the bins give

### `x_range`

**Type** list of numbers or strings · **Accepts** `"default"` (the layer below's value)

the x axis limits, `[minimum, maximum]`, each end a number or `"default"`: the layer below's end (a figure's `["default", 10]` keeps `[plot]`'s minimum), and in `[plot]` the range the page calculates. They only show: the statistics are taken over the calculated range. A heat map and a statistic figure take them from their own figure alone; a heat map's are kept within its histogram and widened to whole bins, and a range that misses the histogram is refused

### `y_range`

**Type** list of numbers or strings · **Accepts** `"default"` (the layer below's value)

the y axis limits, `[minimum, maximum]`, each end as in `x_range`. It only cuts what is drawn: the statistics and the ratios are the curves' own values, and the ratio pad cuts at its own range. A numeric end holds when a curve passes it: Paint and mpl clip the curve, and a point's bar or a band reaching in, at the frame, and mark each bin past it with a thin line in the curve's colour, 2 px outside the frame (inside where a joined ratio pad leaves no room); curves past it in one bin share its width. The data are never marked, nor a value <= 0 on a log axis

### `logy`

**Type** true or false · **Accepts** `"default"` (the layer below's value) · `"native"` (the drawing tool's own)

as [plot].logy, for these pages

### `logx`

**Type** true or false · **Accepts** `"default"` (the layer below's value) · `"native"` (the drawing tool's own)

as [plot].logx, for these pages

### `logz`

**Type** true or false · **Accepts** `"default"` (the layer below's value) · `"native"` (the drawing tool's own)

a heat map's colour scale

### `auto_range`

**Type** true or false · **Accepts** `"default"` (the layer below's value) · `"native"` (the drawing tool's own)

trim x to the bins with content, in curves and data

### `normalise`

**Type** string or true or false · **Accepts** `"area"` · `false` · `"default"` (the layer below's value) · `"native"` (the drawing tool's own)

`"area"`: every curve, and the data, scaled to unit area, Σ value × bin width over the bins drawn (after voiding and the data's alignment), so pages compare shapes. Both backends scale the same way. The y label stays the `.plot`'s: set `y_label` (e.g. `"$1/\sigma\,\mathrm{d}\sigma/\mathrm{d}E_T$"`) on the pages it applies to. A figure may set it for its own

### `void_empty`

**Type** true or false · **Accepts** `"default"` (the layer below's value) · `"native"` (the drawing tool's own)

blank a bin that is zero in **every** curve

### `use_data`

**Type** true or false · **Accepts** `"default"` (the layer below's value)

`false`: the `[plot.data]` table stays in the file but is not drawn, and a `ratio` divides each curve by the page's first curve, the first value of its curve axis

### `min_entries`

**Type** integer · **Accepts** at least 0 · `"default"` (the layer below's value) · `"native"` (the drawing tool's own)

blank a bin that fewer raw entries went into, in **any** curve (read from the `/RAW` twin; objects without one are not voided this way)

### `range_pad`

**Type** integer · **Accepts** at least 0 · `"default"` (the layer below's value) · `"native"` (the drawing tool's own)

whole bins kept either side of the filled ones

### `sets`

**Type** list of integers or strings or lists or tables or table · **Accepts** `"default"` (the layer below's value)

the pages' cells, instead of the `plot_points` grid. An entry is a selector, a list of them (`set<k>`, its place), or a table. A selector is a 1-based index (as `point i/n` counts), a point's name, a glob of names (`"sh3_NNPDF40*"`), a tag of a quantity's (`"py8"`: every point with it), `"quantity=tag"`, or `"all"`; a string entry names its folder (`"pdf=X"` → `pdf-X`); its points are its curves, in the order named. A table (`[[plot.sets]]`): `name` (its folder, default `set<k>`), `points` (selectors), `pages` (a filter whose quantities are the page axes: a cell per combination of their values among the set's points, `<set>/<cell>/<object>`), `curves` (a filter, or a list of them: the union, in order), `reference` (a filter: the curve moved first on each page), `look` (`{ colour = "<q>", line = "<q>" }`, or `"palette"`; with none, two varying curve axes: the one of at most 4 values the line), and any page key of `[plot]`, `objects` and `style` for its pages. A filter is `{ quantity = "all" | tag | glob | "!tag" | number | [those] }`: every combination of its quantities' values (an outer product). In `curves`, a value may carry its curves' look: `{ tag = "…", colour, line, width }`, or several values' in order, `{ tags = "all" | […] (or all = true), colours = […], lines = […], widths = […] }` (`color`, `colors` accepted). A swept quantity a table names in neither pages nor curves, taking several values, pages too, and the stage says so. A selector, tag or quantity no point has is refused at plan time. merged, scan and compare figures page by `plot_points` only

### `split`

**Type** integer · **Accepts** at least 1 · `"default"` (the layer below's value)

at most this many points on a page: each cell (a `plot_points` cell, or a set) cut into pages in point order, `<cell>-<k>` (`part<k>` with no cell): 24 points, `split = 3`, 8 pages. A curve is labelled by the quantities that differ on its page

### `legend_statistic`

**Type** string · **Accepts** `"none"` · `"area"` · `"abs_area"` · `"rel_abs_area"` · `"area_ratio"` · `"ratio_mean"` · `"ratio_dev"` · `"chi2"` · `"chi2_ndf"` · `"default"` (the layer below's value)

one of the statistics (see `statistics`) after each curve's legend entry: `chi2_ndf` → `(χ²/ndf 1.31)`; the reference's own entry gets none

### `title`

**Type** string · **Accepts** `"default"` (the layer below's value) · `"native"` (the drawing tool's own)

the main title, centred above the frame. Every page; a figure overrides it for its own

### `title_left`

**Type** string · **Accepts** `"default"` (the layer below's value) · `"native"` (the drawing tool's own)

small text just above the frame's top-left and top-right corners, inherited the same way

### `title_right`

**Type** string · **Accepts** `"default"` (the layer below's value) · `"native"` (the drawing tool's own)

small text just above the frame's top-left and top-right corners, inherited the same way

### `legend_header`

**Type** string · **Accepts** `"default"` (the layer below's value) · `"native"` (the drawing tool's own)

the legend's first line, inherited the same way. Children inherit every key their parent has and a key means the same at both levels

### `class`

**Type** string · **Default** `"defined"` · **Accepts** `"defined"` · `"overlay"` · `"merged"` · `"compare"` · `"derived"` · `"scan"` · `"sheet"` · `"statistic"`

how the pages are built. `defined`: an analysis object's own pages, `<cell>/<object>`, its curves the cell's points (and option variants). `overlay`: several objects of each point on one page, `<cell>/<name>`; a curve per object and point, labelled by `labels` (plus the point's, when the page has several); a ratio divides by the first curve. `merged`: the objects' pages, `<cell>/<name>/<object>`, with the points merged over the `over` axes: per value of the other axes, their YODAs merged by the combine folder's command (`rivet-merge -e`: statistics add, σ averaged), once per change of a member's YODA, into `.cache/…/merged/<name>/`. The run keeps its points apart; the figure alone merges them (`combine` merges them for the whole configuration). `sheet`: drawn pages laid out in a grid (`pages`, `columns`; below). `compare`: the objects' pages across configurations, `<E>/compare/<name>/<cell>/<object>` beside the configurations' own folders (in `records/` and `results/`, a folder per backend). A curve per configuration and point (or combined group), labelled by the configuration (`labels`, else its `label`) and then the point's curve axes. The configurations must have the same page and curve axes (checked at plan time); the figure is drawn by the plot stage of each of them once all have complete points, and says what it waits for otherwise (`heimdall plot` draws it too). `derived`: a new object per point, `/FIGURES/<name>` (`/FIGURES:R=0.4/<name>` per analysis-option variant): `op = "ratio"`, `"difference"` or `"sum"` of its two objects (histograms made estimates first; the same binning, else an error naming both), or `"projection-x"`/`"projection-y"` of its one 2D object (summed over the other axis: a histogram's weights, an estimate's values × widths, as a Scatter2D whose x ranges are the bins). It is appended to a copy of each point's YODA (`.cache/…/derived/`, remade when the product or the figures change, by `framework/plot/figures/derive.py`: YODA's Python, so `gjallarhorn`), and is then an object like any: its pages `<cell>/<name>` (labels from its first object's `.plot`; set `y_label`), an overlay or a merged or compare figure may name it (`"r15"`). `scan`: one number per point against a swept quantity: `x` a curve axis whose values are numbers, `y` = `sigma` (the point's `/_XSEC`), `entries` (its events, or its object's raw entries), or `integral`, `mean`, `bin:N` of its one object. A page per cell, `<cell>/<name>`, a curve per value of the other curve axes: a Scatter2D, a point per x value with an x range halfway to its neighbours centred on it (so every backend can draw it as a bin; it is drawn as markers, `type = "Scatter2D"`). Axis titles: the quantity's name and the y read, until set. A quantity of names (PDF sets) cannot be an x yet

### `type`

**Type** string · **Accepts** `"Hist1D"` · `"Scatter2D"` · `"HeatMap"`

what is drawn: `Hist1D`, steps per curve; `Scatter2D`, a marker per bin at its centre with its y error, in the curve's colour (`data.marker`, `data.marker_size` of the style), as Paint draws data; the legend shows the marker. The page TOML says `markers = true`; mkhtml and mpl draw the curves as they draw points (`ConnectBins=0`, with their x bars). `HeatMap`: a 2D object (a YODA `Histo2D` or `Estimate2D`), the default for one: a page per point of the cell, `<cell>/<object>/<point>`, coloured by value with its scale on the right (labels from the `.plot`, `ZLabel` and `LogZ` too; no ratio, data or voiding). Paint draws heat maps; mkhtml and mpl draw the 1D pages only, and the plot stage says so. A 1D object cannot be a HeatMap, a 2D object neither a Hist1D nor a Scatter2D, nor in an overlay

### `name`

**Type** string

an overlay's page file stem, a merged figure's folder. A defined figure takes none: its pages are the objects' own

### `objects`

**Type** list of strings

matched against the short name (`d04-x01-y01`), the option-free path or a variant's path. A glob matching no object of the points is an error, at the plot stage

### `statistic`

**Type** string · **Accepts** `"area"` · `"abs_area"` · `"rel_abs_area"` · `"area_ratio"` · `"ratio_mean"` · `"ratio_dev"` · `"chi2"` · `"chi2_ndf"`

a statistic figure's number, as `statistics.csv` has it: per cell (or set) and object, a page whose x axis is the page's curves by their labels, a bin each, and y that number of each against the page's reference (its own reference curve left out), drawn as markers; `area` with its error. Its pages: `<cell>/<name>/<object>`

### `sort`

**Type** true or false · **Default** `false`

a statistic figure's: its points best first (the smallest number), instead of in curve order

### `op`

**Type** string · **Accepts** `"ratio"` · `"difference"` · `"sum"` · `"projection-x"` · `"projection-y"`

a derived figure's: `ratio`, `difference`, `sum` (two objects), `projection-x`, `projection-y` (one)

### `x`

**Type** string

a scan figure's quantity (a numeric curve axis) and number (`sigma`, `entries`, `integral`, `mean`, `bin:N`); `sigma` and `entries` need no object

### `y`

**Type** string

a scan figure's quantity (a numeric curve axis) and number (`sigma`, `entries`, `integral`, `mean`, `bin:N`); `sigma` and `entries` need no object

### `pages`

**Type** list of strings

a sheet's: the drawn pages whose names (`18x275/d02-x01-y01`, `*/eta_algorithms`) the globs match (by their names in each set), in the globs' order, tiled `columns` wide into `plots/<set>/<backend>/sheets/<name>.pdf` and `.png`, each pad the page as it was drawn alone (pdflatex places the PDFs as vectors, a PNG where a page has no PDF; the `.png` is that PDF rendered by pdftoppm). For Paint's and mpl's pages. A sheet takes no page keys (its pages' figures set those); a glob naming no page fails the sheet

### `columns`

**Type** integer · **Accepts** at least 1

a sheet's: the drawn pages whose names (`18x275/d02-x01-y01`, `*/eta_algorithms`) the globs match (by their names in each set), in the globs' order, tiled `columns` wide into `plots/<set>/<backend>/sheets/<name>.pdf` and `.png`, each pad the page as it was drawn alone (pdflatex places the PDFs as vectors, a PNG where a page has no PDF; the `.png` is that PDF rendered by pdftoppm). For Paint's and mpl's pages. A sheet takes no page keys (its pages' figures set those); a glob naming no page fails the sheet

### `over`

**Type** list of strings

a merged figure's: curve axes of the configuration (swept, not `plot_points`, not combined), checked at plan time; it may not also `band` them

### `configurations`

**Type** list of strings

a compare figure's, two or more, in curve order; one at least of this file. `"<A>/<E>:<cfg>"` names a configuration of another errand file: its points (as its last job left them) are curves beside this file's, labelled `<its errand> <its label>` by default and by its own quantities; its page axes must have this file's tags. The pages are this errand's (`<E>/compare/<name>/`), drawn by this errand's plot stage or `heimdall plot`

### `labels`

**Type** list of strings

an overlay's: one legend label per object; a compare figure's: one per configuration (default: each configuration's `label`)

### `x_label`

**Type** string · **Accepts** `"default"` (the layer below's value)

the axis titles (LaTeX)

### `y_label`

**Type** string · **Accepts** `"default"` (the layer below's value)

the axis titles (LaTeX)

### `style`

**Type** table

a style layer for these pages

## [plot.data]: reference data

[`file`](#file) · [`legend`](#legend) · [`map`](#map)

### `file`

**Type** string

`rivet:<Analysis>`: Rivet's own reference file (`build/Rivet/`, then `rivet-config --datadir`, `.yoda` or `.yoda.gz`); otherwise a path under `datasets/` (not in git)

### `legend`

**Type** string · **Default** `"Data"`

the data's legend entry

### `map`

**Type** table

MC object name (`d01-x01-y01`) → reference path. **Explicit only**, never matched by name. A file without a map, or a map without a file, is an error.

## [plot.across_from]: runs together

[`runs`](#runs) · [`prefer`](#prefer) · [`ignore`](#ignore)

### `runs`

**Type** list of strings · **Default** `["*"]`

the Runs drawn together, by globs of their folders beside the document (`["04_*", "0[5-7]_*"]`); every Run by default

### `prefer`

**Type** string · **Default** `"last"` · **Accepts** `"last"` · `"all"`

a point two Runs have (every quantity's tag, the event count and the Run's tag the same, the ignored quantities aside): `"last"` draws it from the later Run that completed it, and says so; `"all"` keeps both. Runs of different tags never stand for each other

### `ignore`

**Type** list of strings

quantities of the Runs (or `"@events"`) that are no axis across them: an ignored quantity never pages a set or tells its curves apart, and never keeps two Runs' points apart (with `prefer = "last"` the later stands for both, unless their tags differ). It must hold one value within each Run, else the drawing is refused, naming the Run and its values; its value stays each point's, so a page text that cites it (`{q:generator}`) shows it when the page's curves share it. A name no Run has is refused

## [stats]: heimdall stats

[`sets`](#sets) · [`objects`](#objects) · [`reference`](#reference) · [`normalise`](#normalise) · [`void_empty`](#void_empty) · [`min_entries`](#min_entries) · [`auto_range`](#auto_range) · [`range_pad`](#range_pad)

### `sets`

**Type** list of strings

the sets measured (default: [plot].draw, else every set)

### `objects`

**Type** list of strings

the objects measured: globs of their short names (d01-*) or YODA paths (default: the pages')

### `reference`

**Type** string or table · **Accepts** `"data"` · `"curves"`

`"data"` (the default): the mapped data where a page has it, else the page's first curve; `"curves"`: each page's first curve, data or not; a filter, `{ generator = "py8", pdf = "NNPDF23lo" }`, names the reference curve on every page (moved first), data or not

### `normalise`

**Type** string or true or false · **Accepts** `"area"` · `false`

as [plot].normalise, for the numbers: "area" compares shapes alone

### `void_empty`

**Type** true or false

as [plot].void_empty, for the numbers

### `min_entries`

**Type** integer · **Accepts** at least 0

as [plot].min_entries, for the numbers

### `auto_range`

**Type** true or false

as [plot].auto_range, for the numbers

### `range_pad`

**Type** integer · **Accepts** at least 0

as [plot].range_pad, for the numbers
