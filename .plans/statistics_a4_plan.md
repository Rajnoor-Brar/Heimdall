# Plan: statistics on A4, and better organised (2026-10-26)

Issue: [I-107](ISSUES.md#i-107-statistics-on-a4-and-better-organised). Approved 2026-10-26.

## Execution map

| Step | State | Commit | V-row |
| --- | --- | --- | --- |
| S1 A4 pages | done | `c3a06d6` | V196 |
| S2 What the summary holds, reorganised | done | (this commit; hash in the next) | V197 |
| S3 Cell × curve tables | to do | | |
| S4 summary.html | to do | | |

## Context

The statistics PDFs size each page to its content, so the pages vary widely. In zeus_validation they range
from 8 to 37.5 inches wide and from 1.8 to 25 inches tall:
- The top-five page is one 37.5 × 2 in table: 7 columns, each cell a full point name.
- The χ² and scoreboard tables are 14–17 in wide, since the label "NNPDF40nnlo_hessian_pdfas_lpdfoff · lepton QED
  shower off" takes half the width.
- 01_pythia_qed_lepton's totality has 70 pages, 38 of them a 2×2 head-to-head table each.
- A ranking of 76 points is 8 × 24.8 in.
- Each page repeats a footnote of up to 6 lines.
- Each per-page bar image (`bars/<cell>/<object>`) is 18.5 in wide.

Typical data: 12 objects; 19–76 points; 1–38 page cells; labels up to 57 characters; curve-axis sweeps
(pdf × QED shower × lepton PDF).

**Decided (2026-10-26):**
- **Page size:** every statistics page is A4 portrait. A too-wide table is cut into column blocks, stacked one
  below the other on the same page.
- **Top five:** each column (a scoreboard) becomes its own table.
- **New:** cell × curve tables; rows grouped by cell; a notes and contents page.
- **Small tables share a page** within their section.
- **HTML:** a `summary.html` is added in this plan.

## Where and how

**Where.** The work is built in the worktree, branch `logging`:
`scratchpad/heimdall-logging`, after L1 and the history commit. The live run (pid 1265398) uses main's checkout,
and its plot stage loads `bars.py` from there when it ends. Main is fast-forwarded later, as before.

**Pace.** Step by step, as for the logging plan:
1. build;
2. test (light, one session);
3. commit by named paths with the step's V-row (the next free number);
4. report, then wait for your word.

**Paperwork.** On approval this plan is copied to `.plans/statistics_a4_plan.md`. `.plans/ISSUES.md` gets
**I-107** "Statistics on A4", linking it, in the index and under M5. The CLAUDE.md `.plans/` row names the file.

## The design: one model, two renderers

`framework/plot/figures/bars.py` keeps the numbers: means, places, points, head to head, and the per-page bar
image. It stops drawing tables itself. Instead it builds a **document model**: sections of tables and
rankings. The model is pure data, so the tests read it directly instead of matplotlib's cells.

- **New `framework/plot/figures/paper.py`: A4 pages from the model**, generic, with no statistics in it. It is
  loaded by `bars.py` through `runner.plugins.load`, as `bars.py` itself is (I-51 later imports both normally).
  - **The model:** `Cell(text, fill, ink, bold)`, `Row(label, cells, bold, band)`,
    `Table(key, title, subtitle, headers, rows, tail, notes)`, `Ranking(key, title, names, values, counts,
    ratio)`, `Section(key, title, items)`, `Document(heading, facts, notes, sections)`.
  - **Page:** 210 × 297 mm. The margins are 0.5 in at the sides and 0.45 in at the top and bottom.
    - Each page has a running header: the heading, and the section on the right.
    - Each page has a footer: a one-line footnote ("notes 2, 9") on the left, and "page n of N" on the right.
    - The tables use 7 pt text, at about 60 rows a page.
  - **Text is measured, not guessed.** `matplotlib.textpath.TextToPath().get_text_width_height_descent` is
    used, mathtext included, and cached. This replaces `_draw`'s character-count widths.
  - **Column blocks.** These are the label column, the data columns, and the tail (mean, or total, wins, win
    rate, mean rank).
    - When they're wider than the page, the data columns are split evenly into the fewest blocks that fit
      (7 + 6, not 11 + 2).
    - The tail goes with the last block.
    - Each block repeats the row labels.
  - **Row slices.** One page shows a range of complete rows, with all of its column blocks stacked under one
    another. The rows per slice are what fits once the blocks are stacked. A continued table is titled
    "(continued)". A band is never left last on a page: a cell continued on the next page repeats its band.
  - **Flow.** Each section starts a new page. Within a section, tables and rankings follow one below another,
    and a new page starts only when the next one doesn't fit (header plus 3 rows at least). So the 38
    head-to-head tables take about 4 pages.
  - **Labels.** A label wider than half the usable width wraps at its " · ", giving a two-line row.
  - **Drawing.** Tables are drawn with rectangles and text in inch coordinates (`fig.dpi_scale_trans`), not
    `ax.table`, because spanning bands and exact widths need it.
  - **Rankings** are drawn as bars, about 55 a page, continued like tables.
  - **Two passes.** `pages(document)` plans every page first: the front matter, then the sections. The
    contents' page numbers and "of N" are then known. `figure(page, plt)` then draws one page at a time,
    written and closed before the next, as now.
- **`bars.summary_of(rows, target, formats, heading)`.** `summary.pdf` (with `PdfPages` metadata: its title)
  and `summary/summary_NN.<fmt>` are written as now, every page A4.
- **`runner/plot.py` `_tables`** passes the `heading`: the run folder's path under `results/` (else its last
  two parts) and the set, for example "eic/zeus_validation/01_pythia_qed_lepton · qed_lepton_by_pdf".

## Steps

### S1 A4 pages (V-row: "Statistics on A4")

- **New `paper.py`,** as above. `bars.py` builds the model from today's content:
  - the top five in today's shape for now;
  - the scoreboards, by cell and by statistic;
  - head to head;
  - the rankings and the tables.

  `_draw`, `table_figures`, `standings_figures`, `summary_figures` and `ranking_figure` give way to
  `summary_model(rows, heading)`.
- **The per-page bar image `bars.page`** becomes A4 portrait, with the six panels in a grid.
  - The grid is chosen for the most height per bar with every panel at least 1.4 in wide: 2 × 3 up to about 18
    curves, 3 × 2 up to about 30, 6 × 1 beyond.
  - With more curves than 0.12 in a bar allows, the PDF continues on further pages (`<object>_NN.png`).
- **Tests:**
  - **New `tests/runner/test_summary_layout.py`.** It uses a synthetic worst case shaped like
    01_pythia_qed_lepton: 76 points, 38 cells, 12 objects and 57-character labels, built in the test with no
    real work dir. It checks that:
    - every page is 8.27 × 11.69 in;
    - every drawn text's extent lies within the page's margins (`fig.canvas.draw()`, `get_window_extent`);
    - a 16-column table becomes stacked blocks on one page, with the tail on the last;
    - a slice holds complete rows;
    - a band is never last;
    - the 38 head-to-head tables take at most 5 pages;
    - each section starts a page;
    - the footer says "page n of N".
  - **`tests/integration/test_plot_stage.py::test_the_summary_pdf_holds_a_table_a_statistic`** is rewritten
    against the model. The same facts are asserted: scoring, matches, means, "ref", the natural order and the
    notes. The 13-column page cut becomes "17 objects: one table, two stacked blocks"; the page count follows.
- **Docs:**
  - 03_Plots "As bar graphs" and "The summary" (A4, blocks, sections);
  - 06_Internals §layout line 840 (`paper.py`);
  - the 07_Record row.

### S2 What the summary holds, reorganised (V-row)

- **The top five as separate tables,** one per scoreboard (all five, χ²/ndf, |Δ|/reference, area/reference, mean
  ratio, mean |ratio − 1|), stacked:
  - place ("=2" when shared), point, points, wins;
  - head to head: place, point, win rate, matches.

  Seven tables of 5 rows fit one page.
- **Rows grouped by cell** in the tables in curve order: each statistic's object table, and the scoreboard by
  page cell. A cell's name becomes a shaded band across the table, and its rows are labelled by the curve
  alone (with the place, on the scoreboard by cell).
  - The sorted scoreboards and rankings keep "cell · curve".
  - With one cell, or none, there are no bands.
- **A front page: facts, contents, notes.**
  - **Facts:** the heading, then the points, objects, pages, cells and references. It also says whether only
    pages against data were counted.
  - **Contents:** each section and table with its page.
  - **Notes, numbered and written once:** each statistic's `NOTES`, `COMPARED`, the table conventions
    (`TABLE_NOTE`: ref, –, the mean), `SCORE_NOTE`, `H2H_NOTE`, and "points of different cells never meet".
  - **Each page's footnote** becomes one line naming its notes. A table's shading rule stays its subtitle.
- **Tests:**
  - the top five's tables and their places;
  - the bands and the labels under them;
  - the contents' page numbers match where each section landed;
  - each page's footnote is one line.
- **Docs:** 03_Plots, the 07_Record row.

### S3 Cell × curve tables (V-row)

- **Per scored statistic,** in its section after the ranking: page cells against curve labels. Each entry is
  that point's mean over its objects' pages, as the ranking's mean is (geometric for the two ratios).
  - **Orientation:** the longer list runs down the rows. That gives 19 PDFs × the four QED / lepton-PDF
    settings, 38 cells × 2, and 19 PDFs × (py8, sh3).
  - **Means:** a mean column (over curves) and a mean row (over cells).
  - **Bold:** each row's best entry, closest to agreement.
  - **Shading:** the statistic's rule.
  - **"–":** a curve absent from a cell.
  - **Left out:** with one cell, or one curve a cell (the ranking says it all already); when a cell repeats a
    curve label; and for the area (its units differ by object).
- **Tests:**
  - orientation;
  - means (plain and geometric);
  - the bold best;
  - "–";
  - when it's left out.
- **Docs:** 03_Plots, the 07_Record row.

### S4 summary.html (V-row)

- **New `framework/plot/figures/webpage.py`** renders the same model to `statistics/<set>/summary.html`. It is
  always written beside `summary.pdf`.
  - **Self-contained:** inline CSS and about 40 lines of inline JS, with no external library.
  - **The page:** the same sections, contents as anchors, and the notes. Each table scrolls on its own
    (`overflow-x: auto`), with a sticky header row and a sticky label column. There are no column blocks and
    no pages.
  - **Cells:** the PDF's fills and inks.
  - **Rankings:** a table whose cells hold inline bars.
  - **Sorting:** a click on a header sorts the table, numbers as numbers, with "–" and "ref" last. A grouped
    table has one `<tbody>` per cell, so it sorts within each band. The label header restores the original
    order.
  - **Mathtext labels:** the `$` are dropped, Greek letters become their own characters, and `^{…}` / `_{…}`
    become `<sup>` / `<sub>`.
- **`plot.write_sets_index`:** each set's line in `plots/index.html` gains a "statistics" link when
  `../statistics/<set>/summary.html` exists.
- **Tests:**
  - every section and table is present;
  - its anchors match the contents;
  - escaping (`<`, `&` in labels);
  - one `<tbody>` per band;
  - no `http` reference;
  - the index link.
- **Docs:** 03_Plots, 06_Internals line 840, the 07_Record row.

## Verification (each step)

- **Tests:** `taskset -c 0-5 nice -n 10 pytest`, run from the worktree with its `HEP`:
  - the new test files;
  - `tests/integration/test_plot_stage.py -k "summary or statistic"`;
  - `tests/runner/test_docs.py`;
  - then the fast suite once, at S4.
- **On real numbers, read-only.** A scratchpad script (`scratchpad/summary_from_csv.py`) reads
  zeus_validation's `statistics.csv` files: 01_pythia_qed_lepton totality and qed_lepton_by_pdf,
  02_generator_pdf totality and 01_pdf. It calls `bars.summary_of` and `bars.page` into the scratchpad only.
  Then it checks that:
  - every page is 595 × 842 pt (`pdfinfo -l`);
  - the page count against today's: 70 → about 53 for 01_pythia_qed_lepton's totality.

  I view the PNGs and send you the PDFs. Your results folders are not touched. Once main has the change,
  `heimdall stats <folder>` redraws them; that's your call.
- **`git status` clean** in main's checkout. The live run untouched.

## Not in this plan

- The statistic figures' pages (`statistics/<set>/figures/<backend>/`): they are plots, drawn by Paint and the
  backends.
- `statistics.csv`: unchanged.
- PDF bookmarks: matplotlib can't write them, and pypdf isn't in the base. The contents page stands in.
