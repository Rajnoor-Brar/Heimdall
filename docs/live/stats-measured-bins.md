---
id: live-stats-measured-bins
summary: Paint writes the bins it measured, in each curve's stats.json
affects: plots
issue: I-120
---

**Now holds:** each curve in `<page>.toml.stats.json` has `"measured": [[lo, hi, y, err, ref_y, ref_err], …]`: the bins its totals were summed over, in x order (the reference's bins inside the page's span where the curve covers them exactly; the curve rebinned onto them), written to 17 digits so they read back as the same doubles; NaN and inf are `null`. The page's first curve, when it is the reference, has rows where the curve equals the reference (to rounding: it is rebinned onto its own edges). `Paint::Statistics::measured` (Transform.hh) is filled in the same loop as the totals. The totals are unchanged, still written to 10 digits: Python's sums of `measured` equal them to 1e-9 relative (`tests/integration/test_paint_bins.py`, every page of the plot-stage fixture), not the 1e-12 the plan hoped, which the totals' printed precision rules out.

**No longer holds:** Python seeing nothing of a page's bins.

**Decisions:** `measured` is inline in `stats.json`, not a file of its own: the fixture's largest is 7 KB (the plan's bound was 1 MB). Paint was rebuilt for this (only Paint; the live `Paint.exe` was copied to `forge/backups/Paint.exe.2026-11-07-before-measured` first).

**Stable pages need:** `stable/internals/paint.md` (the stats.json keys), `stable/internals/plot-stage.md` if it lists them.
