# Phase 4: statistics.csv format 2

Status: done 2026-11-07.

### Step 4.1: move and extend the table (Size: S)
- Acceptance: `statstable` moves to `framework/stats/table.py`, and `runner/statstable.py` re-exports it for a release. Columns of the computed metrics are appended after `STATISTIC_COLUMNS`, which keeps its order. `statistics.json` beside the CSV holds `format = 2`, the metrics on, each one's definition note, and the thresholds. An old CSV (no sidecar) reads as format 1.
- Files: `framework/stats/table.py`, `framework/runner/statstable.py`, `tests/runner/test_statstable.py`.
- Check: `taskset -c 0-5 nice -n 10 python -m pytest -q tests/runner/test_statstable.py`
- Live doc: `docs/live/statistics-format.md`.
- Blocked by: 2.2.

## Log

2026-11-07: 4.1 done. `framework/stats/table.py` (rows, csv, sidecar, `read`, `format_of`), `runner/statstable.py` keeps `bars`, `heading_of`, `write_set` and re-exports the rest. New columns `norm, shape, tilt, worst` by default; `statistics.json` format 2. Checked: `test_statstable.py` and the report, summary and plot tests (232 passed); the real studies' format 1 csvs (2472 rows, read only) read as format 1. Deviation: `statstable` imports `stats.table` at module level (see Implementation_Notes). Not run: the slow plot-stage statistics tests.
