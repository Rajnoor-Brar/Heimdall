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
