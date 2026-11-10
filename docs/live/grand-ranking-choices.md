---
id: live-grand-ranking-choices
summary: the Grand Ranking's smaller rules, chosen while building it: rank's JSON and terminal, migrate's reach, edge values, the summary's layout
affects: plots-statistics, reports
issue: I-151
---

**Now holds:** the rules below, beside [live-grand-ranking](grand-ranking.md), which owns the design. Each was chosen by the implementer and waits for the developer's yes (`.plans/Notes.md`).

**No longer holds:** `rank --json` failing on a number it has not, and `rank` failing on a terminal that is not UTF-8.

**Decisions:**
- **V287** `rank --json` writes every number that is not finite as null: a point with no scored page, a value with one stratum. It says `loss` wherever it said `score`, in a Run's row (`loss`, `best_loss`) and a marginal's `values[]` too. A vetoed point's and a lossless point's `rank` is null; the terminal prints "–" there. Gave up: NaN in JSON, which most readers refuse.
- **V288** On a terminal that is not UTF-8, `rank` prints ASCII forms: the polarity glyphs' (`[v]`, `[^]`, `[=1]`, `[o]`) and its other signs' (`x`, `+/-`, `~`, `-`); any sign left is replaced, never an error. Gave up: a crash on a log file's encoding.
- **V289** `heimdall score` keeps a hidden parser of its old options, so any old line stops with the refusal, not an argparse error; `explain score` is refused with `explain ranking`. The default report's folder is `stats/01_Leaderboard`.
- **V290** `migrate` rewrites `heimdall score` and `explain score` in a comment only: a string value can be hashed (a tool's `arguments`). A section's `stats` is rewritten under `[[report.section]]` only, since `[errand].stats` names sets. Every form of `[score]` the refusal names is rewritten: a header (quoted too), a dotted key, a set's own table.
- **V291** Edge values. `peak_bin_ratio` is NaN when no compared bin has a yield (an empty curve is `yield_sign`'s). A `one` metric's thresholds are on \|log₁₀ m\|, as the registry states them; an infinitely good value (q = −∞) costs 0. A trim of α = 0 trims nothing; any α > 0 trims at least one value of three or more.
- **V292** A set whose pages have no measured bins has no default metric with a number, so its summary is the facts page alone; naming `chi2_ndf` in `[ranking].metrics` ranks it.
- **V293** A figure's weight is recorded with the source `figure`, named by its page; when a glob of `[ranking].weights` also matched, the note says the figure's weight won. The Pages stage lists only weights other than 1, then "every other page" with its count.
- **V294** A marginal's best row is "best" (`vs_best` 0, `same_as_best`); a value is indistinguishable at \|vs_best\| ≤ 2 SE. Its headline is "<quantity>: <best>, ×<ratio> against <next>, <n> strata", with the indistinguishable after; a quantity with no matched stratum is ordered by level and says so.
- **V295** The summary's front: the facts, the contents, the reading key, "How these numbers were made", the notes. "Made by" is a line under its table, skipped by the contents and the web page's navigation. The PDF's cut row says how many more points the HTML and `rank --json` hold.
- **V296** The leaderboard's rank is a column, so the label is the point's name; a vetoed row has an empty rank under a band "vetoed". "Metric values" follows it: each point's median of each metric over its pages, the record's choice "values shown".
- **V297** `--head-to-head` on `plot` and `report` reaches the summary through the command, and the sidecar keeps it with the source `--head-to-head`, so a later `rank` still says where it came from. `rank --detail` adds a "Metric values" table to the terminal; a crossed table has no terminal form.
- **V298** `yield_sign`'s thresholds are (0, 1): a page with a non-positive yield costs bad, every such page alike; its size is `log_yield_ratio`'s, clamped at 1 % of the reference.

**Stable pages need:**
- [plots-statistics](../stable/guide/plots-statistics.md): V287, V288, V291–V298 where it describes `rank`, the summary and the metrics.
- [reports](../stable/guide/reports.md): V289's folder name; V297's `--head-to-head`.
- The decision notes V287–V298 into `stable/design/decisions/plots.md` with V276–V286.
