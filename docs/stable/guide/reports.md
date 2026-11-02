---
id: reports
summary: heimdall report: an A4 report of Runs' pages and numbers; recipes, sections, what it draws for itself, where it is built
code: framework/runner/report.py, framework/schema/report.toml, framework/plot/figures/typeset.py
---

# Reports

A **report** is a quick, informal account of Runs' pages and numbers, the kind you send a colleague after a job: one A4 PDF, a page to browse, and every figure in its own folder. It is made only when you ask. Every key: [report settings](../../reference/settings/report.md).

```bash
heimdall report Demo/validation/02_pdf          # its report.toml: what its config asks for
heimdall report Demo/validation                           # the default report of the errand's Runs
heimdall report Demo/weekly.toml                               # a recipe of its own, over its from
heimdall report Demo/weekly.toml 'Demo/validation/0[2-4]_*' # the recipe over other sources
heimdall report Demo/validation/02_pdf --list   # what it would hold; nothing written
heimdall report Demo/weekly.toml --init Demo/validation/02_pdf   # write that recipe, once
```

A recipe is always named with its `.toml`; anything else is a source.

| File | What it is |
|---|---|
| `report.pdf` | a front page (sources, where they came from, flags) and contents; what was run; how the numbers are made; the results |
| `report.tex` | its LaTeX, naming only files in the folder: it compiles there, or on Overleaf |
| `figures/` | every page it shows, as PDF and PNG, with its curves' bins as CSV |
| `stats/` | the numbers of the statistics it shows, typeset in the report |
| `tools/` | what each tool was given: `<tag>.baseline.<ext>`, `<tag>.varied.csv` |
| `index.html` | the same to browse, its sources up front |

A rebuild makes only what changed, and removes what no section shows any more. Up front, for each source: its address, configuration, when drawn and by which Heimdall, points complete of all, events, what it is compared against. It flags incomplete points, and points newer than their pages.

## Where it is built

`reports/` mirrors `results/`: one Run's in `reports/<A>/<E>/<R>/`, an errand's in `reports/<A>/<E>/`, several errands' where their addresses meet. `output` or `-o DIR` builds elsewhere, never into `results/`; sources of two assignments need one.

**The default report**, of a folder with no `report.toml` and of several sources, holds a Tools section; the statistics' headline on the first set measured; then the pages of every set the sources draw. A scan of many points makes many pages: `--list` says how many.

## A recipe

```toml
# configs/Demo/weekly.toml
[report]
title    = "ZEUS photoproduction: {configuration}"
subtitle = "for the group, 30 Oct 2026"
from     = ["Demo/validation/02_pdf"]

[[report.section]]
title = "Standings"
stats = ["top5", "ratio_dev"]

[[report.section]]
title = "Spectra"
pages = ["d01-*", "d02-*"]

[[report.section]]
title  = "Run by run"
from   = ["Demo/validation/0[2-4]_pdf"]
pages  = ["d01-x01-y01"]
layout = "sources"
```

A section shows one kind of item:

- **`pages`:** globs of a set's page names. `layout = "pages"` shows each source's in turn; `"sources"` side by side, a panel per source, labelled by folder or `label = "events"`.
- **`compare`:** a compare figure's pages.
- **`stats`:** parts of the summary (`top5`, `scoreboard`, `head-to-head`, `chi2_ndf`, or `chi2_ndf:ranking`, `:crossed`, `:table`).
- **`bars`:** globs of page names, each page's bar graph.
- **`files`:** your own PDF or PNG files, relative to the recipe.
- **`tools`:** tool tags or globs, `"*"` every tool given a card or options; `hide` leaves varied lines out by key.
- **`optional = true`:** a source that neither has the set nor can draw it is passed over.
- **`plot = { … }`:** `[plot]` keys over each source's own, so that section is drawn for the report.

`{assignment}`, `{errand}`, `{configuration}`, `{title}` in a title are filled in. Sources on the command line replace `[report].from`, so one recipe serves many Runs. Refused: a set a source neither drew nor can draw, a glob naming nothing, two side-by-side panels of one label, an unknown key.

**What the tools were given** is read from the source's records, never today's `configs/`: the card lines every point had, its options, and what varied point by point. A point whose record is gone is named, not guessed.

**The errand file's own.** Its `[report]` says what its Runs' reports show, and `template` names a shared recipe its keys are laid over. Each time a job writes a Run's `plot.toml`, it writes `report.toml` beside it, rewritten from the config every time. To change a Run's report, change the config, or copy `report.toml` into `configs/` as a recipe.

## Drawn for itself

A report draws, with the same code, when a source has not drawn a set a section shows, drew it as PNG alone, has not measured the numbers shown, or a section has `plot = { … }`:

```toml
[[report.section]]
title = "Shapes"
set   = "all_few"
pages = ["d0[1-4]-*"]
plot  = { normalise = "area" }
```

It goes to `.cache/<A>/reports/<its place>/.drawn/…`. **The source is only read.** It is done again only when the source, the section's keys or the drawing's code changed. `--list` and the front page say what was drawn and why.

## What comes first

Tools sections come first, then **How the numbers are made**, whenever it shows statistics: how a page is compared, a paragraph per statistic with its formula, how points are scored. Then every other section in the recipe's order. `context = "last"` moves these to an appendix, and `method = false` drops the second, each statistics part then keeping its own notes.

## Its look

Set once in `report.tex`'s preamble: TeX Gyre Heros, Latin Modern Typewriter for code, A4, a running header, sections starting a page. `[report]` changes a little: `font = "serif"`, `size`, `accent`, `columns`, `contents = false`.

A report is not a talk or a paper. Take what it made into your own tools: vector PDFs from `figures/`, numbers from `stats/`, `report.tex` as a start.
