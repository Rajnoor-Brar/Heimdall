# Phase 1: Paint writes measured bins

Status: done 2026-11-07. Blocked by: none.

Paint's numbers are computed on the reference's bins, with the curve rebinned onto them (`Transform.hh:251`, `rebinned` at :262). Python gets the same arrays, so every later metric works on exactly what was measured.

### Step 1.1: write `measured` per curve (Size: S)
- Acceptance: each curve object in the stats JSON gains `"measured": [[lo, hi, y, err, ref_y, ref_err], …]` over the compared bins (those counted in `compared`), in x order; a reference curve's own row has ref = itself; NaN and inf are written as `null`.
- Files: `src/Apps/Paint/Transform.hh` (`Statistics` gains a vector of rows filled in the same loop), `src/Apps/Paint/main.cc` (`statisticsJson`).
- Build: `taskset -c 0-5 nice -n 10` the Paint target only (Paint is plot-only, rebuilding is safe; no other app).
- Check: `taskset -c 0-5 nice -n 10 python -m pytest -q tests/integration/test_paint.py`
- Test seam: test_paint.py, a page whose bins are known.
- Blocked by: none.

### Step 1.2: Python sums equal Paint's totals (Size: S)
- Acceptance: a test reads every `.stats.json` the plot-stage fixture writes, recomputes `cmp_area`, `ref_area`, `abs_area`, `chi2`, `ndf` and the `ratio_*` sums from `measured`, and matches Paint's totals to 1e-12 relative. `area` is over the curve's own bins, so it is not checked from `measured`.
- Files: `tests/integration/test_paint.py` (or a new `test_paint_bins.py`).
- Check: `taskset -c 0-5 nice -n 10 python -m pytest -q tests/integration/test_paint.py`
- Decide here (Not yet specified): `measured` inline or in its own `<page>.toml.bins.json`, more than 1 MB on the fixture's largest page meaning its own file.
- Blocked by: 1.1.

## Log

2026-11-07: 1.1: `Statistics::measured` (Transform.hh) and `measuredJson` (main.cc), written with `%.17g` (`null` for NaN and inf) after `ndf`. Paint only was rebuilt (`make src/Apps/Paint.exe`, light); the live `Paint.exe` was copied to `forge/backups/Paint.exe.2026-11-07-before-measured` first. `test_paint.py` 50 passed. 1.2: `tests/integration/test_paint_bins.py` recomputes `cmp_area, ref_area, abs_area, chi2, ndf, compared` and the three `ratio_*` sums from `measured` on every curve of the fixture's pages (log-x aware) and matches Paint's totals to **1e-9** relative, not 1e-12: Paint writes its totals with `%.10g`, so no sum of exact bins can agree better; I left the totals' precision alone (changing it could move printed digits in statistics.csv). The self-reference rows equal their curve to 1e-12. Decision: inline: the largest stats.json on the fixture is 7 KB.
