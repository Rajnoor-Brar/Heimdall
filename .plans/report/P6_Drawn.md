# P6: drawn for itself (V211)

[00_Plan.md](00_Plan.md) §2 P6, N3, N4, N8. A report no longer needs what plot and stats left on disk.

## Tasks

- **Loaded for the report.** A source whose plan has *drawn* entries is loaded with
  `plotdoc.load(path, folders=RunFolders(project, cache/"records", cache/"results", cache/"work"))`
  (P1), where `cache = .cache/<P>/reports/<name>/<NN>_<source>/`.
  - Its `[plot]` gets the section's `plot` keys laid over it in memory.
  - `formats` holds pdf and png.
  - `draw` is limited to the sets the report needs, a section's own set included.
- **Drawn:** `plot.draw(doc, configuration, members, say)` for missing pages and for sections with `plot`.
- **Measured:** `plot.measure` for numbers no `statistics.csv` holds.
- **Then:** what they made is copied into `figures/` and `stats/` as in P3. A failure names its log (V204's
  `logs/plot/`, under the cache folder).
- **Bar images (`bars`):** built at P3 from `statistics.csv` (`report._bars`); here only from numbers measured for
  the report, when a source has no `statistics.csv`.
- **`resolve`:** *drawn* entries are allowed now; `--list` says which are drawn and why.

## Verification

- **New `tests/integration/test_report_draw.py`** (slow; on a fixture run's result folder):
  - a section with `plot = { normalise = "area" }` drawn for the report;
  - a set no run drew;
  - numbers measured when there is no `statistics.csv`;
  - a bar image from numbers measured for the report;
  - the source's `results/` and `records/` byte for byte unchanged (a tree hash before and after).
- **On real results:** a section with `plot = { normalise = "area" }` over Brookhaven's
  `eic/zeus_validation/02_generator_pdf`, with `HEP_CACHE` and `HEP_REPORTS` in the scratchpad.
  Brookhaven's `results/` and `records/` must have the same tree hash before and after.
- The slow suite once (its baseline plus the new test); `test_docs`.

## Log

- 2026-10-27: done (V211), in the worktree, branch `report`.
  - **Readings taken while building it:**
    - **Two passes.** A drawn set's page names are known only once drawn, so `resolve` gives a waiting grid (a
      figure with no file) and waiting numbers (no CSV) and asks for a `Drawing`, one per source and look; the
      build draws, then resolves the waiting sections again (`_settle`).
    - **What can be drawn** (`Source.drawable`): the totality or a set of the document's `[plot].sets` (the look's
      too), and a complete point with its YODA. An optional set whose drawing gives no page (Sherpa's sets where
      Sherpa failed) is left out after drawing, and said: the drawing costs the sweep's merge once.
    - **PNG alone is drawn again** as PDF when the source can draw it (N3's vector pages); else its PNGs are shown.
    - **Where:** `.cache/<P>/reports/<the report's place, <P> left out>/.drawn/<address slug>[-<look hash>]/`, not
      `<NN>_<source>/`: a run's report and its configurations' nest, so each keeps a `.drawn/` of its own and
      removes there what no section asks for. A drawing is stamped (`drawn.key`: the document, the points' YODAs,
      the look, the sets, Paint and the plot code) and written only when nothing failed.
    - **A look** adds its `sets` and `figures` to the document's and lays its `style` over; other keys replace.
      `plot` is refused on a compare, files or tools section. `[stats]` keys the look sets are dropped, so the look
      decides the numbers too.
    - **Drawn with `stats=False`, then measured** (`plot.measure(…, picked=)`), so only the sets wanted are
      measured; compare, sheet and statistic figures are left out of the drawing.
    - `allow_drawn` is gone; a refusal names the sets drawn there and the document's.
  - **Tests:** test_report (22; 2 new, 2 changed), test_report_build unchanged, the new slow
    `tests/integration/test_report_draw.py` (2: a folder never drawn, its trees hashed before and after, a rebuild
    drawing nothing; a look, its numbers' areas one, its bar graphs, a set of a section's own, PNG alone drawn
    again); 111 passed across report, report_build, report_draw, imports, docs, config, house. The slow suite runs
    once at P7.
  - **On Brookhaven, read-only** (`scratchpad/p6live/`, `HEP_CACHE` and `HEP_REPORTS` there): `09_generator_pdf`
    (its set folders empty): the default report drew 48 pages in 4 sets, left Sherpa's two out, 21 A4 pages in
    25 s (Matplotlib's font cache first), a rebuild 0.16 s; `area.toml` over `02_generator_pdf` with
    `normalise = "area"` on `all_few`: 12 pages drawn, 72 curves measured, every area ratio one, 9 A4 pages in
    12.5 s. `results/` and `records/` listed the same before and after; `git status` clean.
