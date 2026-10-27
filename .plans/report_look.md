# A report's look, native statistics, and its data (I-110)

Asked by the user on 2026-10-27, after I-108 and I-109:
- "Make reports/ a standard workdir folder and gitignored";
- line spacing in notes; for a set's graphs, one sub-header for the unvaried quantities and the set's axes;
  spacing between the page header and the contents, table rows, etc.;
- figures and statistics "do not have them exist in report like view into external file, have it be in report
  natively"; CSV or other data files beside them "to avoid extraction of data from pdfs"; failing that, renders
  that match the report's styling;
- `Brookhaven/configs/eic/zeus_report.toml`, the best configuration (aesthetics, sets and plots chosen) with the
  settings worth knowing commented out;
- syntax highlighting for code blocks; standard fonts and sizes, bold and italic rules, spacing and padding of
  pages, body, tables, figure grids, and the placement of titles, subtitles, taglines and labels: a uniform look.

The execution map is §4; each phase's log is §5. Built in the worktree `scratchpad/heimdall-look`, branch `look`
(from main at `bb2ec49`); main fast-forwarded at the end. **Pause at the end:** the Brookhaven report's PDF sent.

## 1. What is there (main at `bb2ec49`)

- **`reports/`**: `heimdall setup` makes it (`setup.FOLDERS`); the work template ignores `reports/*` under the
  datasets comment, apart from the run's other outputs (`build/`, `records/`, `.cache/`, `results/`).
- **The report's look**: `report.tex` is `article` 10pt, Latin Modern sans, 15 mm margins, no running header or
  footer but the page number; section titles LaTeX's defaults; grid captions `\small` lines; the front page a
  `tabular` with `\hline`. The statistics are the summary's own A4 pages (`paper.write`), included whole with
  `\includegraphics[page=…]`: their running headers, footnotes and "page n of N" inside the report's pages, their
  font Matplotlib's DejaVu Sans. The bar graphs are `bars.page`'s images. A tool's card is plain `Verbatim`.
- **What the run knows of a set** (its plot document): `[axes]` (`vary`, `plot_points`, `fixed` as `#N`),
  `[quantities.<q>].points` (tag, value, label: LaTeX), `[plot].sets.<name>` (`pages`, `curves`: a table of axis
  → `"all"` or tags, or a list of such tables; or `points`).
- **What can be typeset natively**: the statistics are a model (`paper.Document`: sections of `Table`, `Ranking`
  and `Text` items, each `Row` of `Cell`s with a fill, an ink and bold, notes by key), already rendered twice
  (`paper.figure`, Matplotlib; `webpage.render`, HTML). A third renderer, LaTeX, puts them in the report as
  text: its fonts, its spacing, its page breaks (`longtable`).
- **The data behind a figure**: its page document (`.cache/…/<set>/<cell>/<object>.toml`) names each curve's
  member and object; the member's YODA is in `results/`; YODA's Python reads it (the stack's).
- **TeX here**: `tgheros` (TeX Gyre Heros, Helvetica's metrics: Paint's pages are Helvetica too), `tgtermes`,
  `titlesec`, `fancyhdr`, `lastpage`, `booktabs`, `colortbl`, `xcolor`, `enumitem`, `microtype`, `fvextra`,
  `longtable`; no Inconsolata or Bera Mono (Latin Modern's typewriter stays).

## 2. Decided

- **R1 `reports/`, a run's output like the others:** the template's `.gitignore` lists `reports/` in its first
  block (what the runner and the build make), the README's table says so; `heimdall setup` already makes it.
  A work dir's `.gitignore` block takes it at `setup . --refresh` (its marked block is merged).
- **R2 One look (a design system in `report.tex`'s preamble, its values in one place, `report.LOOK`):**
  - **Fonts:** TeX Gyre Heros for everything set in text (titles, body, tables, labels), Latin Modern
    Typewriter for code, addresses and keys; math in the same sans (`sansmath`). `[report].font = "serif"`
    takes TeX Gyre Termes for the body.
  - **Sizes (pt, line):** title 22/26, subtitle 12.5/16, tagline 8/10.5; section 15/18, subsection 11/14,
    item title 9.5/12; body 9.5/13.5 (`[report].size` scales it: 9, 9.5, 10.5); a set's sub-header and grid
    captions 8.5/11.5; table text 8/10.5; panel labels and notes 7.5/10.5; code 7.5/9.5; header and footer 7.5.
  - **Weight and slant:** bold for titles, table headers, row labels of totals (a pinned or bold row) and
    keys in code; italic only for notes' lead words, flags and "nothing to show" lines; never underlined.
  - **Colour:** ink `#0b0b0b`, muted `#52514e` (taglines, captions, labels, notes), rules `#e4e3df`, bands
    `#efeeea`, the accent (section numbers, ranking bars, links, code keys) `#2a78d6`, `[report].accent` its own.
  - **The page:** A4, 18 mm left and right, 22 mm top (a running header: the report's title left, the section
    right, a rule under them, 7 mm above the body), 20 mm bottom (the footer: "page n of N", centred, muted).
  - **Spacing:** a section starts a page; its title, then 6 pt, its note (muted, 1.35 line spacing), then 10 pt;
    a set's sub-header, 4 pt, its grids; 14 pt between grids, 4 pt between a grid's caption and its panels,
    6 pt between panels; tables with `booktabs` rules in the rule colour, rows 1.35 high, 5 pt cell padding.
  - **The front page:** the title, the subtitle, the tagline (what made it, when, which Heimdall); the sources
    table (`booktabs`); flags as a muted list; what was drawn for the report; the contents.
- **R3 A set's sub-header** (once per source and set in a pages section): the set's name, then
  *Pages* (its page axes and their values, as labels), *Curves* (its curve axes: the labels when eight or fewer,
  else their count), *Fixed* (each quantity the configuration does not vary, as its label). Each grid's caption
  is then its page cell as labels (`Pythia 8.318`), not its tags.
- **R4 Code highlighted** (a tool's card, its varied lines): comments muted italic; keys bold in the accent;
  `=` and `:` muted; numbers and booleans their own colours; text as it is. Done in Python into `Verbatim`
  with `commandchars` (no `minted`, no shell escape); long lines still break; `index.html` the same in spans.
- **R5 Statistics typeset, not included** (`framework/plot/figures/typeset.py`, a third renderer of
  `paper.Document`): an item's title with its notes' numbers; a table as `longtable` column blocks that fit the
  text width (measured as `paper.width` measures), its bands and fills (the shading) and bold kept, a total row
  after a rule; a ranking as a table of bars drawn with rules, from 0 or both ways from its base, cut and
  coloured as V205's; the facts up front, the notes numbered at the part's end. **Bar graphs** (a `bars`
  section) become a table a page: a row a curve, a column a statistic, each a small bar and its value. No
  Matplotlib image is left in the report but the figures themselves.
- **R6 The data beside what is shown:** `stats/…/<MM>_<source>__<set>.csv` (the source's `statistics.csv`, or the
  report's own measurement), `stats/…/<page>.csv` for a bar table; `figures/…/<stem>.csv` for a figure whose
  page document is at hand: each curve's bins as the run made them (`curve`, `label`, `xlow`, `xhigh`, `y`,
  `err_down`, `err_up`), read by YODA's Python; a figure without one (or without YODA) has none, and `--list`
  says how many.
- **R7 `[report]`'s look keys:** `accent` (a `#rrggbb`), `font` (`"sans"`, `"serif"`), `size` (9, 9.5, 10.5:
  the body's pt), `contents` (true: a table of contents), `columns` (a grid's default columns: 1–4).
- **R8 `Brookhaven/configs/eic/zeus_report.toml`**: a recipe of its own over `eic/zeus_validation/02_generator_pdf`,
  built into `reports/eic/zeus_report/` (`output`): the standings; the spectra of both generators' chosen PDFs
  (`all_few`), then E_T in η ranges and η in E_T ranges per generator; the statistics' rankings and
  head-to-head; bar tables of the headline pages; the tools (seeds hidden); every other key there, commented.

## 3. Phases

| Phase | What | V-row |
|---|---|---|
| R1 | `reports/` in the template's first block; README and docs | V214 |
| R2 | the look (R2–R4, R7): preamble, macros, front page, sub-headers, captions, highlighting, `[report]`'s look keys; tests; docs | V215 |
| R3 | statistics and bars typeset (R5), the data files (R6); tests; docs | V216 |
| R4 | Brookhaven's `zeus_report.toml` (R8), built read-only into the scratchpad; the suites; main fast-forwarded | — |

## 4. Execution map

| Phase | V-row | Commit | State |
|---|---|---|---|
| R0 this plan, I-110 | — | (with R1) | written |
| R1 `reports/` | V214 | | done |

## 5. Log

- 2026-10-27, **R1** (V214): the template's `.gitignore` takes `reports/` in its first block; 02 §1 says so.
