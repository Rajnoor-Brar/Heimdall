---
id: live-statistics-format
summary: statistics.csv is format 2 with a statistics.json sidecar and the default metrics as columns
affects: plots
issue: I-120
---

**Now holds:** the table is `framework/stats/table.py` (`runner/statstable.py` re-exports it and keeps the bar graphs and the summary). `statistics.csv` has the old `STATISTIC_COLUMNS` first, in their order, then one column for each metric that is on and not already an old column: by default `norm`, `shape`, `tilt`, `worst`. They are computed in Python from the page's `measured` bins and are NaN (empty) for a page whose stats.json has none. `statistics.json` beside the csv holds `format = 2`, the columns, and for each metric column its purpose, direction, thresholds, default flag, note and the reason for the thresholds. A csv with no sidecar is format 1 and reads as before (checked on real studies' csvs, read only). `statstable.write_statistics(pages, target, names)`, `statistics_of(page, names)` take the metric names; `format_of(path)` and `sidecar(path)` read the format.

**No longer holds:** a csv with exactly the 20 old columns. Readers that take a column by name are unaffected.

**Decisions:** the metrics a table carries are the defaults until phase 5's `[stats].metrics` names others. `statstable` imports `stats.table` at module level, which the import rule allows because that module imports only the standard library at module level; numpy loads when a metric is computed.

**Stable pages need:** `guide/plots-statistics.md` (the columns, the sidecar), `internals/` page on the table if there is one.
