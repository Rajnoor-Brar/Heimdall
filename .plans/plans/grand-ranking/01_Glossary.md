# 01 · Words: the audit and the rename table (Pillar 4)

## How it was audited

These terms were counted, and each use was read in context:

- **The terms:** statistic(s), metric, score, loss, cost, purpose, standings, ranking, place, marginal, baseline, reference, axis/axes, quantity, curve, cell, veto, worst.
- **Where:** `framework/stats/`, `framework/plot/figures/bars.py`, `framework/runner/report.py`, `scorecmd.py`, `statstable.py`, `framework/schema/run.toml` and `report.toml`, and the guide pages `plots-statistics` and `reports`.

Counts in those files: score 210, curve 247, cell 153, axis 127, statistics 127, reference 113, baseline 111, metric 111, purpose 85, quantity 74, loss 51, cost 40, standings 31, veto 29, ranking 25, statistic 30, marginal 24, variation 0.

## Collisions found

| Word | Its meanings today | Where | Harm |
|---|---|---|---|
| **score** | (1) a point's aggregate, lower is better; (2) the `[score]` table; (3) the `heimdall score` command; (4) under `aggregate = "topsis"`, `1 − closeness`, another quantity | `score.py:312`, `run.toml:1094`, `scorecmd.py`, `score.py` topsis | "score" reads higher-is-better everywhere else in statistics and ML. A reader inverts the table. |
| **statistic / statistics** | (1) the table, statistics.csv; (2) one column (`legend_statistic`, the `statistic` figure, `[figure].statistic`); (3) the `[stats]` table; (4) `[errand].stats`, the follow-up switch | `run.toml:951-1253` | "statistic" and "metric" both name one column |
| **purpose** | the question a metric answers | `metrics.py:PURPOSES` | the developer's word is *category*; "a metric asks one of the purposes" is not English a reader expects |
| **shape** | (1) a purpose; (2) a metric in it | `metrics.py:PURPOSES`, `REGISTRY["shape"]` | "shape's shape" in the summary; the similarity purpose is about shape too |
| **worst** | (1) the metric (the k largest pull²); (2) the "worst page" column; (3) "worst bins" (its title) | `metrics.py`, `bars.py:543` | the standings table has a "worst" column that is not the metric `worst` |
| **norm / normalise** | (1) metric `norm`, the \|ln yield ratio\|; (2) `[score].normalise`, how a metric becomes a cost; (3) the page key `normalise = "area"` | `metrics.py`, `score.py:NORMALISE`, `run.toml` | three unrelated things, one stem |
| **axis / axes** | (1) a swept quantity (`[score].by`, `--by AXES`, the sidecar's `axes`, `Marginal.axis`, a baseline's `axis=tag`); (2) a plot's x or y axis; (3) a set's roles, called "axes" (`SetSpec.axes`) | `score.py`, `scorecmd.py`, `table.py`, `sweep.py` | the model's word is **quantity**; `axis` is taken by plotting |
| **mean** | (1) `[score].mean`, RMS by default; (2) a set merge's `how`; (3) `ratio_mean`; (4) the marginal's "mean score", which is an RMS | `score.py:497`, `bars.py:708` | the marginal's note says mean and computes RMS: a contradiction, fixed in P4 |
| **reference** | (1) what a curve is compared against (the data, else the page's first curve); (2) `[stats].reference`, a filter that picks it; (3) `tests/reference/`, the physics outputs; (4) Rivet's reference data | `table.py`, `plot.py:measured` | (1) and (2) are one thing; (3) is another subject and keeps its name |
| **baseline** | (1) `[score].baseline`, a point the others are differenced against; (2) a bar graph's zero line ("from one baseline", `bars.py:_bars`); (3) snapshot folders `~/heimdall-baselines/` | `score.py`, `bars.py` | (2) becomes "zero line" |
| **tag** | (1) a quantity value's name; (2) a Run's label (V261) | `quantities`, `records/…/tag` | user-facing, a quantity has **values**; a Run has **labels** |
| **standings / ranking / place** | the per-cell table; each metric's ordering; the rank number | `bars.py` | three words for orderings; "place" is a retired notion (V176) |
| **configuration** | Heimdall: a recipe `[cfgs.<name>]`. The request's "parameter configurations (points)": one combination of values | `model.md` | the request's sense is Heimdall's **point**. Kept as Heimdall's, and the glossary says so. |
| **variation** | not used in code. The request's "orthogonal variations" | — | the concept is a **stratum** (below), now named |

## The ontology: one word, one meaning

Lower-is-better runs through one family of words: cost → category cost → page loss → point loss. Only **rank** is ordinal.

| Term | Strict definition |
|---|---|
| **point** | one combination of quantity values: one chain of processes, one folder. (Not "configuration": that is the recipe.) |
| **quantity**, **value** | a named setting that a sweep varies or fixes; one of its levels. A value's internal name stays `tag`. |
| **varied quantity** | a quantity with at least two values among the scored points |
| **curve** | a point's histogram drawn on one page; the unit every metric is computed on |
| **page**, **cell** | one object drawn for one cell; the points sharing a page (the page cell) |
| **reference** | what a curve is compared against on its page: the data, else the page's first curve. The reference curve itself is not scored. |
| **metric** | one named number of a curve against its reference, from the measured bins, with a category, a polarity and two thresholds. (Replaces "statistic" for one number.) |
| **statistics** | the table of every curve's metrics: `statistics.csv` and its sidecar. Plural noun only. |
| **category** | the question a metric answers: compatibility, normalisation, shape accuracy, shape similarity, trend, local defects, integrity, Monte Carlo quality. (Was "purpose".) |
| **polarity** | which way is better: ↓ lower, ↑ higher, →1 closest to one, ○ a descriptor, not scored |
| **gate** | a pass/fail integrity test on a page (03 §1.1); **vetoed**: a point that failed a gate on any page |
| **cost** | a metric's value in tolerance units, oriented and compressed: 0 within good, 1 at bad (03 §1.2). ↓ |
| **category cost** | the RMS of a category's metric costs on a page. ↓ |
| **page loss** | the RMS of a curve's category costs on a page. ↓ |
| **point loss** | the RMS of a point's page losses, page weights counting. ↓ (Was "score".) |
| **worst page** | the page where a point's page loss is largest |
| **Grand Ranking**, **rank** | the order of the points by (vetoed, failed pages, point loss); a point's position in it, 1 best |
| **leaderboard** | the table that shows the Grand Ranking (was "standings") |
| **slice** | the points sharing one value of one quantity |
| **stratum** | the points sharing the values of every *other* varied quantity: one slice member per value of the quantity |
| **marginal** | a value's trimmed mean of ln point loss over its slice: its typical level (03 §2) |
| **matched effect** | a value's trimmed mean, over strata, of a point's ln loss less its stratum's mean: how much better or worse the value is with everything else held equal (03 §2) |
| **baseline** | a chosen point, or a filter naming one, that every other point is differenced against |
| **head to head** | one page's curves pairwise: each pair's page-loss difference; no wins counted; opt-in |

## Rename table (current → proposed)

| Current | Proposed | Where it changes |
|---|---|---|
| score (a point's number) | **point loss**, `loss` | `PointScore.score` → `PointLoss.loss`; summary and report headers; `--json` keys | · closed 1.5
| `[score]` | **`[ranking]`** | schema, errand files (migrate), the sidecar's `score` key → `ranking` |
| `heimdall score` | **`heimdall rank`** | CLI; `score` refused, naming `rank` | · closed 1.5
| `score = {…}` on a set | `ranking = {…}` | `sweep.SetSpec.score` | · closed 1.5
| purpose, `PURPOSES`, `ASKS` | **category**, `CATEGORIES`, `QUESTIONS` | stats, bars, report, sidecar (`purpose` → `category`) | · closed 1.4
| `purpose:<name>` (a report section key) | `category:<name>` | report recipes (migrate) |
| standings | **leaderboard** | the section key `standings` → `leaderboard` (old key refused, naming the new) | · closed 1.5
| axis, axes (a swept quantity) | **quantity**, quantities | `[ranking].by` takes quantities; sidecar `axes` → `values` (`{point: {quantity: value}}`); `--by QUANTITIES`; `--baseline q=value` | · closed 1.5
| tag (a quantity's value, user-facing) | **value** | messages and docs only; the TOML key `tag` stays |
| `veto` (a loss threshold) | **`veto_loss`** | `[ranking]`; the gate is the default veto | · closed 1.5
| `[score].normalise` | **`[ranking].cost`** (`thresholds` default) | frees "normalise" for pages | · closed 1.5
| `[score].mean` | **`[ranking].over_pages`** (`rms` default) | its job, not its kind | · closed 1.5
| `legend_statistic` | **`legend_metric`** | `[plot]` | · closed 1.6
| figure kind `statistic`, `[figure].statistic` | **`metric`** | figures | · closed 1.6
| "the bars' baseline" | **zero line** | `bars.py` docstrings and keys | · closed 1.6
| metric ids | see 02 | registry, alias table | · closed 1.1

**Kept as they are:** `[stats]`, `statistics.csv`, `--stats-only`, `statistics/<set>/` (the table of metrics is "the statistics"), "configuration" (Heimdall's recipe), `tests/reference/`.

**Missing from today's glossary** (`docs/stable/design/glossary.md`): metric, category, cost, page loss, point loss, gate, Grand Ranking, leaderboard, slice, stratum, marginal, matched effect, baseline, reference (in this sense), head to head, polarity. They go into the live doc in P6 and reach the glossary at the next crystallise. · closed 6.1
