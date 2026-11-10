# Phase 1: names and polarity

Status: in progress. Blocked by: phase 0. Sources: [01](../plans/grand-ranking/01_Glossary.md) (the rename table), [02](../plans/grand-ranking/02_Metrics.md) (ids, polarity, the alias table). Names in code: [Tables](Tables.md) T1–T6, T9, T10.

No number changes in this phase. A loss computed after 1.7 equals the score computed before 1.1 on the same table, and step 1.5's test holds that.

The order is expand, move, contract: 1.1 adds the new ids with the old ones still resolving, 1.2 to 1.6 move each layer, 1.7 rewrites users' files. After every step the fast suite is as the baseline, and a record written before the round still loads.

**Today:** the registry is `framework/stats/metrics.py:532` (27 entries, `Metric` at :83 with `purpose`, `better`); `PURPOSES` :29, `ASKS` :40, `TITLES` :53, `FORMULAS` :70. The table is `framework/stats/table.py` (`FORMAT = 2`, `sidecar_of` :95, `read` :144). The settings are `[score]` (`framework/schema/run.toml:1094`), checked by `config.check_score` (`config.py:1410`). Every TOML an errand loads passes `config._toml` (`config.py:518`) or the `text=` branch of `config.load` (:948).

### Step 1.1: the registry's ids, polarity and scale (Size: M)
- Acceptance:
  - Every id and function is T1's "new" column. Every display name (`TITLES`), formula (`FORMULAS`) and one-line `note` is 02's catalogue row for that id. `wmape_yield` and `wmape_axis` are deleted, functions and entries.
  - `Metric.better` → `polarity`, the value `none` → `descriptor`. `Metric.scale: str = "linear"` is added, `"log"` for `n_eff` only. `metrics.GLYPH`, `metrics.ASCII` and `metrics.PHRASE` are dicts from each of the four polarities to 02's glyph, ASCII form and phrase.
  - `metrics.ALIASES: dict[str, str]` is T1's old → new for every row whose id changed (22 keys). `metrics.resolve(name: str) -> str` returns `ALIASES.get(name, name)`. `metrics.evaluate`, `metrics.describe` and `score.thresholds_of` call `resolve` on the name they are given, so a caller that still passes an old id works until its own step.
  - The three string uses of an id move (T1's last bullets): `null_p`, the Fisher loop, `consensus_dev`'s `base`.
  - `purpose` stays until 1.4. The defaults stay today's five under their new ids until 3.2.
- Files: `framework/stats/metrics.py`, `framework/stats/score.py`, `tests/runner/test_stats_registry.py`, `tests/runner/test_stats_metrics.py`, `tests/runner/test_stats_score.py`. A direct call of a renamed function outside these is found by `grep -rnE "\b(M|metrics)\.(norm|shape|worst|rel_abs_area|area_ratio|ratio_mean|ratio_dev|chi2_z|poisson|tail|L4|rho1|cvar|roughness|r_int|chi2_smooth|holes|tail_rate|r2_ln|consensus|js|ad)\b" framework tests` and moved in this step.
- Test: `test_stats_registry` gains: every entry has a polarity of the four, a scale of the two, a note; every key of `ALIASES` is absent from `REGISTRY` and its value present; no two entries share a function; `evaluate("shape", curve)` equals `evaluate("log_dev_shrunk", curve)`. It fails first on the old code (no `ALIASES`).
- Check: `taskset -c 0-5 nice -n 10 python -m pytest -q tests/runner/test_stats_registry.py tests/runner/test_stats_metrics.py tests/runner/test_stats_score.py`, then the fast suite.
- Seam: the registry.
- Blocked by: 0.1.

### Step 1.2: tables and sidecars, format 3 (Size: S)
- Acceptance:
  - The four fixed columns are renamed in `STATISTIC_COLUMNS` (`table.py:20`) and `statistics_of` (:47): `rel_abs_area` → `yield_weighted_abs_dev`, `area_ratio` → `yield_ratio`, `ratio_mean` → `mean_bin_ratio`, `ratio_dev` → `mean_abs_ratio_dev`. The other fixed columns keep their names.
  - `table.read` (:144) maps each header through `metrics.resolve`, so the rows of a format 1 or 2 csv carry new ids.
  - `FORMAT = 3`. `sidecar_of` writes T5's format 3 keys that exist at this step: per metric `polarity`, `phrase`, `scale` (and `purpose` until 1.4). `table.upgraded(side: dict) -> dict` is T5's reader, and `table.sidecar(path)` returns `upgraded` of what it read. At this step `upgraded` maps the metric ids (in `metrics`, `columns`, and `score.metrics` and `score.thresholds`) and `better` → `polarity`. Steps 1.4 and 1.5 add their keys to it.
  - Every reader of a row by an old column name moves to the new one: `bars.py`, `report.py`, `scorecmd.py`, and `plot.py` (`STATISTIC_LABELS` :1088's keys, `"area_err"` stays). `plot._statistic_of` (:1092) and `statistic_pages` (:1119) pass the setting's value through `metrics.resolve`, so `legend_statistic = "ratio_dev"` still draws until 1.3 refuses it.
- Files: `framework/stats/table.py`, `framework/plot/figures/bars.py`, `framework/runner/report.py`, `framework/runner/plot.py`, `framework/runner/scorecmd.py`, `framework/runner/statstable.py`, and T9's "old metric ids" tests: each has its ids renamed in this step or in 1.1, whichever first makes it fail.
- Test: a format 2 csv and sidecar, built in the test with the old names, read back: every column and every sidecar key has its new name, and no value changed. Fails first (`KeyError` on a new id).
- Check: `taskset -c 0-5 nice -n 10 python -m pytest -q tests/runner/test_statstable.py tests/runner/test_summary_layout.py tests/runner/test_report.py`, then the fast suite, then `tests/integration/test_paint_bins.py` alone and `tests/integration/test_plot_stage.py` alone.
- Seam: `table.read` and `table.sidecar`.
- Blocked by: 1.1.

### Step 1.3: old names in a file, and metric ids in settings (Size: M)
This step builds the one function every later rename of a written name goes through (R9), and uses it first for metric ids.
- Acceptance:
  - **`paths.SNAPSHOT = "snapshot.toml"`** (the constant moves from `record.py:693`; `record.SNAPSHOT = paths.SNAPSHOT` stays as the name `record`'s callers use). **`paths.in_record() -> bool`** is `(configs_root() / SNAPSHOT).is_file()`: true exactly when a command has pointed `HEIMDALL_CONFIGS` at a record's `config/` with `paths.configs_at`.
  - **`config.renamed(raw: dict, where: str, recorded: bool) -> dict`.** It walks the places below. For an old name found: when `recorded`, it returns a copy with the new name in its place and appends `` `<old>` → `<new>` `` to the module list `config.OLD_NAMES` (once each); when not, it raises `HeimdallError(f"renamed: {old} is {new}", where=f"{where}: {place}", hint="heimdall migrate rewrites it")`. A raw dict with no old name is returned as it is.
  - **The places at this step** (the keys still carry their old names; T3's last paragraph): `[stats].metrics`; `[score].metrics` (a list's items or a table's keys) and `[score].thresholds` (keys); the same two inside each `[plot].sets` entry's `score`; `legend_statistic` and a figure's `statistic` wherever a page key may be written: `[plot]`, each `[plot.figures.<name>]`, each `[plot].sets` entry, a report section's `plot`; each entry of a report section's `stats`, the part before `:` (`[report]`'s `section` list). An id is old when it is a key of `metrics.ALIASES`.
  - **Who calls it.** `config._toml` (:518) and the `text=` branch of `config.load` (:948), right after `tomllib.loads`, with `recorded = paths.in_record() or LENIENT.get()`. `config.LENIENT` is a `contextvars.ContextVar` (default `False`) that `config.load` sets for its whole body when `strict=False` and resets in a `finally`: `migrate`, completion and `config.py:823` read old forms on purpose. `plotdoc.load` (`plotdoc.py:633`) calls it with `recorded=True`: a Run's `plot.toml` is a record. `report.load_recipe` (`report.py:273`) calls it on `_read(path)`'s result with `recorded = path.name == RECIPE and (path.parent / plotdoc.FILE).is_file()`: the recipe a run wrote beside its `plot.toml` is a record, a user's recipe is not.
  - **Said once.** `cli.main` (`cli.py:3505`), before it returns, prints one line on stderr when `config.OLD_NAMES` is not empty: `heimdall: read old names from the record: <the list, comma-joined>`.
  - The schema's choices and docs name the new ids: `[plot.legend_statistic]` (`run.toml:965`) and `[figure.statistic]` (:1235) list `yield_weighted_abs_dev`, `yield_ratio`, `mean_bin_ratio`, `mean_abs_ratio_dev` for the four; `[section.stats]` (`report.toml:146`) says `chi2_sigma` where it gave an id as an example.
- Files: `framework/runner/paths.py`, `framework/runner/record.py`, `framework/runner/config.py`, `framework/runner/plotdoc.py`, `framework/runner/report.py`, `framework/runner/cli.py`, `framework/schema/run.toml`, `framework/schema/report.toml`, `tests/runner/test_score_settings.py`, `tests/runner/test_report.py`, `tests/runner/test_snapshot.py`.
- Test:
  - **A user's file:** a refusal for each place above, each naming the new id. Fails first ("no metric" without the new name).
  - **A record:** an errand run far enough to write its snapshot (as `test_snapshot.py`'s tests do), its snapshot's errand file then rewritten in the test with `[score] metrics = ["shape"]`: loaded under `paths.configs_at(<the record's config>)`, the errand's `score["metrics"]` names `log_dev_shrunk`, and `config.OLD_NAMES` holds the pair. The same file under the scratch `configs/` is refused.
  - **Lenient:** `config.load(name, strict=False)` on that file under `configs/` maps and does not raise.
  - **Once:** `cli.main` on a command that loads the record prints the line once (`capsys`).
- Check: `taskset -c 0-5 nice -n 10 python -m pytest -q tests/runner/test_score_settings.py tests/runner/test_report.py tests/runner/test_snapshot.py`, then the fast suite.
- Seam: `config.renamed`.
- Blocked by: 1.2.

### Step 1.4: purpose → category (Size: S)
- Acceptance:
  - `Metric.purpose` → `category`; `PURPOSES` → `CATEGORIES`, `ASKS` → `QUESTIONS`. The categories, in order, are today's seven with `integrity` added before `quality`: keys `compatibility`, `normalisation`, `accuracy`, `similarity`, `trend`, `defects`, `integrity`, `quality`, each with 02's title and question. The key `shape` becomes `accuracy`: it collided with the metric. `integrity` has no metric until 2.1, and an empty category draws no section, as today.
  - `Obs.purposes` and `PointScore.purposes` → `categories`; the sidecar's `purpose` → `category` (and in `table.upgraded`, with `shape` → `accuracy`); `bars._purpose_sections` → `_category_sections`, its section keys `purpose-<p>` → `category-<c>`; `scorecmd`'s `--json` key `purposes` → `categories`.
  - A report section's `purpose:<name>` → `category:<name>`: `config.check_stats_key` (:1460) reads the new, `report.HEADLINE` (:56) and `chosen` (:1407–1430) use it, and `config.renamed` gains the place: an entry `purpose:<name>` of a section's `stats` is old, its new name `category:<name>` (`category:accuracy` for `purpose:shape`).
  - `house`'s `explain` lists by category (`house.py:204–221`).
- Files: `framework/stats/metrics.py`, `framework/stats/score.py`, `framework/stats/table.py`, `framework/plot/figures/bars.py`, `framework/runner/report.py` (`HEADLINE` :56, :1407–1486, :1725–1767), `framework/runner/config.py`, `framework/runner/house.py`, `framework/runner/scorecmd.py`, `framework/schema/report.toml` (:149), `framework/schema/run.toml`'s docs where they say purpose, T9's "`purpose`" tests.
- Test: `grep -rnwE "purpose|purposes|PURPOSES|ASKS" framework/stats framework/plot framework/runner/report.py framework/runner/scorecmd.py framework/runner/house.py` finds nothing; `test_report` refuses `purpose:trend` in a user's recipe naming `category:trend`; `test_report.py:182–183` holds `HEADLINE` to `CATEGORIES`.
- Check: the grep above, then `taskset -c 0-5 nice -n 10 python -m pytest -q tests/runner -m 'not slow'`.
- Seam: the report's section keys and the summary model's section keys.
- Blocked by: 1.3.

### Step 1.5: `[ranking]`, `heimdall rank`, loss, quantity (Size: M)
Three commits, in this order, each with the fast suite as the baseline: (a) the modules and the engine's words, (b) the settings and the sidecar, (c) the CLI and the section key.
- Acceptance:
  - **(a) Modules** move by `git mv` (R1): `framework/stats/score.py` → `ranking.py`, `framework/runner/scorecmd.py` → `rankcmd.py`, `tests/runner/test_stats_score.py` → `test_stats_ranking.py`, `test_score_cli.py` → `test_rank_cli.py`, `test_score_settings.py` → `test_ranking_settings.py`. `"scorecmd": 4` in `framework/runner/__init__.py`'s `RANKS` becomes `"rankcmd": 4`. Every `from stats import score` and `import scorecmd` follows (`bars.py:26`, `statstable.py`, `report.py`, `cli.py`, `table.py`). `framework/stats/__init__.py`'s docstring lists every module of the package.
  - **(a) The engine's words** are T2's rows marked 1.5. `ranking.score()` and `Scores` keep their names until 2.2. `Settings` is built by keyword from this step (R22), still without the new fields.
  - **(b) Settings:** `[score]` → `[ranking]` in `run.toml` (:1094–1161, and the table order :31), its keys `normalise` → `cost` (:1105), `mean` → `over_pages` (:1129), `veto` → `veto_loss` (:1143); the docs' "heimdall explain score" (:895, :1085–1086) and `[figure.weight]`'s doc (:1245) follow. `Errand.score` → `ranking` (`config.py:140`, :1303–1313), `check_score` → `check_ranking` (:1410), every message `[score]…` → `[ranking]…`. A set's `score = {…}` → `ranking = {…}` (`sweep.SET_KEYS` :171, `SetSpec.score` :279, :336–337). `plotdoc` (`score` :73, `KEYS` :170, :533, :547–553, `write_chosen` :561–575), `schema.TABLES` (:34–35), `v3.TABLES` (:36) and `v3.translate` (:386–387), `docs.py` (:121, :128, :269), `knowledge.py` (:199), `house._score_names` and `_score_lines` (→ `_ranking_names`, `_ranking_lines`). `statstable.score_of` → `ranking_of`, `point_axes` → `point_values`, `write_set`'s `score=` → `ranking=`.
  - **(b) Old names:** `config.renamed` gains the places: the table `score` → `ranking` (and `[score.<sub>]` with it); inside it `normalise`, `mean`, `veto`; a `[plot].sets` entry's `score` → `ranking`, the three keys inside it too. Its 1.3 places now read the new table names as well as the old.
  - **(b) The sidecar:** written with `ranking` and `values`; `table.upgraded` maps `score` → `ranking` (its three keys inside) and `axes` → `values` (T5). `table.sidecar_of` and `write_statistics` take `ranking=` and `values=`.
  - **(c) The CLI:** the parser `rank` replaces `score` (`cli.py:138–146`) with `target`, `--set`, `--across`, `--by QUANTITIES`, `--baseline q=value`, `--json`; `cmd_score` → `cmd_rank`. `heimdall score` is refused naming `rank`, the way the retired `stats` is (`cli.py:132–136`, dispatch :3590–3593, `complete.RETIRED` :29). `complete.KINDS` and `FREE` (:45, :62) say `rank`. `heimdall explain ranking[.<name>]` (`house.py:249–250`); `explain score` raises `HeimdallError("renamed: explain score is explain ranking")`. `--json`'s keys are T6's 1.5 set. Error hints say "heimdall explain ranking".
  - **(c) Words:** every message and header says loss, category, quantity, value, leaderboard. The section key `standings` → `leaderboard` in `config.SUMMARY` (:1454), `report.HEADLINE` (:56), the default section (`report.py:313`) and `bars` (`_standings_tables` → `_leaderboard_tables`); `config.renamed` gains `standings` in a section's `stats`; `config.REPLACED` (:1456)'s values that said `standings` say `leaderboard`.
- Files: T9's "framework files with the word `score`", every one; `framework/runner/paths.py` is not among them; `tests/runner/test_imports.py` only if it names a module; T9's "`score`" and "`standings`" tests. The generated schemas are regenerated by the command `test_the_editor_schema_is_current` names, if it fails.
- Test:
  - **Same numbers:** in `test_stats_ranking.py`, a table of 3 points × 2 pages built in the test from literal metric values, its three losses written as literals. The literals are computed by hand from the linear hinge and the RMS in the test's comment, and checked against the code as it is before commit (a): the test is written first, against `score.score`, and passes; then the rename; it still passes to 1e-12.
  - **A user's file** with `[score]`, with `[ranking].mean`, with a set's `score = {}`, with `stats = ["standings"]`: each refused, naming the new.
  - **A record:** a snapshot's errand file with `[score] normalise = "median"` and `veto = 2` loads under `configs_at`, and its errand has `ranking == {"cost": "median", "veto_loss": 2}`. A format 2 sidecar with `score` and `axes` reads as `ranking` and `values`. Fails first.
  - **The CLI:** `heimdall score <target>` exits non-zero with the refusal naming `rank`.
  - `grep -rnw "score\|scores\|scored\|scoring" framework --include=*.py --include=*.toml` finds only: `metrics.py` and `ranking.py` where a sentence says a metric is "scored" (kept: 01 keeps "scored metric"), `config.renamed`'s table, the refusals. Each line left is listed in the log.
- Check: `taskset -c 0-5 nice -n 10 python -m pytest -q tests/runner -m 'not slow'`, then `tests/integration/test_plot_stage.py` alone.
- Seam: `config.renamed`, `rankcmd.run`, `table.upgraded`.
- Blocked by: 1.4.

### Step 1.6: `legend_metric`, figure class `metric`, zero line (Size: S)
- Acceptance:
  - `[plot].legend_statistic` → `legend_metric` (`run.toml:965`); a figure's `class = "statistic"` → `class = "metric"` (the choices at :1169) and its key `statistic` → `metric` (`[figure.statistic]` :1235 → `[figure.metric]`; `schema.FIGURE_OWN` :39–40; the check at `config.py:1622–1626`; `report.py:2327`). In `plot.py`: T2's last row, and `Figure.kind == "metric"` (:1990), the plan line (:1728).
  - **No path on disk changes** (R24): the Paint object `/statistic/<name>`, the cache folder `statistic/`, and `folders.pages / "statistic" / figure.name` (`plot.py:1991`) keep their names, as string literals.
  - `config.renamed` gains the places: the key `legend_statistic` → `legend_metric` wherever 1.3 looked for it; in a `[plot.figures.<name>]` table, `class = "statistic"` → `"metric"` and the key `statistic` → `metric`.
  - `bars.py`'s docstrings and keys say "zero line" where they said the bars' "baseline" (not `[ranking].baseline`, which keeps its name).
- Files: `framework/runner/plot.py` (:89, :117, :131, :977, :1088–1168, :1728–1742, :1987–1996), `framework/runner/config.py`, `framework/runner/schema.py`, `framework/runner/report.py`, `framework/schema/run.toml`, `framework/plot/figures/bars.py`, `tests/integration/test_plot_stage.py` with any fixture it needs, `tests/runner/test_ranking_settings.py`.
- Test: a user's file with `legend_statistic`, one with `class = "statistic"`, one with a figure's `statistic =`: each refused, naming the new; the same three in a record's snapshot load, the errand's figure having `class == "metric"`. Fails first.
- Check: the fast suite, then `tests/integration/test_plot_stage.py` alone.
- Seam: the errand loader.
- Blocked by: 1.5.

### Step 1.7: `heimdall migrate` rewrites the old names (Size: S)
- Acceptance:
  - `migrate.ranking_text(text: str) -> str`, by line as `errand_text` is (`migrate.py:1294`), so comments and layout stay. It rewrites exactly what `config.renamed` maps, from the same tables (`metrics.ALIASES` and `config.renamed`'s; no second list): `[score]` and `[score.…]` headers, commented-out ones too; the three renamed keys under such a header or inside a `score = {`/`ranking = {` inline table; a set's `score = {`; `legend_statistic`; `class = "statistic"` and a figure's `statistic =`; an old metric id as a quoted string or a bare key on a line whose key is `metrics`, `thresholds`, `legend_metric`, `metric`, `stats`, or under a `[ranking.metrics]` or `[ranking.thresholds]` header; in a `stats = [...]` list, `"standings"`, `"purpose:<name>"`, `"<old id>[:part]"`; the words `explain score` and `heimdall score` anywhere. Idempotent.
  - In `errand_changes` (`migrate.py:1422`) it joins the `configs/` branch only: a `.toml` under `configs/` gets `ranking_text(errand_text(text))`. A user's recipe is a `.toml` under `configs/`, so it is covered. **It is not added to the loops over `records/**/config/`, `results/**/plot.toml` or `results/**/report.toml`** (R23): those are read through `config.renamed`.
  - It is dry by default as `migrate` is. The round runs it on no real work dir.
- Files: `framework/runner/migrate.py`, `tests/runner/test_migrate.py`.
- Test: a built errand file and a recipe with every old name of T3: migrated once, they load with `strict=True`; migrated twice, the text is unchanged; an old id inside a comment's prose, and the word `shape` as a quantity's key, are left alone; a record's snapshot in the same scratch work dir is not in `errand_changes`' result for this rename. Fails first.
- Check: `taskset -c 0-5 nice -n 10 python -m pytest -q tests/runner/test_migrate.py`, then the fast suite.
- Seam: `migrate.ranking_text`.
- Blocked by: 1.6.

## Log

- **1.1 · done 2026-11-10.** The registry has T1's new ids and functions, 02's titles and notes; `wmape_yield` and `wmape_axis` are gone. `Metric.better` is `polarity` (`descriptor` for `none`), `Metric.scale` is added (`log` for `n_eff` only), and `GLYPH`, `ASCII`, `PHRASE`, `POLARITIES`, `SCALES` exist. `ALIASES` (24 keys) and `resolve` exist. `evaluate`, `describe`, `Settings.thresholds_of`, `settings_of` (metric and threshold keys) and `null_p` resolve an old id. `null_p`, the Fisher loop and `consensus_dev`'s `base` name the new ids. The four fixed columns were renamed here, not at 1.2 (Notes), with `plot.STATISTIC_LABELS`' keys; `legend_statistic` and a statistic figure's `statistic` go through `resolve`. `bars`, `house` and `table` read `.polarity`.
  - Fails first: `AttributeError: module 'stats.metrics' has no attribute 'ALIASES'` (the new registry test, against `HEAD`'s `framework/`).
  - Check: the three step files, 190 passed. Fast suite: 2180 passed, 11 skipped. The baseline had 2182; the 6 parametrized cases of the two deleted metrics went, and 4 tests were added.
  - A reader may rely on: the new ids as columns and settings; an old id still evaluating, describing and scoring; each metric's polarity, scale, glyph and phrase.
- **1.2 · done 2026-11-10.** `table.FORMAT` is 3. The sidecar's metric entries hold `polarity`, `phrase` and `scale`, with `purpose` until 1.4. `table.upgraded(side)` reads a format 1, 2 or 3 sidecar as format 3: metric ids in `metrics`, `columns`, `score.metrics` and `score.thresholds`, and `better` → `polarity`. It never writes. `table.sidecar(path)` returns it, and `format_of` still reports the format the file was written in. `table.read` maps each header through `metrics.resolve`. The four fixed columns moved at 1.1 (Notes).
  - Fails first: on the code before this step, the new test gives `AssertionError: ['rel_abs_are…'] == ['yield_weigh…']`.
  - Check: `test_statstable`, `test_summary_layout`, `test_report`: 72 passed. Fast suite: 2181 passed, 11 skipped. `tests/integration/test_paint_bins.py` alone: 2 passed. `tests/integration/test_plot_stage.py` alone: 53 passed.
  - A reader may rely on: an older Run's `statistics.csv` and sidecar reading with today's ids and polarity, the file untouched.
- **1.3 · done 2026-11-10.** `paths.SNAPSHOT` and `paths.in_record()` exist, and `record.SNAPSHOT` is `paths.SNAPSHOT`. `config.renamed(raw, where, recorded)` exists with `config.OLD_NAMES` and `config.LENIENT`. `load(strict=False)` sets `LENIENT` for its whole body; its old body is `config._load`. It walks these places: `[stats].metrics`; `[score].metrics` and `.thresholds`; each `[plot].sets` entry's `score`; `legend_statistic` and `statistic` in `[plot]`, each `[plot.figures.<name>]`, each set entry and a report section's `plot`; and each report section's `stats`, the part before `:`.
  - `config._toml` and `load`'s `text=` branch call it through `config._loaded`. `plotdoc.load` calls it with `recorded=True`. `report.load_recipe` treats a `report.toml` beside a `plot.toml` as a record.
  - `cli.main` clears `OLD_NAMES`, runs `_main` and says the line once on stderr; it says nothing for `__complete`.
  - The schema's choices name the new ids. `run.schema.json`, `run.v3.schema.json` and `docs/reference/settings/{plot,report}.md` are regenerated (`make schema`, `make docs`).
  - Fails first: `AttributeError: module 'runner.config' has no attribute 'OLD_NAMES'`.
  - Check: `test_score_settings`, `test_report`, `test_snapshot`: 92 passed. Fast suite: 2206 passed, 11 skipped.
  - A reader may rely on: an old metric id in a user's file being refused with "renamed: <old> is <new>" and the place; a record's snapshot, a Run's `plot.toml` and the `report.toml` beside it reading old ids; one stderr line a command saying which were read.
