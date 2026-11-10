# Implementation notes, round 2

Written by the implementing agent. Every decision made off the plan, newest last, one bullet each: the date and step id, what was decided, why, and where in the code. The phase files' logs hold each step's state. This file is the list a reader checks first.

The developer reviews this file at the round's end, and then it leaves `.plans/`: a decision kept goes to a decision note.

## Decisions

- **2026-11-10 · 1.1.** `ALIASES` has 24 keys, not 22. T1 lists 24 rows whose id changes, `lambda` and the two removed twins among them, and the test holds 24.
- **2026-11-10 · 1.1.** The four fixed columns (`yield_weighted_abs_dev`, `yield_ratio`, `mean_bin_ratio`, `mean_abs_ratio_dev`) were renamed in 1.1 rather than 1.2. They are registry metrics under the same id, so renaming the registry alone would have left the table's columns out of the sidecar's metrics. `plot.STATISTIC_LABELS`' keys and the `resolve` of `legend_statistic` and a figure's `statistic` came with them. 1.2 keeps the rest: format 3, `table.read`'s mapping, `upgraded`.
- **2026-11-10 · 1.1.** `settings_of` resolves an old id in `metrics` and `thresholds` too, beside the three readers named in 1.1, so a ranking table still naming one scores until 1.3 refuses it in a user's file. `bars.py` and `house.py` moved off `.better` here, since the field is gone.
- **2026-11-10 · 1.1.** Display names and notes are 02's catalogue rows; the formulas' LaTeX left-hand sides (`|Δ|/reference`, `area/reference`, `mean ratio`) are kept as written.
- **2026-11-10 · 1.3.** `config.renamed` checks `legend_statistic` and `statistic` in every table it walks for page keys: `[plot]`, a figure, a set entry and a report section's `plot`. That is one rule rather than a key per kind of table. A key that does not belong there is still refused by the schema afterwards.
- **2026-11-10 · 1.3.** `cli.main` clears `config.OLD_NAMES` before each command. In-process callers, the tests among them, would otherwise hear the names an earlier command read.
- **2026-11-10 · 1.4.** `integrity`'s title is "Integrity" and its question is written here, since 02 gives neither. Its key heads `HEADLINE` before `quality`, so a report shows it once the gates exist; an empty category draws nothing. The registry test excludes it from "every category has a metric" until 2.1.
