---
id: live-grand-ranking
summary: points ranked by a loss after integrity gates; compressed costs, nine curated metrics, matched marginals; every table says how its numbers were made
affects: plots-statistics, reports, glossary, extending, runner, decisions-plots
issue: I-151
---

**Now holds:**

*The words.* A point's number is its **loss**, lower is better; a metric's contribution on a page is its **cost**. Metrics fall into **categories**. The settings are `[ranking]`, the command is `heimdall rank`, and the engine is `framework/stats/ranking.py` (`ranking.rank`). A metric's **polarity** says which way is better, shown as a glyph in every header: ↓ lower, ↑ higher, →1 closest to 1, ○ a descriptor. A terminal that is not UTF-8 gets the ASCII forms (`[v]`, `[^]`, `[=1]`, `[o]`). Ids, categories, defaults and thresholds are the generated [keys](../reference/keys.md) and [plot settings](../reference/settings/plot.md), and `heimdall explain ranking`.

*The order.* Integrity **gates** come first and are lexicographic: a point with a page that fails a gate is **vetoed** and ranks after every point that passes, whatever its loss. Among the vetoed, fewer failed pages come first, then the smaller loss. A vetoed point has no rank number, and its reason names the gate, the page count and the largest value found. The gate metrics are `peak_bin_ratio` (a bin far beyond its reference) and `yield_sign` (a yield of zero or less on a cross-section page). `[ranking].gates` turns them off or picks some, and `veto_loss` adds a page-loss gate. A table written before the gate columns existed reads as "not evaluated". Passing points are ordered by loss. Losses equal to three significant figures share a rank (1, 2, 2, 4).

The leaderboard is **flat**, one order over every page cell, when every cell is measured on the same objects against the same reference. Otherwise each cell is ranked apart under its band. Either way the record says why.

*Costs.* With `cost = "thresholds"` a metric's value is oriented (q) and hinged on its good and bad thresholds (z = 0 within good, 1 at bad). It is then compressed: c = log₂(1 + z), so a cost of 2 is three times bad's excess, not twice. A category's cost is the RMS of its metrics' costs. A page's loss is the RMS over the categories with a cost, so four metrics of one category weigh as one. A point's loss is the `over_pages` mean of its page losses, page weights counting: a figure's `weight`, else a glob of `[ranking].weights`. The opt-in costs (`median`, `mad`, `minmax`, `surprisal`) are pool-dependent and not compressed.

*The metrics.* Nine curated metrics are scored by default, two to a category where the evidence earned a pair. `n_eff` is shown, not scored. `chi2_ndf` is a column, not a default. Each point carries the median of each default and shown metric over its pages, beside the loss: the values explain the loss and are not in it.

*Marginals.* A table per varied quantity (`[ranking].by`, else every one), a row per value, ordered by the **matched effect**: the 20 % trimmed mean (`[ranking].trim`) of each point's ln(0.01 + loss) against the mean of its **stratum**, the points equal on every other varied quantity. Columns:
- × vs strata: e^E, with its SE;
- vs best: a paired trimmed ratio over the strata both hold, ≈ best within 2 SE, uncorrected for multiplicity;
- level: e^M, the slice's typical loss;
- n strata, g trimmed each end, vetoed (out of every number, counted) and unmatched.

A headline line above each table names the best value, its ratio to the next, and the values indistinguishable from it. A quantity with no matched stratum is ordered by level and says it is confounded.

*The summary* (`statistics/<set>/summary.pdf` and `.html`, and the report's statistics):
- The front holds the facts, the contents, a reading key (the legend, the cost, the gates, the order), "How these numbers were made" (the whole record, with one real row worked through the cost) and the notes.
- Then the sections, in order: `leaderboard`, `marginals`, `category-<c>`, `baseline` when set, and `head-to-head` when asked.
- The leaderboard's columns: rank; a column per varied quantity; point loss; worst page and its page loss; a column per category; n_eff; the gate when a point is vetoed. "Metric values" follows it, a row per point in the same order.
- The PDF shows the first 25 points and every vetoed one, and says how many more the HTML and `rank --json` hold.
- A category's section holds its question, each metric with its polarity, description and thresholds, and one ranking by the category's cost, the vetoed last and marked. With `[ranking].detail` (or `--detail` on `rank`), each metric's own section follows: its ranking, its page cells against its curves, and its object table. A report section naming a metric (`chi2_sigma`, `chi2_sigma:crossed`) draws that metric's alone.
- `head_to_head` is opt-in, by the key or `--head-to-head PAGE|all` on `heimdall rank`, `heimdall plot` and `heimdall report`.
- The report's default section list is the same order.

*The method record.* `rank` returns, with the numbers, a record of every choice it applied, stage by stage: gates, metrics, cost, category, page loss, pages, order, marginals, opt-in. Each choice carries its value, its source (`registry`, `default`, `[ranking]`, `set <name>`, `figure`, `--<flag>`, `table`) and a note. It is shown:
- under every table of the summary as "Made by" (the choices that shaped that table);
- at the summary's front;
- in the report's "How the numbers are made";
- under each of `rank`'s tables as "made by:";
- in full by `rank --method`;
- as `method` in `rank --json` and in `statistics.json`.

A setting off its default is said with its source. A test fails if any `[ranking]` key, a set's `ranking`, a figure's weight or a flag of `rank` moves a number while the record does not change, so a new key cannot be added without its record.

*Old names.* An old name (`[score]`, `score`, a purpose, an old metric id) in a file under `configs/` or a report recipe is refused, naming the new one. `heimdall migrate` rewrites a user's configs and recipes. A record's snapshot, a Run's `plot.toml` and its `report.toml` still read: old names are mapped on read, with one line a command saying so. An older Run's `statistics.csv` and sidecar read with today's ids and polarity, and the file is untouched.

**No longer holds:**
- a point's "score", higher or lower;
- `[score]` and `heimdall score`;
- purposes;
- the old metric ids as settings;
- standings ranked within each page cell when the cells share objects and reference;
- a veto only by `veto_loss`;
- a linear hinge without a cap;
- a marginal that is the RMS of a slice's scores;
- every metric's crossed and object tables by default;
- notes that state a rule in prose beside the code (the loss note, "lower is better" in titles).

**Decisions:**
- **V276** Gates before loss, lexicographic: no good page can buy a failed one back. Gave up: one number that orders every point.
- **V277** Costs are compressed, c = log₂(1 + z): 0 and 1 stay at good and bad, and one wild metric cannot dominate a loss. Gave up: a cost proportional to the excess beyond bad.
- **V278** Nine curated default metrics and two gates, a pair a category where the benchmarks earned it. `chi2_ndf` is not a default. Gave up: one metric a category.
- **V279** A marginal is ordered by its matched effect, a trimmed mean of ln loss against each stratum, with the level beside it: matching removes a stratum's difficulty, including the imbalance gates create. Gave up: the plain mean of a slice.
- **V280** The leaderboard is flat when every cell has the same objects against the same reference (judged by the `reference` label), else banded by cell. Gave up: always comparing within a cell.
- **V281** The engine returns a method record, and presenters render it rather than restate rules. A test holds the record complete. Gave up: hand-written notes beside each table.
- **V282** Old names are refused in a user's files, naming the new, and mapped on read in records. `migrate` rewrites configs and recipes only, since rewriting a record changes its digest for no gain. Gave up: silently accepting old names.
- **V283** Long leaderboards: the PDF holds the first 25 and every vetoed point, and the HTML and `--json` hold all. Per-metric detail is opt-in, as ordinary sections. Gave up: a complete PDF table, a collapsing HTML element.
- **V284** Ties share a rank when their losses agree to three significant figures, ordered by name. Gave up: ranks that differ in the fourth digit.
- **V285** A command's flag over a key (`--by`, `--baseline`, `--trim`, `--head-to-head`, `--detail`) is a source `--<flag>` in the record, and a flag given to `plot` is kept in the sidecar with it. Gave up: flags that leave no trace.

Decided while building it:
- The engine is `framework/stats/ranking.py` and the command module `framework/runner/rankcmd.py`, so one word keeps one meaning: `score` was a loss under another name.
- `means.trimmed_se` is the marginals' trimmed mean with its Tukey–McLaughlin error, apart from `means.trimmed`, which stays the `over_pages` mean it was.
- A table without a column the settings need is never an error: a gate is "not evaluated", a metric "not in this table", both said in the record.
- The sidecar is format 3: it keeps each `[ranking]` key's source and each point's metric values, so `rank` says where every choice came from.
- A page fails a gate when the metric's value is finite and at or past the gate, or infinite; NaN never fails. `yield_sign` is NaN on a normalised page, since a yield's sign means nothing there.
- The order is one sort key: passing points, then points with no scored page, then the vetoed (fewer failed pages first), each by loss then name.
- The opt-in costs compute as before, on the page's pool, neither hinged nor compressed; the record's Cost stage says the transform is pool-dependent.
- A metric figure's paths keep the word `statistic` (Paint's object, the cache folder, the pages folder): a moved folder would orphan every drawn figure of every older Run.
- Unlike earlier renames, this one rewrites no record (V282): a record is read by every checkout.

**Stable pages need:**
- [plots-statistics](../stable/guide/plots-statistics.md):
  - the sections and the leaderboard's columns; gates; costs and their compression; the default metrics (by link); marginals and how to read a row; "Made by" and the record;
  - `[ranking]` for `[score]`; `rank --method`, `--detail`, `--trim` and `--head-to-head`;
  - its `code:` names `framework/runner/scorecmd.py`, which is now `rankcmd.py`.
- [reports](../stable/guide/reports.md): the default statistics section order; "How points are ranked" is the record; `--head-to-head`; `category:<c>` for `purpose:<p>`.
- [glossary](../stable/design/glossary.md): metric, category, cost, page loss, point loss, gate, leaderboard, stratum, marginal, matched effect, polarity, as above; **Grand Ranking**, the whole ordering of a set's points; **slice**, the points sharing one value of a quantity; **baseline**, the point every loss is also shown against; **reference**, the curve a page is compared against; **head to head**, a page played as matches between each pair of curves. Also loss for score.
- [extending](../stable/internals/extending.md): a new metric is a `REGISTRY` entry with its category, polarity, scale, `default`, `shown` and `gate` (not purpose and direction); `heimdall explain ranking` for `explain score`; the engine is `stats/ranking.py`.
- [decisions-plots](../stable/design/decisions/plots.md): V276–V285 appended; V251–V253 marked replaced (V276–V279, V281); V262's `heimdall score` is `heimdall rank`, and a figure's `weight` is now read.
- [runner](../stable/internals/runner.md): the rank table names `scorecmd.py` for `heimdall score`, which is now `rankcmd.py` and `heimdall rank` (`test_the_rank_table_is_the_runners`).
