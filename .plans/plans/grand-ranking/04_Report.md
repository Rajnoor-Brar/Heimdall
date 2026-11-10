# 04 · The report: sections, order, defaults and notes (Pillar 1)

The summary (`statistics/<set>/summary.pdf` and `.html`) and the report's statistics part draw the same document model (`bars.summary_model`). `report.HEADLINE` (`report.py:56`) lists its section keys. One change serves both.

## Today, and what changes

| Today (`bars.summary_model`) | Proposed |
|---|---|
| Front: facts and notes | Front: facts, the **reading key** (polarity legend, the gate rule, what a loss of 1 means), notes |
| **Standings**: a table ranked within each page cell, with score, worst page, worst, veto, a column a purpose, then the purposes' list | **§1 Leaderboard** (default), below |
| A section a purpose: its ranking, then for every metric its ranking, its cells × curves table and its object table | **§3 Categories** (default): what it asks, its metrics' definitions, one ranking with the gates applied. Per-metric crossed and object tables only with `detail` |
| Marginals: the RMS of scores per value, per axis | **§2 Quantity marginals** (default), below |
| Baseline (when set) | §4 Baseline (when set), unchanged but renamed (01) |
| Head to head (when `[score].head_to_head` names pages) | §5 Head to head, **opt-in only**: `[ranking].head_to_head`, or `--head-to-head PAGE\|all` on `heimdall rank`, `heimdall plot --stats-only` and `heimdall report` |

The report's default section list becomes `["leaderboard", "marginals", *("category:" + c), "baseline", "head-to-head"]`. A section with nothing to show is left out without a word, as today.

## §1 Leaderboard (default)

One flat table, a row a point, in Grand Ranking order (03 §1.4):

| Column | Content |
|---|---|
| rank | 1 = best; vetoed rows are unnumbered and shown last, under a rule |
| one column per varied quantity | the point's value of each, never its mangled name: a reader sorts and filters by quantity |
| point loss ↓ | L(p), shaded by cost |
| worst page ↓ | the object, and its page loss |
| one column per category ↓ | its cost, the RMS over pages of C_κ |
| `n_eff` ↑ | the median over pages: a descriptor, not in the loss |
| gate | empty, or the reason: "bin 10¹¹× ref on 12/12 pages" |

- **Flat** when every cell is measured on the same objects against the same reference, as on B1–B4. Banded by cell, as today, otherwise, with the note saying why.
- **Long tables:** the PDF shows the top 25 and every vetoed row, and says how many it left out. The HTML and `--json` show all.

Under it, **Metric values**: a table a row a point (same order), a column a default metric, each holding the metric's median over the point's pages, with the metric's polarity in the header and shaded by its cost. This is the "evaluated metric values" of the request. The loss explains the order, and the values explain the loss.

## §2 Quantity marginals (default)

A table for each varied quantity, in the order the sweep names them. A row a value, ordered by the matched effect:

| value | × vs strata ↓ | ± SE | vs best | level | n | trimmed | vetoed | unmatched |
|---|---|---|---|---|---|---|---|---|
| lpdfon | ×0.93 | 0.01 | best | 1.45 | 144 | 28 + 28 | 0 | 0 |
| lpdfoff | ×1.08 | 0.01 | ×1.16 ± 0.02 | 1.72 | 144 | 28 + 28 | 0 | 0 |

Above the tables is one **headline line a quantity**: the best value, its distance to the next ("lepton PDF: on, ×0.86 against off, 144 strata"), and the values indistinguishable from the best. Notes: the definition of E and M (03 §2.2), the trim rule, the small-n marks, and why vetoed points are out.

## §3 Categories (default, after the marginals)

For each category with a metric on:
- **what it asks:** today's `ASKS`, renamed `QUESTIONS`;
- **its metrics:** each with its polarity, one-line description and thresholds;
- **one ranking of the points by their category cost:** vetoed points are shown last and marked, never ranked first. This fixes the inversion of 05 §1, where χ² alone ranked the pathological points best.

**With `detail = true`** (`[ranking].detail`, `--detail`), each metric's ranking, cells × curves table and object table follow, as today's purpose sections hold them. Off by default: on B4 they are 36 × 8 rows per metric.

## Notes and annotations

- Every table's first note is the polarity legend. Every number column's header carries its glyph (02).
- A vetoed point's note names the gate, the page count and the largest value found.
- A marginal's note gives n, g and the vetoed and unmatched counts. No table states a mean without its n.
- "Lower is better" appears once, in the reading key, and as the ↓ in each header. The title sentences ("lower is better; darker: costlier …") go.
- The method section of a report ("How the numbers are made") gains the gate rule, the cost formula with its compression, and the marginal's two statistics, from 03.

## Method: how every number was made (the transparency rule)

The reader is never left to guess. Two layers, both rendered from the engine's method record (03 §3a):

**1. Under every table, a "Made by" line** naming the rules that shaped that table's numbers, with the values in use:
- *Leaderboard:* "Gates: a bin ≥ 10³ × reference, a yield ≤ 0 (registry). Cost: thresholds, compressed log₂(1 + z). Category: RMS of its metrics, weights 1. Page loss: RMS of 5 categories. Point loss: RMS over 12 pages, weights 1 (no figure weight, no glob). Ranked flat across 36 cells: same objects, same reference."
- *A marginal:* "20 % trimmed mean of ln(0.01 + loss) over 32 strata, 6 trimmed each end; ordered by the effect against each stratum's mean; 0 vetoed; best compared by a paired trimmed difference, uncorrected."
- *A category ranking:* its metrics with their weights and thresholds, and the mean used over pages.

**2. A "How these numbers were made" section,** at the front of the summary and in every report that shows statistics (today's method section, extended). It gives:
- each metric scored: its formula or note, polarity, thresholds with their source and why, and its weight;
- the gates, and every point they vetoed, with the evidence;
- the cost transform, its compression said in words ("a cost of 2 is three times bad's excess, not twice"), and a worked line from one real row, value → z → c;
- each mean in the chain, named: within a category, across categories, across pages, and for marginals, with what each favours ("RMS weighs a bad page up: the all-rounder wins");
- every weight that is not 1, and where it came from;
- what was left out, and why.

When a setting departs from its default, both layers say so: "over_pages = median ([ranking], not the default rms)".

`heimdall rank` prints the "Made by" lines under its tables, and `--method` prints the whole record. `--json` carries it as `"method"`.

## Settings and flags (the generated reference owns their defaults once built)

| Where | Key or flag | Values |
|---|---|---|
| `[ranking]` | `metrics`, `thresholds`, `weights`, `weights_by`, `cost`, `over_pages`, `aggregate`, `dominated` | as today's `[score]` keys, renamed (01) |
| `[ranking]` | `gates` | `true` (G1, G2) \| `false` \| a list of gate names |
| `[ranking]` | `veto_loss` | a number: G3 |
| `[ranking]` | `trim` | 0 ≤ α < 0.5, default 0.2 |
| `[ranking]` | `by` | the quantities whose marginals are shown (default: every varied one) |
| `[ranking]` | `head_to_head` | `"<cell>/<object>"` \| `"all"` \| unset |
| `[ranking]` | `detail` | `false` \| `true` |
| `heimdall rank` | `--by`, `--baseline`, `--head-to-head`, `--detail`, `--trim`, `--json`, `--set` | as the keys |
