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
