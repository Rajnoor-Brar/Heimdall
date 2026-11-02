---
id: settings-style
summary: every style key a page may set in [plot.style] or a style file, nested as the file nests them
code: src/Apps/Paint/base.toml
generated: true
---

Generated from the code; change it there. `heimdall explain <key>` says the same. From `src/Apps/Paint/base.toml`, which every page starts from. A layer names only what it changes.

# `page`

[`size`](#size) · [`dpi`](#dpi) · [`font`](#font)

## `size`

| Type | Default | Acceptable |
|---|---|---|
| list | `[4.67, 4.21]` | — |

Inches: the PDF's page; the PNG is size × dpi pixels.

## `dpi`

| Type | Default | Acceptable |
|---|---|---|
| integer | `300` | — |

PNG resolution: 300 → 1400 × 1264 pixels.

## `font`

| Type | Default | Acceptable |
|---|---|---|
| string | `"serif"` | `serif`, `sans`, `mono` |

(ROOT's Times, Helvetica, Courier)

## `margins`

[`left`](#left) · [`right`](#right) · [`top`](#top) · [`bottom`](#bottom)

### `left`

| Type | Default | Acceptable |
|---|---|---|
| number | `0.16` | — |

Fractions of the page, around the axes.

### `right`

| Type | Default | Acceptable |
|---|---|---|
| number | `0.032` | — |

Fractions of the page, around the axes.

### `top`

| Type | Default | Acceptable |
|---|---|---|
| number | `0.066` | — |

Fractions of the page, around the axes.

### `bottom`

| Type | Default | Acceptable |
|---|---|---|
| number | `0.11` | — |

Fractions of the page, around the axes.

# `text`

[`title`](#title) · [`labels`](#labels) · [`legend`](#legend) · [`header`](#header) · [`page_title`](#page_title) · [`corner`](#corner)

## `title`

| Type | Default | Acceptable |
|---|---|---|
| number | `10.0` | — |

Axis titles.

## `labels`

| Type | Default | Acceptable |
|---|---|---|
| number | `8.0` | — |

Tick labels.

## `legend`

| Type | Default | Acceptable |
|---|---|---|
| number | `9.0` | — |

Legend entries (the yoda backend follows it)

## `header`

| Type | Default | Acceptable |
|---|---|---|
| number | `9.0` | — |

The legend's first line: legend_header.

## `page_title`

| Type | Default | Acceptable |
|---|---|---|
| number | `12.0` | — |

Title, centred above the frame.

## `corner`

| Type | Default | Acceptable |
|---|---|---|
| number | `9.0` | — |

Title_left and title_right, just above the frame's corners.

# `curves`

[`palette`](#palette) · [`width`](#width) · [`errors`](#errors)

## `palette`

| Type | Default | Acceptable |
|---|---|---|
| list | `["#EE3311", "#3366FF", "#109618", "#FF9900", "#990099"]` | — |

#rrggbb, ROOT names (kBlue+1) or numbers.

## `width`

| Type | Default | Acceptable |
|---|---|---|
| number | `1.0` | — |

Points: the steps and their error bars.

## `errors`

| Type | Default | Acceptable |
|---|---|---|
| string | `"bars"` | — |

Bars (at the bin centres) | band | none.

# `data`

[`colour`](#colour) · [`marker`](#marker) · [`marker_size`](#marker_size) · [`x_bars`](#x_bars)

## `colour`

| Type | Default | Acceptable |
|---|---|---|
| string | `"kBlack"` | — |

The reference data.

## `marker`

| Type | Default | Acceptable |
|---|---|---|
| integer | `20` | — |

ROOT's marker style.

## `marker_size`

| Type | Default | Acceptable |
|---|---|---|
| number | `2.0` | — |

Points.

## `x_bars`

| Type | Default | Acceptable |
|---|---|---|
| true or false | `true` | — |

The bin width as a horizontal bar.

# `axes`

[`tick_length`](#tick_length) · [`ticks_all_sides`](#ticks_all_sides) · [`titles_at_ends`](#titles_at_ends) · [`title_offset`](#title_offset) · [`label_offset`](#label_offset)

## `tick_length`

| Type | Default | Acceptable |
|---|---|---|
| number | `6.0` | — |

Points; minor ticks are half as long.

## `ticks_all_sides`

| Type | Default | Acceptable |
|---|---|---|
| true or false | `true` | — |

Ticks on the top and right edges too.

## `titles_at_ends`

| Type | Default | Acceptable |
|---|---|---|
| true or false | `true` | — |

The x title at the right end, the y title at the top; false centres them.

## `title_offset`

| Type | Default | Acceptable |
|---|---|---|
| list | `[1.0, 1.55]` | — |

X, y: ROOT's title offsets (larger is further from the axis)

## `label_offset`

| Type | Default | Acceptable |
|---|---|---|
| number | `2.5` | — |

Points between an axis and its tick labels.

# `legend`

[`position`](#position) · [`inset`](#inset) · [`spacing`](#spacing) · [`symbol`](#symbol) · [`gap`](#gap)

## `position`

| Type | Default | Acceptable |
|---|---|---|
| string | `"top-right"` | `top-right`, `top-left`, `bottom-right`, `bottom-left`, `best` |

, or [x, y]: its top-right corner in fractions of the frame (then right-aligned); or outside the frame, which shrinks to make room: out-right | out-left (a column beside it) | out-top | out-bottom (as many columns as fit its width)

## `inset`

| Type | Default | Acceptable |
|---|---|---|
| list | `[5.0, 5.0]` | — |

Points from the frame's corner (x, y), for a named position; from the frame and the page's edge, outside.

## `spacing`

| Type | Default | Acceptable |
|---|---|---|
| number | `1.2` | — |

Line pitch, × the legend's text size.

## `symbol`

| Type | Default | Acceptable |
|---|---|---|
| number | `16.0` | — |

Points: the width of the "+" beside each entry.

## `gap`

| Type | Default | Acceptable |
|---|---|---|
| number | `5.0` | — |

Points between the "+" and its text.

# `ratio`

[`heights`](#heights) · [`range`](#range) · [`limits`](#limits) · [`divisions`](#divisions) · [`decimals`](#decimals) · [`gap`](#gap-1)

## `heights`

| Type | Default | Acceptable |
|---|---|---|
| list | `[2.0, 1.0]` | — |

The main pad to the ratio pad (mkhtml's 6:3)

## `range`

| Type | Default | Acceptable |
|---|---|---|
| list | `[0.5, 1.5]` | — |

Always shown; widened to the ratios drawn ….

## `limits`

| Type | Default | Acceptable |
|---|---|---|
| list | `[0.0, 3.0]` | — |

… but never past these.

## `divisions`

| Type | Default | Acceptable |
|---|---|---|
| integer | `512` | — |

ROOT's axis divisions: at most 12 labelled (0.1 on ~0.4–1.5), 5 minor each.

## `decimals`

| Type | Default | Acceptable |
|---|---|---|
| true or false | `true` | — |

Labels 1.0, 1.2, … rather than 1, 1.2, ….

## `gap`

| Type | Default | Acceptable |
|---|---|---|
| number | `0.0` | — |

Points between the main frame and the ratio's: 0 joins them (mkhtml's)
