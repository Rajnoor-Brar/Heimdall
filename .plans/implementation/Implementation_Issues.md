# Implementation issues, round 2

Written by the implementing agent. Findings left open, appended as found. Each is a claim with where it was seen: what failed or is wrong, the output or the line, and what it blocks (a step id, or nothing). At the close each one gets an `I-` id in `.plans/Issues.md`, or is marked closed here with why.

## Open

Each is triaged (9.1, the developer's order of 2026-11-11): **Cause** (where in the code), **A user sees** (the effect and its side effects), **Urgency**, **Size** (a quick fix; light planning or a decision; a proper plan).

- **2026-11-10 · 1.5(a) · two docs tests red: two stable pages name a renamed module.** Waits for a crystallise, by the developer's word (2026-11-11).
  - **Cause:** `framework/runner/scorecmd.py` moved to `rankcmd.py`. `docs/stable/internals/runner.md:41` (its rank table) and `docs/stable/guide/plots-statistics.md`'s `code:` frontmatter still name the old file. They are read by `test_the_rank_table_is_the_runners` and `test_the_code_a_page_names_exists[stable/guide/plots-statistics.md]`.
  - **A user sees:** nothing at the command line. A reader of those two pages is sent to a file that is gone. `live-grand-ranking` overlays both, and `MAP.md` says so. The fast suite carries two known reds, so a new red is easier to miss next to them.
  - **Urgency:** low. It ends at the next crystallise.
  - **Size:** quick fix, two lines, done as part of the crystallise.
- **2026-11-10 · 1.5(c) · "tag" names three things.**
  - **Cause:** the word is a Run's label (`heimdall tag`, `plotdoc.py:881`, `cli.py:2612`) and a key of the schema: a curve's or merge entry's name, `tag = "pdf1"` (`sweep.py:248`, `:468`, `:839`, `plot.py:716`). In set filters it is also a quantity's value: `"quantity=tag"` (`sweep.py:363`), `"!tag"` (`sweep.py:496`) and "give that value another tag" (`sweep.py:128`). `rank` says "value" (renamed in 1.5).
  - **A user sees:** one word meaning a Run's label, a curve's name and a value. `rank --baseline` asks for `quantity=value`, while `[plot].sets` and `--points` say `quantity=tag` for the same thing. A message can be read the wrong way: "a set's points are … tags" can be taken for Run tags.
  - **Urgency:** low. It is wording; nothing computes wrong.
  - **Size:** light planning and a decision. The messages are a quick sweep: "value" where a quantity's value is meant. But the `tag` key of a curve or merge entry is schema, so renaming it is a rename with an alias, refusal and `migrate`, like 1.3. Decide first whether the key keeps its name.
- **2026-11-10 · 2.2 · an errand's Run row counts its vetoed points.**
  - **Cause:** `rankcmd.runs_of` (`framework/runner/rankcmd.py:185–190`). It takes `good` as every point with a finite loss, vetoed or not. The Run's loss is the `over_pages` mean of their losses, and its best point is the least loss.
  - **A user sees:** with `gates = true` only, since phase 8 made gates opt-in. `rank` on an errand of several Runs can name a vetoed point as a Run's "best" and average vetoed losses into the Run's loss. The leaderboard says the same point is vetoed, so the two tables disagree.
  - **Urgency:** low. It needs gates on and an errand-level `rank`.
  - **Size:** quick fix plus one decision. The best is the rank-1 point; the loss is over passing points, with the vetoed counted beside. It changes a printed number only where gates are on.
- **2026-11-10 · 2.2 · a flat leaderboard judges "the same reference" by its label.**
  - **Cause:** `ranking._flat` (`framework/stats/ranking.py:655–664`) compares each cell's set of (object short name, `reference` column). The `reference` column is the reference curve's label ("data", or the first curve's label), not which histogram it is.
  - **A user sees:** two cells measured against different data under one label (two beams, two energies) are ranked as one order. A point's loss on the easier data then counts against points on the harder. Its rank says more about its cell than about the point, and the record says "flat … the same reference", which is not true. `test_plot_stage.py`'s em and ep cells are a case.
  - **Urgency:** medium. A real multi-beam study meets it, and the order it prints is wrong without any sign.
  - **Size:** proper planning. The reference's identity has to be in the table, as its path or a hash of its bins (`stats/table.py`). That is a column change: a format-4 table, the fallback for older tables (today's label rule, said in the record), and a sidecar change.
- **2026-11-10 · 5.2 · the per-metric detail tables average with their own mean.**
  - **Cause:** `bars._ranking`, `_crossed` and `_table_of` (`framework/plot/figures/bars.py:375`, `:406`, `:461`) average a point's pages with `bars._mean` (`bars.py:287`). That is the `over_pages` mean without page weights. Their notes (`RANKING_NOTE`, `TABLE_NOTE`, `CROSSED_NOTE`) say the rule in prose, where the engine's record should say it.
  - **A user sees:** with figure weights or `[ranking].weights` set, a metric's own section (`detail = true`, or a report naming a metric) gives a point a number weighted differently from the leaderboard's. Its "Made by" names `over_pages` but not that page weights are left out. Unweighted studies see no difference.
  - **Urgency:** low. Detail is opt-in, and weights are rare.
  - **Size:** light planning. The engine returns each point's per-metric mean over pages with page weights counting, as it returns `values`, and records it. bars draws that and drops `_mean` and the three notes.
- **2026-11-11 · 7.1 · with gates off, a broken point's noise hides real effects in the marginals.**
  - **Cause:** phase 8 made gates opt-in. `ranking.marginals` (`framework/stats/ranking.py:879`) leaves out vetoed points only (`alive = [p for p in known if not p.vetoed]`). A broken point is no longer vetoed, so it stays in its strata. Its ℓ = ln(0.01 + L) is about ln 12, and it varies by a unit or more between its strata, so the paired differences of every value it touches are noisy.
  - **A user sees:** on B1, dr32 (a jet radius far worse than the rest with gates on, ×0.66 ± 0.10) reads "indistinguishable from the best" by default (×0.84 ± 0.19). On B3, the broken PDF itself reads "indistinguishable from the best" on two strata (×0.36 ± 1.02). The leaderboard is right: broken points last, by loss. A marginal's headline can mislead whenever a study holds broken points, and the record does not warn of it.
  - **Urgency:** medium. It arises exactly when a study has broken curves, which is when a reader leans on the marginals to find the cause.
  - **Size:** light planning and a decision:
    - (a) the marginals leave out points whose integrity cost is past bad, counted as "broken" beside "vetoed", whether or not gates are on;
    - (b) say in the headline and the record that broken points are in;
    - (c) recommend `gates = true` for marginals.
    - (a) changes printed numbers, so it is the developer's call. The recommendation is (a) with (b): the leaderboard keeps its penalty, and the marginals compare like with like.

