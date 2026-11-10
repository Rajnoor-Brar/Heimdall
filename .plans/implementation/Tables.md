# The round's tables

The names, shapes and file lists the steps cite, verified at `db72aa7`. A step says "T3" and means the table below. The design files own the meaning of an id, a formula or a column; this file owns what the code is called. Where a line number has moved since `db72aa7`, find the name with `grep -n`: the name is the claim, the number a hint.

## T1. Metric ids and their functions (`framework/stats/metrics.py`)

The id is the `REGISTRY` key and the csv column. The function is renamed with it. `—` in "old" is a new metric (step 2.1).

| Old id | New id | Old function (line) | New function | Polarity | Category key | Thresholds (kept) |
|---|---|---|---|---|---|---|
| `chi2_ndf` | `chi2_ndf` | `chi2_ndf` (:157) | same | lower | compatibility | (1, 3) |
| `chi2_z` | `chi2_sigma` | `chi2_z` (:263) | `chi2_sigma` | lower | compatibility | (2.5, 6) |
| `poisson` | `poisson_dev` | `poisson` (:296) | `poisson_dev` | lower | compatibility | (3.5, 9) |
| `tail` | `tail_excess_sigma` | `tail` (:303) | `tail_excess_sigma` | lower | compatibility | (2.5, 6) |
| `norm` | `log_yield_ratio` | `norm` (:165) | `log_yield_ratio` | lower | normalisation | (0.02, 0.15) |
| `area_ratio` | `yield_ratio` | `area_ratio` (:234) | `yield_ratio` | one | normalisation | (0.009, 0.065) |
| `ratio_mean` | `mean_bin_ratio` | `ratio_mean` (:240) | `mean_bin_ratio` | one | normalisation | (0.009, 0.065) |
| `wmape_yield` | removed; alias of `yield_weighted_abs_dev` | `wmape_yield` (:324) | deleted | | | |
| `shape` | `log_dev_shrunk` | `shape` (:176) | `log_dev_shrunk` | lower | accuracy | (0.02, 0.15) |
| `L4` | `log_dev_l4` | `L4` (:338) | `log_dev_l4` | lower | accuracy | (0.07, 0.40) |
| `ratio_dev` | `mean_abs_ratio_dev` | `ratio_dev` (:247) | `mean_abs_ratio_dev` | lower | accuracy | (0.04, 0.25) |
| `rel_abs_area` | `yield_weighted_abs_dev` | `rel_abs_area` (:228) | `yield_weighted_abs_dev` | lower | accuracy | (0.03, 0.20) |
| `wmape_axis` | removed; alias of `mean_abs_ratio_dev` | `wmape_axis` (:329) | deleted | | | |
| `consensus` | `consensus_dev` | `consensus` (:482) | `consensus_dev`, its `base` default `"log_dev_shrunk"` | lower | accuracy | (0.03, 0.20) |
| `js` | `js_divergence` | `js` (:504) | `js_divergence` | lower | similarity | (0.0005, 0.02) |
| `ad` | `ad_distance` | `ad` (:518) | `ad_distance` | lower | similarity | (0.0005, 0.02) |
| `tilt` | `tilt` | `tilt` (:188) | same | lower | trend | (0.03, 0.25) |
| `rho1` | `pull_autocorr` | `rho1` (:345) | `pull_autocorr` | lower | trend | (0.35, 0.8) |
| `worst` | `peak_pull2` | `worst` (:205) | `peak_pull2` | lower | defects | (7, 25) |
| `cvar` | `peak_deviance` | `cvar` (:358) | `peak_deviance` | lower | defects | (14, 45) |
| `roughness` | `log_ratio_roughness` | `roughness` (:377) | `log_ratio_roughness` | lower | defects | (0.06, 0.40) |
| — | `peak_bin_ratio` | — | `peak_bin_ratio` | lower | integrity | (1.0, 3.0), gate 3.0 |
| — | `yield_sign` | — | `yield_sign` | lower | integrity | none, gate 1.0 |
| `n_eff` | `n_eff` | `n_eff` (:429) | same | higher, scale log | quality | (1000, 100) |
| `holes` | `hole_fraction` | `holes` (:437) | `hole_fraction` | lower | quality | (0, 0.10) |
| `r_int` | `log_roughness` | `r_int` (:401) | `log_roughness` | lower | quality | (0.05, 0.40) |
| `chi2_smooth` | `smoothness_chi2` | `chi2_smooth` (:413) | `smoothness_chi2` | lower | quality | (2.5, 8) |
| `r2_ln` | `tail_nonlinearity` | `r2_ln` (:477) | `tail_nonlinearity` | lower | quality | (0.05, 0.30) |
| `lambda` | `tail_slope` | `tail_rate` (:472) | `tail_slope` | descriptor | quality | none |
| — | `negative_share` | — | `negative_share` | lower | quality | (0, 0.25) |

- The category of a row is today's `purpose` of that entry, with the key `shape` written `accuracy`. If a row above disagrees with the entry's `purpose` in the code, the code's stands (this column was copied by hand) and the difference goes in Implementation_Notes. If a polarity, title or description disagrees with [02](../plans/grand-ranking/02_Metrics.md), 02 stands.
- Helpers that are not metrics keep their names: `deviance` (:275), `tail_fit` (:451), `log_ratio` (:117), `_usable`.
- `ALIASES` is every row whose old id differs from its new one: 22 keys, the two removed ones included.
- Three places name ids as strings: `null_p` (`score.py:134`: `chi2_ndf`, `chi2_z` → `chi2_sigma`, `tail` → `tail_excess_sigma`), the Fisher loop in `_aggregate` (`score.py:342`: `("chi2_ndf", "tail")` → `("chi2_ndf", "tail_excess_sigma")`), `consensus`'s `base="shape"`.
- **Flags after 3.2:** `default` (scored) on the nine: `chi2_sigma`, `poisson_dev`, `log_yield_ratio`, `log_dev_shrunk`, `log_dev_l4`, `tilt`, `pull_autocorr`, `peak_pull2`, `log_ratio_roughness`. `gate` on `peak_bin_ratio`, `yield_sign`. `shown` on `n_eff`. Until 3.2 the defaults are today's five under their new ids: `chi2_ndf`, `log_yield_ratio`, `log_dev_shrunk`, `tilt`, `peak_pull2`.

## T2. Words in the engine

| Old | New | Step |
|---|---|---|
| `Metric.purpose` | `Metric.category` | 1.4 |
| `Metric.better`, values `lower`, `higher`, `one`, `none` | `Metric.polarity`, values `lower`, `higher`, `one`, `descriptor` | 1.1 |
| `metrics.PURPOSES`, `ASKS` | `CATEGORIES`, `QUESTIONS` | 1.4 |
| category key `shape` | `accuracy` | 1.4 |
| `stats/score.py`, `runner/scorecmd.py` | `stats/ranking.py`, `runner/rankcmd.py` (and `"scorecmd": 4` in `runner/__init__.py`'s `RANKS` → `"rankcmd": 4`) | 1.5 |
| `score.NORMALISE` | `ranking.COSTS` | 1.5 |
| `Settings.normalise`, `.mean`, `.veto` | `.cost`, `.over_pages`, `.veto_loss` | 1.5 |
| `PointScore`, its `.score`, `.veto`, `.purposes` | `PointLoss`, `.loss`, `.vetoed`, `.categories` (`.purposes` → `.categories` at 1.4) | 1.5 |
| `Obs.purposes` | `Obs.categories` | 1.4 |
| `Marginal.axis`; the word "axes" for a point's coordinates | `Marginal.quantity`; "values" | 1.5 |
| `score.score()`, `Scores`, `Scores.ranked(cell)` | `ranking.rank()`, `Ranking`, `Ranking.of(cell)` | 2.2 |
| `Metric.loss()`, `Metric.scored()` | `Metric.cost()`, `Metric.excess()`, `Metric.oriented()` | 3.1 |
| `statstable.score_of`, `point_axes`, `write_set(…, score=)` | `ranking_of`, `point_values`, `write_set(…, ranking=)` | 1.5 |
| `rankcmd.scored`, `standings_of` | `rankcmd.ranked`, `leaderboard_of` | 1.5 |
| `bars._standings_tables`, `_purpose_sections`, `_score_text` | `_leaderboard_tables`, `_category_sections`, deleted at 5.1 | 1.4, 1.5, 5.1 |
| `config.Errand.score`, `check_score`, `sweep.SetSpec.score` | `.ranking`, `check_ranking`, `.ranking` | 1.5 |
| `plot.Figure.statistic`, `Page.statistic`, `STATISTIC_LABELS`, `_statistic_of`, `statistic_pages`, `_statistic_figures` | `.metric`, `.metric`, `METRIC_LABELS`, `_metric_of`, `metric_pages`, `_metric_figures` | 1.6 |

## T3. What a user writes

| Where | Old | New | Step |
|---|---|---|---|
| errand file, table | `[score]`, `[score.<sub>]` | `[ranking]`, `[ranking.<sub>]` | 1.5 |
| `[ranking]` keys | `normalise`, `mean`, `veto` | `cost`, `over_pages`, `veto_loss` | 1.5 |
| `[ranking]` keys, new | | `gates` (2.2), `trim` (4.2), `detail` (5.2) | |
| a set entry of `[plot].sets` | `score = {…}` | `ranking = {…}` | 1.5 |
| `[plot]` | `legend_statistic` | `legend_metric` | 1.6 |
| a figure, `[plot.figures.<name>]` | `class = "statistic"`, `statistic = "<column>"` | `class = "metric"`, `metric = "<column>"` | 1.6 |
| a metric id, wherever one is written | T1's old | T1's new | 1.3 |
| a report section's `stats` | `standings`, `purpose:<name>`, `purpose:shape` | `leaderboard`, `category:<name>`, `category:accuracy` | 1.4, 1.5 |
| command | `heimdall score`, `heimdall explain score[.<name>]` | `heimdall rank`, `heimdall explain ranking[.<name>]` | 1.5 |

The keys of a ranking table that take metric ids: `metrics` (a list, or a table's keys), `thresholds` (a table's keys). Elsewhere: `[stats].metrics` (a list), `legend_metric` (a value), a figure's `metric` (a value), a report section's `stats` (the part before `:`).

A figure's `metric` and `legend_metric` name a column of the table, which is a metric id or one of the fixed columns that are not metrics (`area`, `abs_area`, `chi2`, `chi2_ndf`): those four keep their names. In code a figure's class is the field `Figure.kind`; the key a user writes is `class`.

## T4. The summary's section and item keys (`bars.py`, `report.chosen`)

| Old | New | Step |
|---|---|---|
| section `standings`, title "Standings" | `leaderboard`, "Leaderboard" | 1.5 |
| section `purpose-<p>` | `category-<c>` | 1.4 |
| section `marginals`; items `marginal-<axis>`; notes `confounded-<axis>` | unchanged keys, the suffix is the quantity's name | |
| sections `baseline`, `head-to-head` | unchanged | |
| metric sections `<m>`, `<m>-ranking`, `<m>-crossed` | the same with the new id; drawn only with `detail` or when a report names them | 1.2, 5.2 |
| notes key `score` | `method`, from the record | 5.1 |

## T5. The sidecar `statistics.json`

| Format 2 | Format 3 | Written from |
|---|---|---|
| `format: 2` | `format: 3` | 1.2 |
| `metrics.<id>.purpose`, `.better` | `.category`, `.polarity` (`none` → `descriptor`), plus `.phrase`, `.scale`, `.default`, `.shown`, `.gate` | 1.2 (`polarity`, `phrase`, `scale`), 1.4 (`category`), 2.1 (`shown`, `gate`) |
| `metrics` keyed by old ids; `columns` with old ids | new ids | 1.2 |
| `score` (with `normalise`, `mean`, `veto`, old ids in `metrics` and `thresholds`) | `ranking` (with `cost`, `over_pages`, `veto_loss`, new ids) | 1.5 |
| `axes` | `values` | 1.5 |
| — | `ranking_sources`, `page_weights`, `method` | 3.3 |
| `merged`, `run` | unchanged | |

`table.upgraded(side)` returns a format 3 dict from a format 1, 2 or 3 one, never writes, and is what `table.sidecar(path)` returns. A key format 3 has and the file lacks is absent, not invented: readers use `.get`.

## T6. `heimdall rank --json`

Per table: `run`, `serial`, `set`, `metrics`, `notes`, `warning` unchanged. `standings` → `leaderboard`; in each of its rows `place` → `rank`, `score` → `loss`, `veto` → `vetoed`, `purposes` → `categories`; `cell`, `point`, `worst_page`, `worst`, `dominated`, `pages`, `shares` unchanged (all at 1.5). From 2.2 a row also has `failed_pages` and `gate_reason`, and the table has `flat` and `method`. `marginals[]`: `axis` → `quantity` (1.5); from 4.2 `values[]` holds a `MarginalRow`'s fields (T7) in place of `score`, `points`, `purposes`, and the marginal has `headline` and `strata`. NaN and ±inf are written as today's code writes them: no change of convention.

## T7. Shapes (final, after phase 5)

Every dataclass here is built by keyword. `Settings` and `plot.Figure` are built positionally today (`score.py:90–93`, `plot.py:126–131`): `Settings` is built by keyword from 1.5, `Figure` from 3.3 (R22), and no later step relies on field order. Every field of `Settings` has a default today and keeps one (a `field(default_factory=dict)` for the dicts); the listing below leaves them out for room.

```python
# framework/stats/ranking.py
@dataclass(frozen=True, kw_only=True)
class Settings:
    metrics: dict              # id → weight
    cost: str = "thresholds"   # one of COSTS
    thresholds: dict           # id → (good, bad), over the registry's
    weights: dict              # object glob → page weight
    weights_by: str = "equal"
    over_pages: str = "rms"
    veto_loss: float | None = None
    gates: object = True       # True, False, or a tuple of gate metric ids        (2.2)
    aggregate: str = "rms"
    dominated: bool = False
    trim: float = 0.2          #                                                   (4.2)
    by: tuple = ()
    baseline: object = None
    head_to_head: str | None = None
    detail: bool = False       #                                                   (5.2)
    sources: dict              # key → "default" | "[ranking]" | "set <name>" | "--<flag>"   (2.2; R8)

def settings_of(table: dict | None = None, flags: dict | None = None, sources: dict | None = None) -> Settings
# `table` is the merged ranking table (a sidecar's `ranking`, or `overlaid(errand's, set's)`); `flags` are a command's
# overrides, laid over it; `sources` is the sidecar's `ranking_sources`. A key in `flags` has the source "--<flag>" (the
# flag's own spelling, `head_to_head` → `--head-to-head`); else `sources[key]` when given; else "[ranking]" when the key is in
# `table`; else "default". Today's second parameter `over` goes: callers lay a set's table with `overlaid` first.

@dataclass(frozen=True)
class Choice:
    name: str                  # what was chosen: "cost", "weight of tilt", "page /A/b"
    value: object              # JSON-safe: str, number, bool, list or dict of those
    source: str                # "registry", "default", "[ranking]", "set <name>", "figure <name>", "--<flag>", "table"
    note: str = ""             # the sentence a reader needs: pool-dependent, not evaluated and why, the formula in words

@dataclass(frozen=True)
class Method:
    gates: tuple = ()          # 2.2
    metrics: tuple = ()        # 3.1
    cost: tuple = ()           # 3.1
    category: tuple = ()       # 3.1
    page_loss: tuple = ()      # 3.1
    pages: tuple = ()          # 3.3
    order: tuple = ()          # 2.2
    marginals: tuple = ()      # 4.2
    optin: tuple = ()          # 3.1: aggregate, dominated, weights_by, baseline, head_to_head, detail
    STAGES = ("gates", "metrics", "cost", "category", "page_loss", "pages", "order", "marginals", "optin")   # a ClassVar
    TITLES = {…}               # stage → 03 §3a's stage name, "optin" → "Opt-in aggregators and views"
    def as_dict(self) -> dict  # {stage: [{"name", "value", "source", "note"}, …]} for every stage, empty ones too
    def lines(self, *stages) -> list[str]   # one sentence a Choice: "<name>: <value> (<source>). <note>"; all stages when none given

@dataclass
class PointLoss:
    cell: str
    point: str
    loss: float = math.nan     # NaN: no scored page
    rank: int | None = None    # None: vetoed, or no loss                           (2.2)
    vetoed: bool = False
    failed_pages: int = 0      #                                                    (2.2)
    gate_reason: str = ""      #                                                    (2.2)
    worst_page: str = ""
    worst_loss: float = math.nan
    categories: dict           # category → cost
    shares: dict
    pages: dict                # page → loss
    values: dict               # metric id → median over the point's pages of its value, for default and shown metrics   (3.2)
    dominated: bool = False
    n_pages: int = 0

@dataclass
class Ranking:
    settings: Settings
    points: list               # PointLoss, in rank order (R21)
    cells: list                # the cells, in the rows' order
    flat: bool                 # R10
    method: Method
    weights: dict              # metric → the weight used (CRITIC's when weights_by = "critic"); was Scores.weights
    notes: list                # was Scores.notes
    marginals: list            # Marginal, filled when `values` is given                (4.2; before it, today's)
    baseline: object = None    # Baseline, when settings.baseline is set
    def of(self, cell: str) -> list   # the cell's points in order; was Scores.ranked

def rank(rows: list[dict], settings: Settings | None = None, page_weights: dict | None = None, values: dict | None = None) -> Ranking

@dataclass(frozen=True)
class MarginalRow:             # 4.2; the columns are 03 §2.4's
    value: str
    n: int                     # matched strata this value has a loss in
    g: int                     # trimmed from each end
    vetoed: int
    unmatched: int
    effect: float              # E_v, in ln; NaN when n = 0
    effect_se: float
    level: float               # M_v
    vs_best: float             # TM of the paired differences against the best row; 0 for the best
    vs_best_se: float
    same_as_best: bool
    mark: str                  # "", "one stratum", "n = 2: not robust", or the reason there is no number

@dataclass(frozen=True)
class Marginal:
    quantity: str
    rows: tuple                # MarginalRow, ordered by effect, rows without one last
    strata: tuple              # the other varied quantities the strata are made of
    headline: str              # 04 §2's line
    confounded: str = ""       # today's sentence, kept for a quantity with no matched stratum

def marginals(points: list, values: dict, settings: Settings) -> tuple[list, tuple]   # (the Marginals, the record's stage)
```

- `rank` calls `marginals` itself when `values` is given and stores both results. The public `marginals` exists so a test can pass `PointLoss`es with given losses.
- `baseline_filter`, `baseline`, `head_to_head`, `_dominated`, `_aggregate`, `critic_weights`, `observations`, `page_weight`, `chi2_p`, `null_p`, `varied`, `_confounded`, `Obs`, `BaselineRow`, `Baseline` stay in `ranking.py` under their names. `rank` calls `baseline` when `settings.baseline` is set. `head_to_head(rows, page, settings)` stays a function `bars._matches` calls.

## T8. Who calls the engine (each moves in the step that changes the call)

| Caller | Today | After 2.2 (and 3.3 for weights) |
|---|---|---|
| `statstable.write_set` (:77) | `write_statistics(…, score, axes, merged)`, then `module.draw(…, st=settings_of(score), axes=axes)`: the summary scores again inside `bars` | builds rows once, `rank(rows, settings, page_weights, values)` once, writes the sidecar with the record, passes the `Ranking` to `module.draw(…, ranking=…)`. `page_weights` is `{(p.rel or p.name): p.weight for p in pages if p.weight is not None}`: a row's `page` is `page.rel or page.name` (`table.py:65`), and the keys must be the same |
| `bars.summary_model(rows, heading, st, axes)` (:778) | `S.score(_rows_of(rows), st)` | `summary_model(rows, heading="", ranking=None)`: uses the given `Ranking`, and calls `rank(_rows_of(rows))` only when none is given (a test's shortcut) |
| `bars.summary_of` (:800), `bars.draw` (:817) | pass `st`, `axes` | pass `ranking` |
| `rankcmd.ranked` (was `scorecmd.scored` :84), `runs_of` (:134) | `score.score(rows, st)` | `rank(rows, settings, side.get("page_weights"), values)` |
| `report._scored` (:1466) and its use (:1485) | `settings_of(side.get("score"))`, then `bars.summary_model(rows, heading, st, axes)` | `report._ranked(csv_path)` returns the `Ranking` from the sidecar's `ranking`, `ranking_sources`, `page_weights`, `values`; `summary_model(rows, heading, ranking)` |
| `statstable.metric_names` (:45) | `settings_of(score_table).metrics` | the same through `settings_of(table)`, plus every gate metric when `gates` is not false |

## T9. Test files by subject (verified by `grep -l` at `db72aa7`)

- **Old metric ids:** `tests/runner/`: `test_stats_metrics.py`, `test_stats_registry.py`, `test_stats_score.py`, `test_statstable.py`, `test_summary_layout.py`, `test_score_cli.py`, `test_score_settings.py`, `test_report.py`, `test_report_build.py`. `tests/integration/`: `test_plot_stage.py`, `test_paint_bins.py` (:81–95, names only). Not `test_config.py` or `test_layers_of_a_study.py`: their `"shape"` is a quantity's shape.
- **`purpose`:** `test_stats_registry.py`, `test_stats_score.py`, `test_statstable.py`, `test_summary_layout.py`, `test_report.py` (:182–183 hold `HEADLINE` to `PURPOSES`), `test_report_build.py`, `tests/integration/test_plot_stage.py`.
- **`score`:** `test_stats_score.py`, `test_score_cli.py`, `test_score_settings.py`, `test_stats_metrics.py`, `test_statstable.py`, `test_summary_layout.py`, `test_snapshot.py`, `test_complete.py`, `test_report_build.py`, `tests/integration/test_plot_stage.py`.
- **`standings`:** `test_summary_layout.py`, `test_report.py` (:159–163), `test_report_build.py`, `test_score_cli.py`, `tests/integration/test_plot_stage.py`.
- **`statistic` as a figure kind or legend key:** `tests/integration/test_plot_stage.py` only.
- **Framework files with the word `score`:** `plot/figures/bars.py`; `runner/`: `__init__.py`, `cli.py`, `complete.py`, `config.py`, `docs.py`, `house.py`, `knowledge.py`, `plotdoc.py`, `plot.py`, `report.py`, `schema.py`, `scorecmd.py`, `statstable.py`, `sweep.py`, `v3.py`; `schema/run.toml`, `schema/report.toml`; `stats/`: `__init__.py`, `metrics.py`, `score.py`, `table.py`. The generated `schema/run.schema.json` and `run.v3.schema.json` are regenerated, never edited.

`tests/reference/` is never in a list: it is not touched.

## T10. Lines by file (the places a step edits)

- **`framework/runner/cli.py`:** the retired `stats` parser :132–136; the `score` parser :138–146 (`target`, `--set` dest `set_name`, `--across`, `--by AXES`, `--baseline FILTER`, `--json`); dispatch :3590–3593 (`cmd_stats_retired`, `cmd_score`); `main` :3505, its `HeimdallError` handlers :3511 and :3643; other mentions :1917, :1976, :2021–2025.
- **`framework/runner/complete.py`:** `RETIRED = ("stats", "deck")` :29; `KINDS[("score", "target")]` :45; `FREE`'s `("score", "set_name" | "by" | "baseline")` :62.
- **`framework/runner/config.py`:** `Errand.score` :140; `_form` :504; `_toml` :518 (the one TOML reader; callers :501, :945, :977, :996, :1555); `load` :938 (its `text=` branch parses at :948); `parse` :1053; where `score` is read and checked :1303–1313; `figure_tables` :1361; `check_score` :1410; `SUMMARY` :1454; `PARTS`, `REPLACED` :1455–1457; `check_stats_key` :1460–1486; `check_report`'s loop over a section's `stats` (about :1527); `check_plot` :1574; the statistic figure's check :1622–1626 (`(kind == "statistic") != ("statistic" in table)`, its hint `class = "statistic", statistic = "chi2_ndf"`). Lenient loads (`strict=False`): `config.py:823`, `complete.py:339`, `migrate.py:1034` and :1036.
- **`framework/runner/report.py`:** `RECIPE` :50; `HEADLINE` :56; `_read` :238 and `load_recipe` :273; the default section :313; `chosen` :1407–1430; `METHOD_NOTES` :1452 and :1457; `_scored` :1466–1470; :1485–1486; :1525; the method section :1725–1767; the figure class filter :2327.
- **`framework/runner/plot.py`:** `Page` :74 (`statistic` :89, `rel` :92); `Figure` :100–118 (`statistic` :117); `figures()` :121–132; `written()` :956–977 (called at :1032 and :1076; the figure's table reaches it as `override`, :1005 and :1044); `STATISTIC_LABELS` :1088; `_statistic_of` :1092; `_with_statistics` :1101; `statistic_pages` :1119 (`"area_err"` :1143); :1728, :1742; `_tables` :1889–1910; `_statistic_figures` :1987–1996.
- **`framework/runner/` others:** `plotdoc.py` (`score` :73, `KEYS` :170, `ORDER` :171, :533, :547–553, `write_chosen` :561–575, `load` :626, :658, :815–816, :962); `house.py` (`_score_names` :199, `_score_lines` :204–221, dispatch :249–250); `schema.py` (`TABLES` :34–35, `FIGURE_OWN` :39–40); `v3.py` (:36, :386–387); `docs.py` (:121, :128, :269, `write_generated` :282); `knowledge.py` :199; `sweep.py` (`SET_KEYS` :171, `SetSpec.score` :279, :336–337); `statstable.py` (`score_of` :36, `metric_names` :45, `point_axes` :53, `write_set` :77); `migrate.py` (`errand_text` :1294, `errand_changes` :1422); `paths.py` (`configs_root` :287, `configs_at` :293); `record.py` (`SNAPSHOT` :693, `write_snapshot` :723).
- **`framework/schema/run.toml`:** the table order :31; "heimdall explain score" :895, :1085–1086; `[plot.statistics]` :951; `[plot.legend_statistic]` :965; the `[score]` block :1094–1161 (`metrics` :1097, `normalise` :1105, `thresholds` :1115, `weights` :1119, `weights_by` :1123, `mean` :1129, `by` :1134, `baseline` :1139, `veto` :1143, `aggregate` :1148, `dominated` :1154, `head_to_head` :1159); figure classes :1169; `[figure.statistic]` :1235; `[figure.weight]` :1245. **`framework/schema/report.toml`:** :76, `[section.stats]` :146–149.
- **`framework/plot/figures/bars.py`:** imports :25–26; `COMPARED` :36 to `CROSSED_NOTE` :49; `_mean` :288; `_ranking` :376; `_crossed` :407; `_table_of` :462; `_on` :520; `_score_text` :528; `_standings_tables` :543; `_purpose_sections` :607; `_matches` :639; `_marginals` :689; `_baseline` :720; `_facts` :759; `summary_model` :778; `summary_of` :800; `draw` :817. **`webpage.py`:** `render` :241.
