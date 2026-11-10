---
id: settings-report
summary: every key of a report's recipe: [report] and [[report.section]]
code: framework/schema/report.toml
generated: true
---

Generated from the code; change it there. `heimdall explain <key>` says the same.

# `[report]`

[`title`](#title) · [`subtitle`](#subtitle) · [`from`](#from) · [`output`](#output) · [`template`](#template) · [`section`](#section) · [`tools`](#tools) · [`font`](#font) · [`size`](#size) · [`accent`](#accent) · [`contents`](#contents) · [`columns`](#columns) · [`method`](#method) · [`context`](#context)

## `title`

| Type | Default | Acceptable |
|---|---|---|
| string | — | — |

The report's title, on its front page (default: its one source's address, else what its sources' addresses share). `{assignment}`, `{errand}`, `{configuration}` and `{title}` (a configuration's title, else its name) in the title or subtitle are filled in from its sources' plot documents (several values joined by commas), so one template titles each folder's report.

## `subtitle`

| Type | Default | Acceptable |
|---|---|---|
| string | — | — |

A line under the title: the date, who it is for.

## `from`

| Type | Default | Acceptable |
|---|---|---|
| list of strings | — | — |

Its sources: result folders holding a plot.toml, as <A>/<E>/<R>, <A>/<E> (each of its Runs, then its own when drawn), a path, or a glob; the command line's replace them.

## `output`

| Type | Default | Acceptable |
|---|---|---|
| string | — | — |

Where it is built: a folder under reports/ (eic/weekly), or a path (./…, /…); default: where results/ has its sources (reports/<A>/<E>/<R>/, reports/<A>/<E>/, …); -o replaces it. Not in an errand file.

## `template`

| Type | Default | Acceptable |
|---|---|---|
| string | — | — |

A recipe laid under this table, named as [config].import names a file (weekly, eic/weekly, ./…; .toml optional): its keys under these, its sections first.

## `section`

| Type | Default | Acceptable |
|---|---|---|
| list of tables | — | — |

Its sections, [[report.section]] each, in order: each shows one of pages, compare, stats, bars, files or tools.

## `tools`

| Type | Default | Acceptable |
|---|---|---|
| list of strings | — | — |

The tools whose configurations the default sections show, last, in a Tools section: tags ([tools.<tag>]) or globs; default: every tool given a card or options; [] none.

## `font`

| Type | Default | Acceptable |
|---|---|---|
| string | `"sans"` | `"sans"`, `"serif"` |

The report's font: sans sets everything in TeX Gyre Heros (Helvetica's metrics, as the pages Paint draws), math too; serif sets the body (notes, prose) in TeX Gyre Termes, the titles, tables and labels still sans.

## `size`

| Type | Default | Acceptable |
|---|---|---|
| number | `9.5` | at least 8 |

The body's size in pt, 8 to 12, its line 1.42 times it; titles, tables, captions and labels keep their own sizes.

## `accent`

| Type | Default | Acceptable |
|---|---|---|
| string | `"#2a78d6"` | — |

The accent colour, #rrggbb: section numbers, kickers, code's keys.

## `contents`

| Type | Default | Acceptable |
|---|---|---|
| true or false | `true` | — |

A table of contents on the front page, under the sources.

## `columns`

| Type | Default | Acceptable |
|---|---|---|
| integer | `2` | at least 1 |

A grid's columns when its section names none, 1 to 4 (a grid of one figure: 1; a side-by-side grid of three or more sources: 3)

## `method`

| Type | Default | Acceptable |
|---|---|---|
| true or false | `true` | — |

A section How the numbers are made, whenever the report shows statistics or bar tables: how a page is compared, each statistic shown (its formula and what it means, a paragraph each) and how a point's loss is made; the statistics parts then leave those notes out. false: each part keeps its own.

## `context`

| Type | Default | Acceptable |
|---|---|---|
| string | `"first"` | `"first"`, `"last"` |

Where what was run (the tools sections) and How the numbers are made go: first, before every other section (the results, in the recipe's order); last, after them.

## `[[report.section]]`

[`title`](#title-1) · [`note`](#note) · [`from`](#from-1) · [`pages`](#pages) · [`set`](#set) · [`cells`](#cells) · [`backend`](#backend) · [`layout`](#layout) · [`columns`](#columns-1) · [`label`](#label) · [`optional`](#optional) · [`compare`](#compare) · [`stats`](#stats) · [`bars`](#bars) · [`files`](#files) · [`tools`](#tools-1) · [`hide`](#hide) · [`plot`](#plot)

### `title`

| Type | Default | Acceptable |
|---|---|---|
| string | **required** | — |

The section's title, in the contents and above its figures.

### `note`

| Type | Default | Acceptable |
|---|---|---|
| string | — | — |

A line of text under the title.

### `from`

| Type | Default | Acceptable |
|---|---|---|
| list of strings | — | — |

This section's own sources (as [report].from), kept when the command line names others.

### `pages`

| Type | Default | Acceptable |
|---|---|---|
| list of strings | — | — |

Globs of page names in each source's plots/<set>/<backend>/ (`d01-x01-y01`, `18x275/d0*`, `*`): a grid of them per page cell, or per page with layout = "sources".

### `set`

| Type | Default | Acceptable |
|---|---|---|
| string | `"totality"` | — |

The set whose pages or numbers it takes: each source's plots/<set>/ and statistics/<set>/, else drawn for the report.

### `cells`

| Type | Default | Acceptable |
|---|---|---|
| list of strings | — | — |

Globs of page cells (the folders in a set: `18x275`), to take only those; default: every one.

### `backend`

| Type | Default | Acceptable |
|---|---|---|
| string or list of strings | — | `"root"`, `"mpl"` |

Whose drawn pages it takes; a list in order of preference (per page, the first that drew it; default: root, mpl)

### `layout`

| Type | Default | Acceptable |
|---|---|---|
| string | `"pages"` | `"pages"`, `"sources"` |

Pages: each source's pages in turn, a grid per page cell; sources: side by side, a grid per page, a panel per source.

### `columns`

| Type | Default | Acceptable |
|---|---|---|
| integer | — | at least 1 |

A grid's columns (default: 2 on an A4 page, 3 for a side-by-side grid of three or more)

### `label`

| Type | Default | Acceptable |
|---|---|---|
| string | `"folder"` | `"events"`, `"folder"` |

A side-by-side panel's label: folder, its source's folder name without the serial (with it, then with its errand, where two sources would share one); events, the events its points ran with (10M)

### `optional`

| Type | Default | Acceptable |
|---|---|---|
| true or false | `false` | — |

A source that neither has the section's set drawn (or measured) nor can draw it for the report (no such set, no complete point in it) is passed over, and the section left out when none has it; false: refused, naming the sets it has.

### `compare`

| Type | Default | Acceptable |
|---|---|---|
| list of strings | — | — |

Compare figures' names: their pages, from each source's errand's compare/<name>/.

### `stats`

| Type | Default | Acceptable |
|---|---|---|
| list of strings | — | — |

The statistics summary's sections, from each source's statistics/<set>/statistics.csv (else measured for the report): leaderboard (each point's loss, worst page, veto and categories), `category:<name>` (a category's section: what it asks and its metrics), marginals (a table per quantity: the loss of the points having each value), baseline (each point against `[ranking].baseline`), head-to-head (the pages `[ranking].head_to_head` names), or a metric's id (`chi2_sigma`) for its section, `<metric>:ranking`, `:crossed` or `:table` for one of its parts.

### `bars`

| Type | Default | Acceptable |
|---|---|---|
| list of strings | — | — |

Globs of page names: each page's bar graph of its curves' numbers, drawn for the report from statistics.csv (else from the numbers measured for it)

### `files`

| Type | Default | Acceptable |
|---|---|---|
| list of strings | — | — |

Your own PDF or PNG files, globs relative to the recipe's folder (`extras/*.png`)

### `tools`

| Type | Default | Acceptable |
|---|---|---|
| list of strings | — | — |

Tool tags ([tools.<tag>]) or globs, "*" every tool given a card or options: what each was given, read from each source's records, over its complete points: the card's lines every point had (its baseline), then each point's other lines (a table when they are key = value or key: value lines), and its other options.

### `hide`

| Type | Default | Acceptable |
|---|---|---|
| list of strings | — | — |

A tools section's: globs of varied lines' keys (else of the lines) to leave out ("Random:seed", "RANDOM_SEED")

### `plot`

| Type | Default | Acceptable |
|---|---|---|
| table | — | — |

A pages, stats or bars section's: [plot] keys over each source's own (its sets and figures added, its style laid over), its pages and numbers then drawn for the report into its cache, never into results/.
