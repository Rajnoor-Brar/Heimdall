# Scoring rework: what is known

Notes for planning, from 2026-11-01. A claim, not a plan: re-verify against the code. Page: `plots-statistics`. Issue: I-120.


**The pipeline today**, one Run's (or a runs-together `--across` set's) pages at a time:

1. **Paint measures** each page as drawn (after voiding, alignment and normalisation), over the x span before
   `x_range`/`y_range`: `src/Apps/Paint/main.cc` `statisticsJson` (~line 200) writes `<page>.toml.stats.json`. The
   curve arithmetic is in `src/Apps/Paint/Transform.hh` (area, χ², rebinning onto the reference's bins). The
   reference is the data when there are any, else the page's first curve.
2. **The table:**
   - `framework/runner/statstable.py` reads it (`statistics_of`) into rows of `STATISTIC_COLUMNS`: `page, cell, object,
     curve, point, reference, is_reference, bins, area, area_err, ref_area, cmp_area, abs_area, rel_abs_area,
     area_ratio, ratio_mean, ratio_dev, chi2, ndf, chi2_ndf`.
   - It writes `results/…/statistics/<set>/statistics.csv` (`write_statistics`, `write_set`) and reads it back (`read`).
   - The callers: `plot._tables` (plot.py ~1782), `plot.measure` (~1831, `heimdall stats`), `report.py`.
3. **Scoring and presentation:** `framework/plot/figures/bars.py` (875 lines) does both.
   - **Per page:** a bar image per page (`page`, `PANELS`).
   - **Per statistic:**
     - tables, a row per point and a column per object, shaded (`_tables`, `TABLES`, `RULES`);
     - rankings by mean (`_ranking`, `_means`), arithmetic, but **geometric** for the ratios;
     - cells against curves (`_crossed`).
   - **The standings (V176):**
     - `_page_rankings` places each page's curves in each of `SCORED = (chi2_ndf, rel_abs_area, area_ratio,
       ratio_mean, ratio_dev)`, by `_distance` (the number itself; the two ratios by |log10 r|);
     - `POINTS = (5, 4, 3, 2, 1)` per place, ties share the better place;
     - only pages against data are counted when any has data;
     - points of different page cells never meet.
   - **Head to head (V177):** `_head_to_head`, `_rates` (each pair of curves on a page is a match).
   - **Prose:** `DEFINITIONS`, `FORMULAS`, `NOTES`, `SCORE_TEXT` and `H2H_TEXT` are the prose that the summary *and* the
     report print (I-111 put the definitions first in reports).
   - **Composition:** `summary_model`/`summary_of` → `summary.pdf`/`.html` (via `paper.py`, `typeset.py`, `webpage.py`).
4. **Reports** (`framework/runner/report.py`, 2408 lines) re-render the chosen summary sections from
   `statistics.csv` (`stats = ["top5", "scoreboard", "scoreboard-cells", "head-to-head", "scoreboards", "chi2_ndf",
   …]`).

**Where it is documented:**
- 03 §3.2 "Statistics of the pages".
- 04's `[plot].statistics`, `[plot].legend_statistic` and `[stats]` keys (generated from `framework/schema/run.toml`).
- `.plans/statistics_a4_plan.md` (V196–V199, the summary's A4 layout).
- `.plans/report_context.md` (I-111).
- The rows: V160, V162, V164, V168, V175–V177, V196–V199, V205, V218, V219 (ranges only show), V233.

**Tests:** `tests/runner/test_statstable.py` (the table and much of bars.py's scoring), `test_summary_layout.py`,
`test_report.py`, `test_report_build.py`, and the slow `test_plot_stage.py`.

**What a rework will have to settle:**
- Scoring and drawing are in one 875-line module, and the rank table of 06 §2.1 puts it under `plot/figures/`. A
  scoring module of its own (pure: rows in, scores out), with bars.py only drawing, is the obvious seam.
- What a score is per page: competition places with fixed points, versus a continuous measure (a normalised
  distance, a likelihood, a p-value from χ²/ndf). Then how pages are pooled (sum, mean, weighting by bins or
  uncertainty), and how ties and missing statistics count.
- Whether the five statistics are independent enough to sum: `rel_abs_area` and `ratio_dev` move together; `area_ratio` and `ratio_mean` too.
- The reference rule (data, else the first curve, which then cannot be ranked; `[stats].reference` and the other
  `[stats]` keys, `framework/schema/run.toml` ~1018, measure with settings of their own) and pages without data.
- Scoring across Runs: `--across` sets get their own `statistics.csv`, but there is no score over several Runs' sets
  or Errands (X2 of the report audit dropped it then).
- `statistics.csv` is a public file (the report reads it, users read it). A column change wants a format version (I-28).
