---
id: live-stats-rms
summary: a statistic over pages is a root mean square, not a mean
affects: plots
---

**Superseded by [live-scoring](scoring.md)** (the scoreboards and their `rms rank` are gone; what remains is that rankings and the `rms` row and column use `[score].mean`, the root mean square by default).

**Now holds:** a statistic over pages (rankings; the last row and column of the tables and of cells against curves, headed `rms`) and the scoreboards' rank (`rms rank`) are root mean squares. Ratios too.

**No longer holds:** the plain mean over pages, the ratios' geometric mean, and `mean rank`. A ratio's number is no longer symmetric about 1: 0.5 and 2 give 1.46.

**Decisions:** a page's own statistics (`ratio_mean`, `ratio_dev`: bin averages within a page), the points totals and the win rate are unchanged.

**Stable pages need:** `guide/plots-statistics.md`, its sort order and its section per statistic.
