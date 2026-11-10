# Phase 5: the leaderboard, the sections, and the record shown

Status: not started. Blocked by: phase 4. Source: [04](../plans/grand-ranking/04_Report.md), all of it; [02](../plans/grand-ranking/02_Metrics.md) for where a glyph goes; [03 §3 property 9](../plans/grand-ranking/03_Math.md). Names in code: [Tables](Tables.md) T4, T6, T7, T8.

The rule of this phase: **a presenter renders the record and writes no rule of its own.** `bars.py`, `rankcmd.py` and `report.py` hold no sentence about a mean, a gate, a weight or a compression except through `Method.lines`.

**Today:** `bars.summary_model` (`bars.py:778`) builds standings within cells (`_standings_tables` :543), a section a purpose (`_purpose_sections` :607), marginals (:689), baseline (:720), head to head (`_matches` :639). `_score_text` (:528) is hand-written prose. `webpage.render` (`webpage.py:241`) draws sections flat.

### Step 5.1: the summary model (Size: M)
- Acceptance:
  - **Sections, in order:** the front (facts, the reading key, "How these numbers were made", notes), `leaderboard`, `marginals`, `category-<c>` for each category with a metric on, `baseline` (when set), `head-to-head` (when asked). An empty section is left out.
  - **Leaderboard:** 04 §1's columns, flat or banded by R10, vetoed rows last under a rule and unnumbered, the PDF's cut by R14. Under it, **Metric values**: a row a point in the same order, a column a default metric, the median over the point's pages, shaded by cost.
  - **Marginals:** a table a quantity with 04 §2's columns, its headline line above.
  - **Categories:** the question, each metric with polarity, description and thresholds, one ranking by category cost with vetoed points last and marked.
  - **Polarity:** every number column's header carries its glyph; every table's first note is the legend line. The sentences "lower is better; darker: costlier" are gone from titles.
  - **Made by:** a line under every table, from `Method.lines` of the stages that shaped it (04 §Method's three examples are the shape, not text to copy). A setting off its default is said with its source.
  - **How these numbers were made:** 04 §Method layer 2, from the record: metrics, gates and every vetoed point with its evidence, the cost transform with one worked row (value → z → c, taken from the best point's first page), each mean named, every weight that is not 1 with its source, what was left out. `_score_text` is deleted.
  - `webpage.py` and the PDF path draw the new items with what they have; if a new item kind is needed (a rule in a table, a headline line), it is added to both.
- Files: `framework/plot/figures/bars.py`, `framework/plot/figures/webpage.py`, `framework/plot/figures/paper.py` if an item kind is added, `tests/runner/test_summary_layout.py`.
- Test, on the document model: the section keys and their order; the leaderboard flat on a built table whose cells share objects and reference, banded when one cell has another reference, with the reason in "Made by"; a vetoed point's row is last, unnumbered, with its reason; every table has a "Made by" item and the legend note; with `over_pages = "median"` the leaderboard's "Made by" says so and names `[ranking]`; no table title contains "lower is better". Each fails first.
- Check: `taskset -c 0-5 nice -n 10 python -m pytest -q tests/runner/test_summary_layout.py`, then the fast suite.
- Seam: `bars.summary_model`'s document, not the PDF.
- Blocked by: 4.2.

### Step 5.2: per-metric detail, opt-in (Size: S)
- Acceptance: `[ranking].detail` (default false). With it, each category's section is followed by each of its metrics' ranking, cells × curves table and object table, as today's sections hold them, as ordinary sections (R11). A report section's `<metric>`, `<metric>:ranking`, `:crossed`, `:table` keys still work, and ask for the detail of that metric alone.
- Files: `framework/plot/figures/bars.py`, `framework/runner/config.py`, `framework/schema/run.toml`, `tests/runner/test_summary_layout.py`, `tests/runner/test_report.py`.
- Test: without `detail`, no `<metric>-crossed` section key exists; with it, each default metric has its three. A report asking `chi2_sigma:crossed` gets it with `detail` off. Fails first.
- Check: `taskset -c 0-5 nice -n 10 python -m pytest -q tests/runner/test_summary_layout.py tests/runner/test_report.py`.
- Seam: the summary model's section keys.
- Blocked by: 5.1.

### Step 5.3: the completeness test, property 9 (Size: S)
- Acceptance: one parametrised test, `test_no_setting_moves_a_number_the_record_does_not_name`, in `tests/runner/test_stats_ranking.py`. On a built table of several pages, cells and quantities, for each case it changes one thing from its default and compares, before and after, (a) every number of the `Ranking` and its marginals and (b) `Method.as_dict()`. It fails in one case only: a number moved and `Method.as_dict()` did not. A record that changes while no number does passes (a setting may be recorded and have no effect on this table).
  - **The cases:** every key of `[ranking]`, taken from `schema.keys("ranking")` so a key added later is a case without anyone remembering; a set's `ranking = {…}` over the table; a figure's `weight`; each flag of `heimdall rank` that reaches the engine (`--by`, `--baseline`, `--trim`, `--head-to-head`, `--detail`). A key with no value given for it in the test's own table of example values fails the test by name, so a new key cannot be skipped.
  - When the record changes, the changed choice's `source` is the one that was set.
- Files: `tests/runner/test_stats_ranking.py`; `framework/stats/ranking.py` for whatever the test finds missing.
- Test: itself. To show it can fail, the step's log records one run with a choice deliberately left out of the record (not committed).
- Check: `taskset -c 0-5 nice -n 10 python -m pytest -q tests/runner/test_stats_ranking.py -k record`.
- Seam: `ranking.rank` and `Method.as_dict`.
- Blocked by: 5.1.

### Step 5.4: the report and the CLI (Size: M)
- Acceptance:
  - `report.HEADLINE` is `["leaderboard", "marginals", *("category:" + c for c in CATEGORIES), "baseline", "head-to-head"]`, and the test that held it to the purposes holds it to `CATEGORIES`.
  - The report's "How the numbers are made" takes its ranking paragraphs from the record of the tables it shows (`report.py:1723–1767`, `METHOD_NOTES` :1452); its hand-written `score` note goes.
  - `heimdall rank` gains `--head-to-head PAGE|all`, `--detail`, `--trim ALPHA`, `--method` (prints the whole record and no table). Under each terminal table, its "Made by" line. `--json` carries `method`. Headers carry glyphs by R15.
  - `heimdall plot --stats-only` and `heimdall report` accept `--head-to-head PAGE|all` (R16).
  - `complete.py` knows the new flags.
- Files: `framework/runner/report.py`, `framework/runner/rankcmd.py`, `framework/runner/cli.py`, `framework/runner/complete.py`, `framework/schema/report.toml`, `tests/runner/test_report.py`, `tests/runner/test_report_build.py`, `tests/runner/test_rank_cli.py`, `tests/runner/test_complete.py`.
- Test: `rank` on a scratch table prints a "Made by" line under the leaderboard and under each marginal; `--method` prints every stage's name; `--json`'s `method` equals the sidecar's; with stdout not UTF-8 the header is `point loss [v]`; `--head-to-head all` adds the section and the record names the flag as its source; a default report's statistics part has the sections in `HEADLINE`'s order. Each fails first.
- Check: `taskset -c 0-5 nice -n 10 python -m pytest -q tests/runner -m 'not slow'`, then `tests/integration/test_plot_stage.py` alone, then `tests/integration/test_report_draw.py` alone.
- Seam: `rankcmd.run` on a scratch work dir; `test_report`.
- Blocked by: 5.2, 5.3.

## Log
