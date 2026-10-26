# P5: the tools' configurations (V210)

[00_Plan.md](00_Plan.md) §1.7 (A7–A9), by the user's word. Pages of what each tool was given: the baseline
every reported point shares, and what varied point by point. **Pause for compaction after this phase.**

## Tasks

- **Read from the records, never from today's `configs/`.**
  - A point's folder is its member's `folders.record / "logs" / <point>` (P1's `RunFolders`).
  - Its tools are its `context.toml`'s `[tools.<tag>]`; a tool's card is that table's `card`, read from
    `cards/`. Its other keys, all but `tool`, `card` and `card_parts`, are its options.
  - Without `context.toml` (an older record): `cards/<tag>.*`, its `.point.` and `.json` files left out.
  - A point with no record folder, or a card that is not text, is said, not guessed.
- **`report.py`:**
  - `tools` as a section item (`schema/report.toml`: `section.tools`, `section.hide`; `report.tools`);
    `config.check_report` takes it.
  - The plan's `Tools` entries: a source, its tags matched (globs, natural order), its complete points.
- **The two halves, generic (no tool named):**
  - **The baseline:** the first point's lines that every point has, in its order.
  - **The varied options:** each point's other lines, comments (`#`, `!`) left out, `hide` globs applied to
    a line's key, else to the line.
    - All `key = value` or `key: value` lines, each key once a point: a table, a row per point (its label
      from the plot document, as its curve's), a column per key in first-seen order, "—" where a point has
      none.
    - Else a list per point.
- **The default report** (A8): a "Tools" section at its end, `tools = [report].tools` (else `["*"]`, every
  tool given a card or options). `report.toml` writes it out (P4's default), so it can be edited.
- **The build** (A9):
  - files: `tools/<NN>_<section>/<MM>_<source>/<tag>.baseline.<ext>` (the card's own extension) and
    `<tag>.varied.csv`, stamped as the rest;
  - `report.tex`: per source, per tool, a subsection; the options as a list; the baseline by
    `\lstinputlisting` (`listings`: monospace, `breaklines`, small); the varied table in `longtable`s of at most
    about six key columns each, the point column repeated;
  - `index.html`: a block per tool and source, the baseline in `<pre>` and the table as HTML (`viewer.Shown`
    takes HTML for a block that has no panels).
- **`execute`/`tools`:** `context.toml`'s header made true: it is kept when the point ends.

## Verification

- **`tests/runner/test_report.py`:**
  - the baseline and varied split on two synthetic points' cards: a cmnd-like card (a table), a YAML-like card
    with a nested block (a list per point);
  - `hide`;
  - comments;
  - a point with no record;
  - the default report's Tools section;
  - `[report].tools = []`.
- **`tests/runner/test_report_build.py`:** the tools' files in `tools/`, `report.tex` compiling (`listings`,
  `longtable`), `index.html`'s text block.
- **On Brookhaven, read-only:** the report of `eic/zeus_validation/02_generator_pdf`.
  - Pythia: baseline `zeus.cmnd`'s lines; varied `PDF:pSet` and `Random:seed`.
  - Sherpa: baseline the YAML; varied `PDF_SET`, `MPI_PDF_SET`, `RANDOM_SEED`.
  - Rivet: its analyses.

  Viewed, and sent to the user with P4's run report. Brookhaven untouched.
- `test_docs`, `test_imports`.
- **Docs:** 03 §11 (a report's tools' pages), 04 §15 (`tools`, `hide`, `[report].tools`), 06 §14 (`tools/`),
  07 V210.

## Log

- 2026-10-27: done (V210), in the worktree, branch `report`.
  - **Readings taken while building it:**
    - **fvextra, not listings.** `listings` reads no UTF-8 under pdflatex, and fvextra's `breakanywhere` splits a
      UTF-8 character (a test card with `±`, `→`, `€`, `≤` and a snowman stopped pdflatex); `breaklines` with
      `breakafter={/_:=,.-}` breaks long lines and takes any character. Characters outside Latin-1, Latin
      Extended-A and a few symbols are declared as `?` in the preamble, so a card never stops the report.
    - **A module's `config`** is its card (read from `config/`), and `config` is not among its options.
    - **Options that varied** join the varied lines as `key = <TOML value>`, so they are columns of the table.
    - **Tools in natural order** within a glob, globs in their order; `"*"` takes only tools given a card or
      options (yd2rt is not shown), a name takes its tool even when it was given nothing, and says so.
    - **Row labels** are the curve's labels as plain text (`plain`: `$e^{+}p$` → `e+p`); the CSV has the
      point's name too.
    - The name `given` for the reader shadowed `resolve`'s argument: it is `configured`.
  - **Tests:** test_report (17; 3 new), test_report_build (8; 1 new: the files, the PDF's text, a copy of the
    folder compiling alone, a rebuild writing nothing); test_plot_stage's report.toml with its Tools section;
    213 passed across report, report_build, docs, imports, config, v3, house, one_cli, snapshot, context, deck,
    deck_build, layout, statstable, summary_layout.
  - **The fast suite:** 1098 passed, 10 skipped; 1 failed, `test_stack_build::test_the_old_way_is_apt_and_a_venv`,
    the failure P1's run had too (the pixi base's python named in a `base=system` script), not the report's.
  - **On Brookhaven, read-only** (`scratchpad/p4live/`): `heimdall report eic/zeus_validation/02_generator_pdf`
    (no `report.toml` there: the default), 31 A4 pages in 3.4 s; its Tools section as the plan expected (Pythia:
    `PDF:pSet`, `Random:seed`; Sherpa: `PDF_SET`, `MPI_PDF_SET`, `RANDOM_SEED`; Rivet: its analyses); nothing in
    Brookhaven newer, `git status` clean.
