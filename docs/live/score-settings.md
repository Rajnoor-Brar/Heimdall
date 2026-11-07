---
id: live-score-settings
summary: the [score] table, [stats].metrics and centres, a set's score, a figure's weight, and heimdall explain score
affects: plots
issue: I-120
---

**Now holds:** an errand file may have `[score]` (keys `metrics`, `normalise`, `thresholds`, `weights`, `weights_by`, `mean`, `by`, `baseline`, `veto`, `aggregate`, `dominated`, all in `framework/schema/run.toml`), `[stats].metrics` (the metrics computed for the table) and `[stats].centres` (`mid` or `barycentre`). A set table may carry `score = { … }`, laid over `[score]` for its pages, and a figure `weight`. Metric, mean and threshold names are checked when the file is read, against `stats.metrics.REGISTRY` and `stats.means.MEANS_BY_NAME`, with a "did you mean" hint; loading `numpy` happens only for a file that has a `[score]` or `[stats].metrics`. `heimdall explain score` lists the keys, the metrics by purpose and the means; `heimdall explain score.<name>` shows one metric (direction, thresholds and why, what it needs) or mean (guard, error rule, settings) in full. The engine that reads them is [live-score-engine](score-engine.md); the summary, the report and the CLI do not use it yet, so for now these are checked and carried on `Errand.score`, `Errand.stats` and `SetSpec.score`.

**No longer holds:** `[stats]` having only the keys that say what is measured.

**Decisions:** `[score]` is its own table beside `[stats]`: `[stats]` says what is measured, `[score]` how it is scored. A set's `score` is checked against the same keys but its metric names are checked where the engine reads it.

**Stable pages need:** `guide/plots-statistics.md`, `reference/` pages are generated.
