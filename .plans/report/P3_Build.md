# P3: the build (V208)

[00_Plan.md](00_Plan.md) §2 P3, N5, N7, Q1, Q3. A report made from what is on disk. **Pause for compaction
after this phase.**

## Tasks

- **`report.build(plan, folder, say)`, into `reports/<P>/<name>/`** (or `-o DIR`).
  1. **`figures/`:** each figure copied as drawn, `figures/<NN>_<section>/<MM>_<source>_<page>.pdf` and
     `.png`. A PNG is rendered by `layout.png` when the page has none. Files are copied only when their
     sha256 changed, and what no section uses any more is removed.
  2. **`stats/`:** per source and its chosen sections, `statstable.read` → `bars.summary_model` → the
     sections kept (their notes and facts with them) → `paper.write` → `stats/<NN>_<source>.pdf`. This is
     redrawn only when its CSV or its sections changed (a `.sha256` stamp).
  3. **`report.tex`:** A4, `article`, `geometry`, `graphicx`, `pdfpages`, `hyperref`, relative paths into the
     folder only.
     - **A front page:** the title and subtitle; Heimdall's revision and when the report was built; a table
       of the sources' facts (N2), with any flags (a failed or missing point, pages older than the points).
     - **`\tableofcontents`.**
     - **Each section:** its title, its note, and its grids, each a `picture` from `layout.picture`, each
       figure an `\includegraphics` of its PDF in `figures/`, with a caption (source · set · cell).
     - **The statistics parts:** `\includepdf[pages=-]` of `stats/…pdf`, each page whole, with its own footer.
  4. **`report.pdf`:** pdflatex twice (the contents), its error from the log.
  5. **`index.html`:** `viewer.page`, a block per grid, its panels the PNGs in `figures/`. Each source's
     `summary.html` is linked from the front facts.
- **`cli.py`:** the build after `resolve`, then each file made, said.

## Verification

- **New `tests/runner/test_report_build.py`** (skipped where pdflatex or pdftoppm is missing):
  - `report.pdf`'s pages are all A4 (`pdfinfo -l`);
  - every path `report.tex` names is inside the folder, and a copy of the folder compiles alone;
  - a second build copies nothing and draws nothing;
  - a changed source page is copied again;
  - a statistics part holds only the chosen sections (its pages' text, by `pdftotext`).
- **On real results, read-only,** with `HEP_REPORTS` (and `HEP_CACHE`) in the scratchpad:
  - the default report of Brookhaven's `eic/zeus_validation/01_pythia_qed_lepton`;
  - a side-by-side recipe (a scratchpad path) over `eic/zeus_validation/0[2-4]_generator_pdf`.

  Checked: A4 pages, the contents' page numbers, every figure in `figures/`, `report.tex` compiling from a
  copy, the time. The PDF is viewed and sent to the user. Brookhaven's `git status` is unchanged.
- `test_docs`; 03 §11 rewritten as "Reports".

## Log
