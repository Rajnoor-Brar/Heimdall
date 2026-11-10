# Implementation round 2: the Grand Ranking

Status: planned 2026-11-10 from the approved design plan, and hardened the same day against the code at `db72aa7`; started 2026-11-10 on the developer's order.

Stage 3 of `docs/rules/work.md`. The source is [`.plans/plans/grand-ranking/`](../plans/grand-ranking/00_Plan.md) (stage 2, approved 2026-11-10). The design files own the formulas and the tables: this round links to them and never restates one. Where this file and a design file disagree, this file is the later decision and says so under [Found while planning](#found-while-planning-verified-at-db72aa7).

The implementing agent cannot ask. Every decision is below. A surprise is handled by the [stop rule](#when-something-does-not-fit).

**Read in this order:** this file; [Tables](Tables.md), which holds every name, signature, caller and line the steps cite as T1–T10; then the phase file of the step in hand, and nothing ahead of it. A step's acceptance names what to build; Tables names what it is called; the design files say what it means.

## The gate (developer, 2026-11-10)

| # | Question | Decided |
|---|---|---|
| 1 | score → loss, `[score]` → `[ranking]`, `heimdall score` → `heimdall rank` | rename |
| 2 | purpose → category | rename |
| 3 | metric ids as [02](../plans/grand-ranking/02_Metrics.md), with an alias table and a migrate | rename |
| 4 | the curated default set of 02 | yes |
| 5 | integrity gates, on by default, lexicographic | yes, **and gates and cost normalisations are named in the report's and the statistics' notes** |
| 6 | compressed costs, log₂(1 + z) | yes, **and it is said wherever it applies** |
| 7 | gated, trimmed, matched marginals | yes |
| 8 | a flat leaderboard when cells share objects and reference | yes |
| 9 | per-metric detail is opt-in | yes |
| 10 | rescore the four benchmark Runs after a snapshot | yes |

**Over all of it, the developer's rule: transparency.** Whatever the backend does, a reader must not be left to guess how a value or a loss was made. It covers weights (of plots and of metrics), every aggregation and the averaging method used. It is built as the method record ([03 §3a](../plans/grand-ranking/03_Math.md), [04 §Method](../plans/grand-ranking/04_Report.md)) and held by a test (step 5.3).

**Assumptions that stand** (the design's eight, [00_Plan](../plans/grand-ranking/00_Plan.md) "Assumptions"), plus this round's:
1. V254's thresholds are kept. Only new metrics get thresholds (02).
2. `log_dev_shrunk`'s τ is not retuned.
3. No identity, seed, Paint or binary change. Nothing is rebuilt.
4. RMS inside a category, across categories and across pages.
5. The opt-in aggregators and cost transforms keep their meaning.
6. Code renames go as far as the words do: modules and tests are renamed too (R1).
7. An old name in a record's snapshot is read, not refused (R9). This narrows gate answer 1, and the report at the round's end says so.
8. Python is 3.10 or later (the base is 3.12, `recipes/settings.toml:11`): `kw_only` dataclasses and `X | None` are used.

## Found while planning (verified at `db72aa7`)

Each is a difference between the design plan and the code, with what the round does about it.

- **`means.trimmed` already exists** (`framework/stats/means.py:193`): a weighted mean with fractional trimming, α = 0.25, registered as a page mean. The design's `trimmed(values, alpha) → (mean, se, n, g)` would shadow it. → the new function is `means.trimmed_se` (R2).
- **No `score.rank` and no `Method` exist.** The engine's entry is `score.score` (`score.py:298`). → `rank` replaces it (R1, R3).
- **A figure's `weight` reaches no score today.** The schema has the key (`framework/schema/run.toml:1248`) and the engine takes `figure_weights` (`score.py:165`), but nothing in `framework/` builds that dict: `bars.py:788`, `scorecmd.py:84` and `statstable.py:89` all call without it. → step 3.3 builds it at plot time and writes it to the sidecar.
- **A `Curve` does not know its page is normalised** (`framework/stats/bins.py:15`), which `yield_sign` needs. → R4.
- **Four old ids are fixed table columns, not only registry metrics:** `rel_abs_area`, `area_ratio`, `ratio_mean`, `ratio_dev` (`framework/stats/table.py`, `STATISTIC_COLUMNS` and `statistics_of`). → renamed in step 1.2 with the rest.
- **Three places hard-code ids:** `null_p` (`score.py:134`: `chi2_ndf`, `chi2_z`, `tail`), the Fisher aggregator (`score.py:342`), `plot.STATISTIC_LABELS` (`plot.py:1087`). → step 1.1 and 1.6.
- **Two notes are prose apart from the engine:** `_score_text` (`bars.py:528`) and the marginal note "the mean of the scores" over an RMS (`bars.py:708`). → both go, replaced by the record's rendering (5.1).
- **The rename reaches further than the design's file list:** `config.py` (`Errand.score` :140, `check_score` :1410, `SUMMARY` :1454, `REPLACED` :1456), `plotdoc.py` (`score` in plot.toml, :73, :170, :533, :561), `house.py` (`explain score`, :205), `schema.py` :35, `v3.py` :36 and :386, `docs.py` :121, `knowledge.py` :199, `complete.py` :45 and :62, `plot.py` (`legend_statistic`, figure kind `statistic`). → P1's steps name each.
- **Every older Run's snapshot holds the old names.** A record's `config/` is the errand file as it ran (`record.write_snapshot`, `record.py:723`), and `plot`, `status` and `report` load it. A loader that refuses `[score]` or `legend_statistic` breaks every such record. Round 1 met the same wall with the dialects. → R9.
- **The opt-in cost transforms are not "on z before compression"** as 03 §1.2's last line says. Today `median`, `mad` and `minmax` work on the oriented value over the page's pool, and `surprisal` on a null p (`score.py:195–221`); none of them hinges. → kept exactly as today, uncompressed, and the record says so (R19).
- **03 §1.4 orders the vetoed by "F(p) descending",** which would put the point with the most failed pages first among them. → fewer failed pages first (R21).
- **`Settings` and `Figure` are built positionally** (`score.py:90–93`, `plot.py:126–131`), so a new field in the middle shifts every argument. → keywords (R22).
- **`heimdall migrate` rewrites records today:** `errand_changes` (`migrate.py:1422`) rewrites each record's snapshot, each Run's `plot.toml` and `report.toml`, with the configs. The earlier draft's "a snapshot is never rewritten" was wrong as a statement of what migrate does. → this round's rename joins the configs branch only (R23); the developer may widen it.
- **The summary ranks a second time.** `statstable.write_set` (:77) writes the table, then `bars.summary_model` (:788) scores the rows again. → one `rank` call, handed on (3.3, T8).
- **A figure's key is `class`, not `kind`** (`config.py:1622`, `run.toml:1169`); `Figure.kind` is the field's name in code only. A metric figure's folder on disk is `statistic/`. → R24.
- **`runner/__init__.py`'s `RANKS` names `scorecmd`.** → renamed with the module (1.5).
- **`webpage.py` has no collapsing element** (`render`, :241, draws sections flat). → R11.
- **`stats/__init__.py`'s docstring is stale** (it lists bins, metrics, means only). → fixed in 1.5.
- **The design cites "03 §4" for the method record; the heading is §3a.** → corrected in the design plan with this round's commit.
- **Code may not cite a plan.** `tests/runner/test_docs.py:275` refuses `I-<n>`, `.plans/` and `0N §n` in code and tests. A comment says the rule in words.

## Execution map

Test command, from the checkout with the stack loaded (`source gjallarhorn.sh`): `taskset -c 0-5 nice -n 10 python -m pytest -q <files>`. One pytest session at a time. The fast suite is `tests/runner -m 'not slow'`. A slow test runs alone.

| # | Phase | Verified when | Blocked by | Size |
|---|---|---|---|---|
| 0 | [Baseline](P0_baseline.md) | the fast suite's state and the engine's numbers on the fixtures are written down | none | XS |
| 1 | [Names and polarity](P1_names.md) | new ids, categories and polarity in the registry; format 3 tables, old ones read; `[ranking]`, `heimdall rank`; old names refused in a user's file and read in a record; `migrate` rewrites; fast suite as the baseline | 0 | M, split 1.1–1.7 |
| 2 | [Integrity gates](P2_gates.md) | the gate metrics; `rank` with its method record; a vetoed point after every passing one | 1 | S, 2.1–2.2 |
| 3 | [Costs, defaults, weights](P3_costs.md) | oriented, compressed costs; the nine defaults; figure weights reach the loss | 2 | M, 3.1–3.3 |
| 4 | [Marginals](P4_marginals.md) | `trimmed_se`; gated, matched marginals with the small-n rules | 3 | M, 4.1–4.2 |
| 5 | [Leaderboard, sections, the record shown](P5_report.md) | 04's sections; "Made by" lines; the completeness test; the report and the CLI | 4 | M, 5.1–5.4 |
| 6 | [Docs](P6_docs.md) | `docs/live/grand-ranking.md`; the reference regenerated; `test_docs` green | 5 | S |
| 7 | [Benchmarks](P7_benchmarks.md) ⏸ | 05's six acceptance items on the engine; the four Runs rescored after a snapshot | 6, and the developer | S, 7.1–7.2 |

Frontier: one step at a time, in the table's order. Nothing runs in parallel: every phase edits `framework/stats/`.

**Milestones.** One pause, after phase 6: report what holds, the open Implementation_Issues, and ask for the four benchmark Runs' addresses (they are never written in this repo). Phase 7 reads and then writes a real study's work dir, so it runs only on that order. A phase's state goes in its file's log and in Progress as it lands.

## How a step is done

- **One concern per commit, staged by path.** Never `git add -A` or `-a`, never `.codex/`. Never push. The message ends with a `Co-Authored-By:` line naming the model that did the work.
- **A test that proves a change fails on the old code first.** The step's log says so, with the failure's first line.
- **Tests and fixtures change together,** in the step that needs the change. A fake has the real type.
- **The live doc is written at phase 6,** not per step: the names move under it until phase 5 ends. Each step's log lists what a reader may now rely on, and 6.1 writes the doc from those lists. This is the one departure from "its live doc in the same commit", decided here (R12).
- **Mark the source.** When a step closes an item of the ledger, append ` · closed <step id>` to that item's heading or row in its design file, in the same commit.
- **Write the log.** The phase file's log gets the step's state: what holds and the check that proved it. An off-plan decision goes in [Implementation_Notes.md](Implementation_Notes.md), an open finding in [Implementation_Issues.md](Implementation_Issues.md).
- **Scratch only.** Tests write `forge/scratch/` through the `HEIMDALL_*` variables. No step before 7.2 writes into a work dir.

## When something does not fit

- A named check fails and the fix is inside the step's files and scope: fix it, note it.
- The fix is outside the step's scope, or would change a decision here: do not build it. Write an Implementation_Issues entry (what failed, the output, what it blocks), mark the step `blocked` in Progress, and go on with the steps it does not block.
- A test run fails or is interrupted: restore nothing, record the state, go on as above.
- Never resolve one by touching what the Never list holds.

## Decision log

| # | Decision | Chosen | Why |
|---|---|---|---|
| R1 | Module and test names | `framework/stats/score.py` → `stats/ranking.py`; `framework/runner/scorecmd.py` → `runner/rankcmd.py`; `tests/runner/test_stats_score.py` → `test_stats_ranking.py`, `test_score_cli.py` → `test_rank_cli.py`, `test_score_settings.py` → `test_ranking_settings.py`. By `git mv`, in step 1.5. The design's `score.rank` is `ranking.rank` | one word, one meaning (01) holds in code too; a `score` module that returns losses is the collision the rename removes |
| R2 | The trimmed mean with its error | `means.trimmed_se(values, alpha=0.2) -> Trimmed(mean, se, n, g)`, a NamedTuple; not in `means.REGISTRY`. `means.trimmed` is untouched | the existing name is a page mean with other semantics, in use by `over_pages` |
| R3 | The engine's entry | `ranking.rank(rows, settings=None, page_weights=None, values=None) -> Ranking`, the shapes as T7. `ranking.score` and `Scores` go; every caller of T8 moves in the same step (2.2) | one entry, so the record cannot be skipped |
| R4 | A normalised page | `bins.Curve` gains `normalised: bool = False`; `bins.curves(made, logx, normalised=False)`; `table._add_metrics` passes `bool(page.document.get("page", {}).get("normalise"))`. `yield_sign` is NaN on a normalised page | the gate is defined only on a cross-section page (03 §1.1) |
| R5 | `Metric`'s fields | `category`, `polarity` (`lower`, `higher`, `one`, `descriptor`), `scale` (`linear`, `log`), `default` (scored by default), `shown` (computed by default, not scored), `gate: float \| None` (the curve fails at value ≥ gate). `peak_bin_ratio`: gate 3.0, thresholds (1.0, 3.0), not scored by default. `yield_sign`: value 1.0 or 0.0, gate 1.0, no thresholds (R20). `n_eff` keeps its thresholds (1000, 100) and is `shown`, not `default`. `table.default_metrics()` is every metric with `default`, `shown` or `gate` | "nine scored, two gates, two shown" (02) needs three flags, not one |
| R6 | A table without a column the settings need | never an error. A gate whose column is missing is "not evaluated: no `<id>` column (a table written before format 3)". A scored metric missing is "not in this table". Both are rows of the method record and lines of "How these numbers were made" | old tables stay readable, and the reader is told what was not applied |
| R7 | The sidecar, format 3 | keys `format = 3`, `columns`, `metrics` (each `category`, `polarity`, `phrase`, `scale`, `thresholds`, `default`, `shown`, `gate`, `note`, `why`), `ranking` (the merged table), `ranking_sources` (`{key: "[ranking]" \| "set <name>"}`, a key of the merged table each; written by `statstable.write_set`, which knows which table a key came from), `values` (`{point: {quantity: value}}`), `page_weights` (`{page: weight}`, figure weights only), `merged`, `method`. `table.upgraded(side)` reads format 2: `score` → `ranking` with its keys and ids renamed, `axes` → `values`, `purpose` → `category`, `better` → `polarity` (`none` → `descriptor`) | one reader for old and new; the source of each choice survives the file |
| R8 | Where a choice came from | `Settings.sources: dict[str, str]`, a key of `[ranking]` to `default`, `[ranking]`, `set <name>` or `--<flag>`. `settings_of(table=None, flags=None, sources=None)` fills it by T7's rule; today's second parameter `over` goes at 2.2, and callers lay a set's table with `overlaid` first. A `Choice.source` may also be `registry` (a metric's own thresholds, polarity, gate level), `figure <name>` (a page's weight) or `table` (what the table holds or lacks) | the record's "source" column (03 §3a) |
| R9 | Old names | In a file under `configs/` and in a report recipe: refused, "renamed: `<old>` is `<new>`; heimdall migrate rewrites it". In a record's snapshot and a Run's `plot.toml`: mapped to the new name on read, with one line said once a command, "read old names from the record (`[score]` → `[ranking]`, …)". One function, `config.renamed(raw: dict, where: str, recorded: bool) -> dict`, does both, from one table of old → new. It is built in step 1.3 and each later step adds its names to it. A file is a record when `paths.in_record()` holds (`HEIMDALL_CONFIGS` points at a folder with `snapshot.toml`), when it is a Run's `plot.toml`, or the `report.toml` beside one; a lenient load (`strict=False`) maps too. Step 1.3 gives every call site | refusing in a snapshot would break `plot`, `status` and `report` on every older Run; one table, so the reader, the refusal and `migrate` cannot disagree |
| R10 | Flat or banded | flat when, over the scored rows, every cell has the same set of `object` and the same `reference`. Else banded by cell as today. The record's Order row gives the reason either way | 04 §1 |
| R11 | Detail in the HTML | `detail = true` adds the per-metric sections as ordinary sections, in the PDF and the HTML alike. No collapsing element | settles the design's fog with the least mechanism; default off keeps the page short |
| R12 | The live doc | once, at phase 6 | see "How a step is done" |
| R13 | Ties | two losses share a rank when `f"{L:.3g}"` is equal: 1, 2, 2, 4. Tied points are ordered by name | 03 §1.4's "display precision", fixed |
| R14 | Long leaderboards | the PDF shows the first 25 and every vetoed row, and says "n more in the HTML and `--json`". The HTML and `--json` show all | 04 §1 |
| R15 | Glyphs in a terminal | the Unicode glyphs when `sys.stdout.encoding` is UTF-8, else 02's ASCII forms | 02 |
| R16 | `rank` flags over settings | a flag overrides the key for that call and is a source `--<flag>` in the record | 04 |
| R17 | Thresholds of `pull_autocorr` and `log_ratio_roughness` | kept from the registry. 7.1 writes their share of the loss on B1–B4 into its log; a retune is an issue, not a step | the design's "Not yet specified" |
| R18 | The rescored summaries | kept in the work dir (they replace the old ones); the snapshot of the old `statistics/` stays in `forge/scratch/grand-ranking/before/` until the developer has read the comparison | gate answer 10 |
| R19 | The opt-in cost transforms | `median`, `mad`, `minmax`, `surprisal` compute exactly as today's `_cost_column` (`score.py:195–221`), with `Metric.scored` renamed `Metric.oriented`: on the oriented value over the page's pool (or the null p), not hinged, not compressed. Only `cost = "thresholds"` gets log₂(1 + z). The record's Cost stage says which transform ran, that it is pool-dependent, and that it is not compressed | assumption 5: the opt-ins keep their meaning. 03 §1.2's last line described them wrongly |
| R20 | A gate's test | a page fails a gate when the metric's value is finite and ≥ `Metric.gate`, or is +∞. NaN never fails. `yield_sign` returns 1.0 for a non-positive yield on a cross-section page, else 0.0 | one comparison for every gate |
| R21 | The order, exactly | sort key `(group, failed, loss, point)`: `group` 0 for a point with a loss and no failed page, 1 for a point with no scored page, 2 for a vetoed point; `failed` is `failed_pages` in group 2, else 0; `loss` with NaN as +∞; `point` the name. So among the vetoed, fewer failed pages come first, then the smaller loss. Banded (R10): the same key within each cell, cells in the rows' order. `rank` numbers group 0 only | 03 §1.4's intent ("the worse, the later"); its "descending" read literally would put the worst vetoed point first |
| R22 | Construction | `Settings` is `@dataclass(frozen=True, kw_only=True)` and built by keyword from 1.5; `plot.Figure(...)` and `plot.Page(...)` are built by keyword from 3.3 | a field added in the middle must not shift a positional argument silently |
| R23 | What `migrate` rewrites for this rename | files under `configs/` only (errand files and a user's recipes), by `migrate.ranking_text` in `errand_changes`' configs branch. Not a record's snapshot, a Run's `plot.toml` or `report.toml`: those read through `config.renamed`. Earlier renames did rewrite records; the round's report flags this for the developer | a record is read by every checkout, and rewriting it changes snapshot digests for no gain when the reader already maps |
| R24 | Paths of a metric figure | nothing on disk moves: Paint's object `/statistic/<name>`, the cache folder and `folders.pages / "statistic" / <name>` (`plot.py:1991`) keep the word, as string literals. Only keys, field names and labels change | a moved folder orphans every drawn figure of every older Run |

## Ledger: every item of `.plans/plans/grand-ranking/`

"→ n.m" is built in that step. "→ Postponed" is in [Postponed.md](Postponed.md). "closed" needs nothing more.

**`00_Plan.md`:** Context's eight findings → 1.1 (duplicates, collisions), 2.2 (the veto), 3.2 (one default a category), 3.3 (figure weights), 4.2 (the marginal that is an RMS), 5.1 (standings within cells), 5.4 (the head-to-head flag) · gate answers 1–3 → P1 · 4 → 3.2 · 5 → 2.1, 2.2, 5.1 · 6 → 3.1, 5.1 · 7 → P4 · 8 → 5.1 · 9 → 5.2 · 10 → 7.2 · the transparency rule → 2.2, 3.1, 4.2, 5.1, 5.3 · assumptions 1–8 → stand (above) · "Not yet specified": P3 → R17 · P5 → R11 · P7 → R18 · "03 §4" → corrected at planning · out of scope: V254's retune, τ → Postponed.

**`01_Glossary.md`:** the collisions → 1.1 (ids), 1.4 (category), 1.5 (loss, ranking, quantity, `veto_loss`, `cost`, `over_pages`), 1.6 (`metric`, zero line) · the rename table, row by row → the same steps · "tag → value" in messages → 1.5 · the terms missing from the glossary → 6.1 (the live doc), the stable glossary → Postponed (the next crystallise).

**`02_Metrics.md`:** polarity and its glyphs → 1.1; where the glyph goes → 5.1, 5.4, 1.5 (`explain`) · the catalogue's ids, titles, notes → 1.1 · `peak_bin_ratio`, `yield_sign`, `negative_share` → 2.1 · the removed duplicates → 1.1 · new thresholds → 2.1 · the defaults → 3.2 · the alias table: reading → 1.2, writing → 1.2, settings → 1.5, migrate → 1.7 · I-26's table of retired names → Postponed.

**`03_Math.md`:** §1.1 → 2.1, 2.2 · §1.2 → 3.1 (its last line, the opt-ins → R19) · §1.3 → 3.1 (category, page), 3.3 (pages' weights) · §1.4 → 2.2 (the order among the vetoed → R21) · §2.1–2.2 → 4.2 · §2.3 → 4.1, 4.2 · §2.4 → 4.2 · §2.5 → 4.2, 5.1 · §3a, stage by stage: Gates, Order → 2.2 · Metrics, Cost, Category, Page loss, Opt-in aggregators → 3.1 · Pages → 3.3 · Marginals → 4.2 · where it lives → 2.2 (`--json`), 3.3 (sidecar), 5.1 (summary), 5.4 (report, `--method`) · §3 properties: 3 → 2.2 · 1, 2, 4, 5 → 3.1 · 8 → 4.1 · 6, 7 → 4.2 · 9 → 5.3.

**`04_Report.md`:** the sections and their order → 5.1 · §1 Leaderboard and Metric values → 5.1 · §2 → 5.1 · §3 → 5.1; `detail` → 5.2 · §4 Baseline, §5 Head to head → 5.1; the flags → 5.4 · Notes → 5.1 · Method, both layers → 5.1; in the report and `rank` → 5.4 · Settings and flags → 1.5 (renamed keys), 2.2 (`gates`, `veto_loss`), 4.2 (`trim`), 5.2 (`detail`), 5.4 (flags) · `report.HEADLINE` → 5.4.

**`05_Benchmarks.md`:** the numbers → the acceptance of 7.1 · acceptance 1–6 → 7.1 · the rescoring → 7.2.

**`P1`–`P7`:** each design step → the round's step of the same subject; the round's files replace them. **`probe/bench.py`:** → 7.1 (`--engine`); kept until the close.

## Always / Never

- **Always:** a loss is pool-independent; every number shown has its polarity and its "Made by"; a vetoed point is shown, never dropped; n and the trimming stand beside every marginal; a format 1 or 2 table still reads; an older Run's record still plots and reports; the identity golden test is green after every step.
- **Never:**
  - change `identity_parts`, `seed_basis`, or what a tool folder hashes;
  - rebuild an app, a module or a plugin; Paint included, though it would be safe;
  - touch `tests/reference/`;
  - write into a work dir before 7.2, or without its snapshot;
  - write Himinbjorg's live state;
  - edit a page under `docs/stable/`;
  - name the real study or a real work dir, in a file, a test or a commit: B1 to B4 only;
  - cite an issue id, `.plans/` or a design section in code or tests;
  - restate a rule of the engine in a presenter's own prose: render the record;
  - push;
  - start anything in Postponed.

## Progress

| Phase | Status |
|---|---|
| Plan | written and hardened 2026-11-10 (Tables, R19–R24); waits for the order to start |
| 0 | done 2026-11-10: fast suite 2182 passed, 11 skipped; no known reds |
| 1 | done 2026-11-10 (1.1–1.7, `f0a3f5d`…): every name of T1–T4 in place, the old ones refused in a user's file and read in a record, `heimdall migrate` rewrites them; no number changed. Fast suite green but for the two stable-docs reds of Implementation_Issues |
| 2 | done 2026-11-10 (2.1 `cf9f6c0`, 2.2 `31f1575`): the gate metrics in every new table; `ranking.rank` the one entry, a vetoed point after every passing one, the Gates and Order stages of the record. Fast suite 2375 passed, 11 skipped, the two stable-docs reds |
| 3 | done 2026-11-10 (3.1 `bde11f5`, 3.2 `66efbc4`, 3.3): costs hinged and compressed, the nine defaults, a figure's weight in the loss, one ranking a set recorded in its sidecar. Fast suite 2388 passed, 11 skipped, the two stable-docs reds; plot_stage 53 passed |
| 4 | in progress |
| 5 | not started |
| 6 | not started |
| 7 ⏸ | not started |
