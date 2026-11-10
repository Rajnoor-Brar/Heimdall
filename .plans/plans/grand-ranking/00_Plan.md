# Grand Ranking: gates, metrics, marginals and the report's order

Stage 2, a design plan for the developer (`docs/rules/work.md`). **Approved 2026-11-10:** every gate question was answered yes, with two additions:
- **5:** gates and cost normalisations are stated in the summary's and the report's notes.
- **6:** compression is done, and said.

Over all of it, the developer's rule: **transparency.** A reader is never left to guess how a value, a cost, a loss, a rank or a marginal was made. This covers:
- **weights**, of pages (figures, globs) and of metrics alike;
- **every averaging method:** within a category, across categories, across pages, and in marginals.

This holds as the **method record** (03 §3a, 04 §Method), and it is tested. Implementation waits for the developer's order.

Source: the developer's design-audit request of 2026-11-10 (five pillars), and I-136 ("the scoring, read by the developer"), which this plan answers in part.

| File | Holds |
|---|---|
| [01_Glossary.md](01_Glossary.md) | Pillar 4: the words, their collisions, and the rename table |
| [02_Metrics.md](02_Metrics.md) | Pillar 3: the metric catalogue, its renames, polarity and defaults |
| [03_Math.md](03_Math.md) | Pillar 2 and Pillar 1.2: the Grand Ranking and the quantity marginals, as formulas |
| [04_Report.md](04_Report.md) | Pillar 1: the sections, their order, what is default and what is opt-in, the notes |
| [05_Benchmarks.md](05_Benchmarks.md) | Pillar 5: the four benchmark Runs, what today's engine does on them, and what the proposed one does |
| `P1`…`P7` | the phases, for the implementation round that follows approval |
| `probe/bench.py` | the probe that made every number in 05, rerunnable on any Run's folders |

## Context: what the code holds (read 2026-11-10 at `4428c2a`)

The scoring engine exists and is sound in its structure. This plan keeps its spine and changes what it gets wrong on real data.

- **The pipeline.** A metric becomes a **cost** by its thresholds: 0 at or inside `good`, 1 at `bad`, linear beyond (`framework/stats/metrics.py:104`). A purpose's value is the RMS of its costs. A page's **loss** is the RMS over purposes (`framework/stats/score.py:262`). A point's **score** is `[score].mean` (RMS) of its page losses (`score.py:312`). Every step reads one curve's row alone, so a score is pool-independent (V251). That property is kept: it is what lets scores compare across Runs and the library.
- **One default per purpose is a rule, held by tests.** Exactly five metrics are `default=True`: `chi2_ndf`, `norm`, `shape`, `tilt` and `worst` (`metrics.py:534-595`). `tests/runner/test_stats_registry.py:42` asserts exactly those five. `tests/runner/test_stats_score.py:80` takes `[0]` of a purpose's defaults, so it assumes one each. The `similarity` and `quality` purposes have no default.
- **Head to head is already opt-in.** `[score].head_to_head` names pages, and the summary draws nothing without it (`framework/plot/figures/bars.py:643`). No CLI flag asks for it: `heimdall score` has `--set`, `--by`, `--baseline` and `--json` only.
- **The standings are ranked within each page cell, never across.** This is `_standings_tables` (`bars.py:543`), with the note "Points of different page cells never meet" (`bars.py:44`). On a Run with 36 cells of 8 curves, there is no leaderboard of its 288 points. Yet the costs are pool-independent, and every cell is measured on the same objects against the same data.
- **A marginal is an RMS, while its note says "the mean".** `marginals()` aggregates with `st.mean` (`score.py:497`), RMS by default. The summary's note says "the mean of the scores" (`bars.py:708`), so the two contradict each other: the code is an RMS. An RMS follows the worst member of the slice. On B1, half of every jet-radius slice is pathological, and the marginal reorders at random (05 §3).
- **A veto exists, but only as a loss threshold.** `[score].veto` flags a point whose worst page loss is above a number (`score.py:315`). It does not reorder anything, and it is off by default.
- **Duplicates in the catalogue.** `wmape_yield` returns `rel_abs_area` (`metrics.py:324`). `wmape_axis` is `ratio_dev`'s formula line for line (`metrics.py:247`, `:329`). They sit in two different purposes.
- **Names that collide.**
  - `shape` is both a purpose and a metric.
  - `worst` is a metric and also the "worst page" column.
  - `norm` (the metric), `[score].normalise` (the cost transform) and the page key `normalise = "area"` are three things.
  - A "score" is lower-is-better.
  - "axis" means both a swept quantity (`[score].by`, the sidecar's `axes`) and a plot axis.

  The full audit is in 01.
- **The summary does not read figure weights.** `bars.py:788` calls `S.score(rows, st)` without `figure_weights` (V262 says so, and I-136 lists it).
- **Thresholds were set on a null, "to be tuned on real studies" (V254).** On the four benchmarks every ordinary point is past `bad` on χ²/ndf and tilt (medians 5–10 and 0.9–1.9, against bad = 3 and 0.25). So the hinge's slope 1/(bad − good) decides which purpose owns the score: trend owns 41–81 % of it, shape 0–1 % (05 §2).

## What the benchmarks showed (05 has the numbers)

1. **Today already sinks the pathological points, for the wrong reason, and its rankings by purpose invert.** The Sherpa + MSHT20qed_lo points have yields of up to 10¹¹ × the data. Their χ²/ndf is about 1, because their error bars are as large as their excess. In the "Statistical compatibility" section they take ranks 1–12 of 24 (B1), 1–6 of 24 (B2) and 1 of 16 (B3). Their scores sink only through `norm`, whose linear cost reaches about 170.
2. **One gate isolates every pathological point, with no tuning:** a bin at least 10³ × its reference on any page. Pathological points fail it on 12 of 12 pages; ordinary points on 0, across all four Runs and 4224 curves. Yield ≤ 0 and |ln yield ratio| ≥ ln 10 each catch only some pages.
3. **Pairing χ² with the reference-anchored Poisson deviance fixes the inversion.** The same points move to ranks 13–24, 19–24 and 16 in the compatibility ranking.
4. **The default `shape` is nearly mute against data with 10–20 % errors.** Its shrinkage τ = 0.10 counts a bin with σ_ℓ = 0.2 at a fifth. Its median is 0.04–0.12 where the unshrunk mean |ratio − 1| is 0.3–0.5.
5. **Compressing costs, log₂(1 + z), steadies the ranking** under a page bootstrap in three Runs of four (B2 0.854 → 0.882, B3 0.907 → 0.932, B4 0.939 → 0.966; B1 0.945 → 0.936). The proposed metric set spreads the score over the purposes: no purpose above 42 %, against 81 % today.
6. **Gated, trimmed and matched marginals separate the trends that RMS marginals blur.**
   - B4: lepton PDF on beats off by ×0.86 ± 0.02 over 144 strata. p_T,ref 24–28 is clearly worse, and 30–40 is a plateau. The LO PDF sets beat the NLO and NNLO ones.
   - B1: once gated, the jet radius trend shows dr32 about 38 % worse, where today's marginal was noise.
   - B3: today blames MSHT20qed_lo for both generators. Matched by generator, its Pythia point is fine.

## Options and recommendation, by pillar

| Pillar | Options | Recommended |
|---|---|---|
| 1.1 Defaults | (a) keep one a category; (b) a curated pair where the evidence earns it | **(b)**, 9 scored metrics and 2 gates (02 §Defaults) |
| 1.2 Section flow | (a) today's standings, then purposes; (b) leaderboard, then marginals, then categories, then opt-in detail | **(b)** (04) |
| 1.3 Head to head | (a) as is, `[score]` only; (b) also `--head-to-head` on the CLI | **(b)**: it is already opt-in, so this adds only the flag |
| 2.1 Normalisation | (a) linear hinge; (b) compressed hinge, log₂(1 + z); (c) ranks within the pool | **(b)**: it stays pool-independent (c is not), and bounds one metric's reach |
| 2.2 Bad actors | (a) a loss veto; (b) integrity gates, lexicographic: a vetoed point ranks after every other | **(b)** |
| 3 Names | (a) display names only; (b) ids renamed too, with an alias table and a migrate | **(b)** (02) |
| 4 Words | (a) define the collisions in the glossary; (b) rename to one word, one meaning | **(b)** (01) |
| Marginals | (a) a trimmed mean of each slice's losses, as asked; (b) that level, beside the matched effect (each point against its own stratum), which orders the table | **(b)** (03 §2) |

## Gate: every decision, asked at once (yes accepts the recommendation)

**Answers, 2026-11-10:**
- 1, 2, 3: rename.
- 4: yes.
- 5: yes. The gates and the cost normalisation are named in the notes of every table they shape.
- 6: yes, and the compression is said wherever a cost or loss is shown.
- 7, 8, 9, 10: yes.
- Added, over all: the method record (transparency).

1. **The point's number is a loss, not a score.** `score` → `loss` in every user-facing word; `[score]` → `[ranking]`; `heimdall score` → `heimdall rank`. The old names are refused, naming the new, and `heimdall migrate` rewrites errand files. *(Alternative: keep `score`, add arrows.)*
2. **"purpose" → "category",** your word, in code, the sidecar, the summary and the docs.
3. **Metric ids are renamed** as in 02 (`norm` → `log_yield_ratio`, `worst` → `peak_pull2`, …). Old ids stay readable in old `statistics.csv` and sidecars through an alias table. In settings they are refused, naming the new id, and `migrate` rewrites them. The duplicates `wmape_yield` and `wmape_axis` go.
4. **The default set** is the curated one in 02. Scored: `chi2_sigma`, `poisson_dev` · `log_yield_ratio` · `log_dev_shrunk`, `log_dev_l4` · `tilt`, `pull_autocorr` · `peak_pull2`, `log_ratio_roughness`. Gates: `peak_bin_ratio` and `yield_sign`. `n_eff` is shown, not scored.
5. **Integrity gates are on by default and lexicographic.** A point that fails a gate on any page ranks after every point that passes, whatever its loss, with the reason beside it. Gate levels: a bin at 10³ × reference; a page yield ≤ 0 on a cross-section page (a normalised page's yield is 1 and needs no gate). The `veto` loss threshold stays as an optional extra gate.
6. **Costs are compressed,** c = log₂(1 + z): 0 within good, 1 at bad, 2 at three times bad's excess. Every score changes, so the summary fixtures change with it (P3).
7. **Marginals:** gated, a 20 % trimmed mean of ln loss over each slice. The table is ordered by the matched effect (each point against its stratum's mean), and each value is compared with the best by a paired trimmed difference ± SE. Small n follows 03 §2.4.
8. **The leaderboard is flat across cells** when every cell is measured on the same objects against the same reference. When they are not, it falls back to today's bands.
9. **Per-metric detail is opt-in:** each metric's crossed and object tables go behind `[ranking].detail = true` or `--detail`. Each category keeps one ranking in the default view.
10. **After implementation, the real study's four benchmark Runs are rescored** (`heimdall plot … --stats-only`, which rewrites their `statistics/` and `.cache/…/plots/`). A snapshot comes first, then a comparison of before and after. *(Alternative: rescore only in scratch copies.)*

**Assumptions** (they stand unless corrected):
1. Pool-independence of a point's loss stays the rule (V251). Ranks and marginals are pool-dependent by nature, and say so.
2. The hinge thresholds stay as V254 set them. Only new metrics get thresholds, from the benchmarks' ordinary curves (02 says each and why). Retuning the old thresholds is a later issue.
3. `shape`'s shrinkage τ is not retuned here. Its muteness is covered by pairing it with `log_dev_l4`, and filed as an issue.
4. No change to identity, seeds, Paint or any binary: the new metrics come from the measured bins already written. The two benchmark Runs without measured bins were re-measured into scratch for this plan.
5. `[stats]`, `statistics.csv` and `--stats-only` keep their names. "statistics" is the table of metric values (01).
6. The aggregations stay RMS (p = 2) inside a category, across categories and across pages. The benchmarks showed no gain from p = 3 (05 §2).
7. `aggregate = fisher | topsis | promethee` and `normalise = median | mad | minmax | surprisal` stay as opt-in, renamed under `[ranking]`, unchanged in meaning.
8. The plan folder is committed as written, with the gate open.

**Out of scope:** retuning V254's thresholds; Paint; set merges (I-133); the points library; pool-dependent ranking as a default; the report's typesetting beyond section order and headers.

## Decision log

| Decision | Chosen | Why |
|---|---|---|
| Keep the cost → category → page → point spine | kept | pool-independent, already tested, and the benchmarks fault its inputs, not its shape |
| Gate on the largest bin's ratio to its reference | 10³ (3 decades) | ordinary curves reach 10^2.01 at most, pathological 10^10.7 at the median; one gate, no tuning (05 §1) |
| Order of a vetoed point | after every passing point; among vetoed, by failed pages, then loss | a terrible page cannot be bought back by good ones, and the order inside the vetoed stays readable |
| Compression | log₂(1 + z) | 0 and 1 stay where they were (good, bad), the far tail becomes decades, stability rose in 3 of 4 Runs |
| Marginal statistic | trimmed mean of ln loss, ordered by the matched effect | ln makes effects ratios that compare across Runs; matching removes the strata's difficulty, the imbalance the gate creates included (B3) |
| Transparency | the engine returns a method record of every choice it applied; the summary, report, `rank` and `--json` render it; a test fails when a setting changes a number and the record does not name it | the developer's rule (2026-11-10). Notes written beside the code drift: today's marginal note says "mean" over an RMS |
| Trim | α = 0.2, g = max(1, ⌊αn⌋) for n ≥ 3, none for n ≤ 2 | Wilcox's standard 20 %. Rank stability changed little over α ∈ {0, 0.1, 0.2, 0.25, median} once gated (05 §3) |

## Not yet specified

- P3: the thresholds of `pull_autocorr` and `log_ratio_roughness` on data with 10–20 % errors. They are kept from the registry. Whether they need retuning is read off the benchmarks at P7, not guessed.
- P5: how the HTML summary collapses the per-category detail (a `<details>` element, or a separate page). Fog, to be decided at its pickup from `webpage.py`'s structure.
- P7: whether the developer wants the four Runs' rescored summaries kept, or only the comparison. Asked at the gate, question 10.

## Always / Never

- **Always:** every number traceable to how it was made, from the engine's own method record, never from prose written apart from the code (03 §3a); pool-independent losses; every number shown with its polarity; vetoed points visible, never dropped; n and the trimming beside every marginal; old tables still readable.
- **Never:** a rebuild; a change to identity or seeds; writing into a work dir without the gate's yes (question 10) and a snapshot; naming the study in docs or history; editing `docs/stable/` (live docs only, until a crystallise is ordered).

## Execution map (for the round, after approval)

| Phase | Verified when | Blocked by | Size |
|---|---|---|---|
| [P1 Names and polarity](P1_names.md) | the registry carries ids, titles, polarity and category; old ids read; settings refuse old names; fast suite green | none | M |
| [P2 Integrity gates](P2_gates.md) | `peak_bin_ratio`, `yield_sign`; vetoed points rank last; the probe isolates B1–B3's pathological points | P1 | S |
| [P3 Compressed costs and the default set](P3_costs.md) | compression; 9 defaults; tests rewritten together with their fixtures | P2 | M |
| [P4 Marginals](P4_marginals.md) | trimmed, gated, matched, paired against the best; small-n rules; unit tests on built designs | P3 | M |
| [P5 Leaderboard and sections](P5_report.md) | flat leaderboard; section order; `--head-to-head`, `--detail`; report HEADLINE | P4 | M |
| [P6 Docs](P6_docs.md) | live doc `live-grand-ranking`; generated reference; glossary changes in the live doc | P5 | S |
| [P7 Benchmarks](P7_benchmarks.md) ⏸ | the probe's expectations in 05 hold on the implemented engine; the developer reads one summary (I-136) | P6 | S |

## Progress

| Phase | Status |
|---|---|
| Plan | written 2026-11-10; approved 2026-11-10 with the transparency rule; implementation waits for the order |
| P1–P7 | not started; the implementation round is planned in [../../implementation/00_Plan.md](../../implementation/00_Plan.md), hardened 2026-11-10, waiting for the order |
