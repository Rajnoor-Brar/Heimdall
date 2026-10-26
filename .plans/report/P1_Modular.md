# P1: plot and stats made modular (V206)

[00_Plan.md](00_Plan.md) §2 P1, Q5. Only what the report shares is reorganised. Every command's output is
unchanged: `heimdall plot`, `heimdall stats`, a run's plot stage and `heimdall overlay` make the same files,
with the same bytes and the same messages. **Pause for compaction after this phase.**

## Tasks

- **`framework/runner/statstable.py`** (new, rank 4): the statistics table, moved out of `plot.py`.
  - **Moved as they are:** `STATISTIC_COLUMNS`, `statistics_of(page)`, `write_statistics(todo, target)`,
    `heading_of(numbers)`. `plot.py` imports them, so `plot.statistics_of` and `plot.heading_of` still
    resolve (`tests/integration/test_plot_stage.py` uses both).
  - **A set's numbers written:** `write_set(pages, numbers, formats) -> (rows, images)`. That is the body of
    `plot._tables`' loop: the CSV, then `bars.draw` with the summary. `plot._tables` keeps the clearing
    (`_clear`, which guards `results/`) and the message.
  - **New `read(path) -> list[dict]`:** `statistics.csv` back into rows typed as `statistics_of` gives them:
    the texts as str, `is_reference` as bool, `bins` and `ndf` as int, the rest as float, "" as NaN.
  - **The bars loader:** `bars()`, `plugins.load` of `framework/plot/figures/bars.py`, used by `plot` and later
    the report.
- **`framework/plot/figures/paper.py`: `write(document, target, formats, title, plt) -> list[Path]`.** This is
  the page loop of `bars.summary_of`: `target`.pdf through PdfPages (metadata Title), a PNG or SVG per page in
  the folder `target`, `facecolor=SURFACE`, each figure closed. `bars.summary_of` keeps the model and the HTML
  and calls it.
- **`framework/plot/figures/layout.py`: one LaTeX placer.** `_draw` is split into:
  - `picture(panels, box, columns, rows, cw, ch, label, title, title_h, gap, names)`: the `picture`
    environment's lines (cells, `\includegraphics` keeping aspect, labels, the title, `tex()`);
  - `compile(source, target, files)`: pdflatex in a scratch folder with the files linked in, its error the
    log's first `!` line.

  `composite` and `tile` call both, with their signatures unchanged. P3's `report.tex` uses `picture` per grid.
- **`plotdoc.load(path, folders=None)`.** With `folders` (a `RunFolders`), the members draw into them: pages,
  numbers, working files and failure logs. Each member's YODA and completeness are still read from the
  document's own folders (its `results/` and `records/`), so nothing is written there. With nothing passed,
  it behaves as today.

## Verification

- **New `tests/runner/test_statstable.py`:**
  - rows written and read back equal, NaN, bool and int included;
  - `write_set` writes the CSV, the bar images and the summary as `_tables` did.
- **`tests/runner/test_plotdoc_folders.py`** (or a case in an existing plotdoc test): a document loaded with
  other folders keeps its members' YODAs and completeness from its own.
- **Unchanged and passing:** `test_summary_layout`, `test_layout`, `test_plot_logs`, `test_deck_build`,
  `test_imports` (with `statstable`'s rank) and `test_docs`.
- **Gate P:** `scratchpad/gateP.py`, before (on main, at P0) and after.
  - **Its inputs:** two of Brookhaven's result folders, `eic/zeus_validation/01_pythia_qed_lepton` and
    `02_generator_pdf`.
  - **For each:** its `plot.toml` copied into the scratchpad with the YODAs named by absolute path. One copy
    is drawn with `heimdall plot <copy>`, the other measured with `heimdall stats <copy>`. `HEP_CACHE`,
    `HEP_REPORTS` and `HEP_RUNS` are in the scratchpad.
  - **Compared:**
    - the list of files made;
    - `statistics.csv`, `summary.html` and the `index.html` files, byte for byte;
    - PNGs byte for byte (pixel for pixel where bytes differ);
    - PDFs by page count and page size.
- **Slow suite once:** 42 pass, 5 known failures (I-09 ×2, I-79 ×2, I-43).
- **Brookhaven:** `git status` and a tree hash of `results/` and `records/`, unchanged.

## Log

- 2026-10-26: done (V206), in the worktree `scratchpad/heimdall-report`, branch `report`.
  - **`framework/runner/statstable.py`** (rank 4): `STATISTIC_COLUMNS`, `statistics_of`, `write_statistics`,
    `heading_of` moved as they were (plot.py imports and so names them still), `write_set` (`plot._tables`' loop
    body: the CSV, then `bars.draw`; `_tables` keeps `_clear`, the bars module loaded once and the message), `read`
    (the CSV's rows typed back), `bars()`.
  - **`paper.write(document, target, formats, title, plt)`:** `bars.summary_of`'s page loop; `summary_of` keeps
    the model and the HTML.
  - **`layout.picture(files, labels, box, …)`** (a grid's `picture` lines) and **`layout.pdflatex(source, what,
    runs)`** (pdflatex in the source's folder, the log's first `!` line): `_draw` calls both; `composite` and
    `tile` unchanged.
  - **`plotdoc.load(path, folders=None)`** (and `load_across(path, data, into)`): members draw into `folders`, their
    YODA and `.complete` still read from the document's own (`own`).
  - **Tests:** `tests/runner/test_statstable.py` (3: the CSV round trip, plot's names, `write_set`);
    `test_snapshot.py::test_a_document_loaded_into_other_folders_reads_its_own_and_draws_there`. A first version
    of it left `HEP_CONFIGS` at the record's snapshot (`cli.opened` sets it), which failed a later
    `test_docs` case in the same session; it restores it now, as its neighbour does.
  - **Docs:** 06 §2.1 (`statstable.py`), 07 V206.
  - **Gate P (`scratchpad/gateP.py`), passed.** Brookhaven's `eic/zeus_validation/02_generator_pdf` and
    `01_pythia_qed_lepton`, drawn (`heimdall plot`) and measured (`heimdall stats`) from copies of their documents,
    by main's code (9028970) and then the refactor's: 5070 files the same (PNGs, CSVs and HTML byte for byte, PDFs by
    pages and sizes), the same exits and messages, 8.5 minutes each. A first run, both tags from the worktree, differed
    only in the summaries: their heading is a folder's last two parts outside results/, and the copies sat in
    `gateP/before/` and `gateP/after/`; the copies now sit at `gateP/<tag>/cases/`. Brookhaven's `results/` and
    `records/` trees (path, size, mtime) and its `git status` unchanged.
  - **Suites:** fast 1069 passed, 1 failed (`test_stack_build.py::test_the_old_way_is_apt_and_a_venv`, failing on
    main too); slow 42 passed, the 5 known failures (I-09 ×2, I-79 ×2, I-43). `test_deck_build` failed once in a
    selection on dzslides' Google font (I-78) and passed alone.
  - **P2 drafted meanwhile** (not in this commit): `scratchpad/p2_patch.py`, `scratchpad/p2/` (`report.py`,
    `report.toml`, `test_report.py`), its 7 tests passing in a scratch copy (`scratchpad/p2check`).
