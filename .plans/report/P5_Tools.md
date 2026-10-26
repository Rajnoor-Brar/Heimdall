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
