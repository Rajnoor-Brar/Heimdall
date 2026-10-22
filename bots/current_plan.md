# Current plan

**Task I is done** (V161, 2026-10-22: High-Energy as a work dir, editor/). **Task H is done** (V156–V160, 2026-10-21/22; below). **Task F is done** (V151–V154, 2026-10-15; its plan below). Open: audit 4 (below). The decisions are in docs/07_Record.md (V1–V155); finished task logs
are in [archive.md](archive.md) (the latest: tasks A–E of 2026-10-14, V140–V150); ideas not built are
in [intent.md](intent.md).

## Task H: run output, Sherpa progress, one records/ tree, replot from the record, point sets, page statistics

Planned 2026-10-21 from the user's notes (`docs/Notes.md`, untracked), approved the same day; built in four
commits (`db38c72` V156, `2ea5de2` V157, `6cc01f1` V158, then V159–V160), the user asking during it to build every
phase and then move a real study's 38-point generator × PDF run onto the new system.

**Done, and how it differs from the plan below:**
- As planned, with: a tool with no count shows its last line under its row whatever its phase (Sherpa's
  integration line); the stage block's lines escaped for rich; `heimdall migrate --layout --list`; reproductions in
  `.cache/<P>/reproduce/`, an overlay's documents in `.cache/overlay/`; identities write a moved configs root as
  `{work}/configs/…` (`paths.identity_texts`), which the plan had not foreseen (Pythia's argv names its cards); a
  plot-only `heimdall plot RECORD`; `heimdall migrate --snapshot RECORD [--from] [--set] [--apply]`; `heimdall plot
  --points SEL`; the CSV's labels without the legend's number.
- **The real work dir** (2026-10-22): a tarball of its records/, results/ and logs/ first
  (`$HEP_FORGE/scratch/<work dir>-before-v157.tar`, 232 MB), then `heimdall migrate --layout --apply` (775 renames,
  every configuration: the layout is the work dir's); the run's snapshot from today's config, its PDFs since commented
  out restored in the snapshot's own common.toml (19, in the recorded order, values and labels checked against
  points.json); `heimdall status RECORD`: 38 complete; `heimdall plot RECORD`: 24 pages, 456 statistics rows against
  the data. Its configs/ untouched.
- **Seen:** the mpl-versus-mkhtml pixel test fails when run alone, at HEAD before task H too (an order dependence;
  it passes in the suite). Pages of earlier sets stay in their folders. `statistics.csv` describes the last drawing.
- **The slow suite on the conda-base stack** (its first run there, 2026-10-22): 38 of 41 pass after task H's path
  fixes (`67434ff`); the third is the pixel test's order dependence (above). `test_gates_p1.py::test_the_legacy_reference_is_reproduced_byte_for_byte[MSTW|NNLO]` fail, at
  `4bf2e06` (before task H) too: one digit of the YODA differs (byte 323) from `tests/reference/`, so the rebuilt
  stack's Pythia/Rivet/LHAPDF, not the runner. The references are never regenerated: for the user to judge.

### Context

The user's notes (2026-10-21), written after a 38-point run in a real study's work dir
(a 38-point generator × PDF configuration, `04_generator_pdf`, ~21 h per Sherpa point):

1. Pages of k points cut from one run (24 points → 8 pages of 3, or 4 of 8): run once, mix and match later.
2. Named point sets, `[[1,4,6,8], [1,2,4,9], "all"]`, by index or tag, whatever the plot axes.
3. Replot a run after its configs or cards changed: a copy of its config kept with its record, editable,
   that `heimdall plot` (and `run`) read; the plot configuration separable from the run's.
4. Logs inside records/, points in `points/`: `records/<P>/<Name>/{points, logs, plots}`,
   `results/<P>/<Name>/{points, plots}`.
5. The live view: the tool's "error line" off the progress row (gone, or a line of its own below).
6. The run's blocks: `ok after … at <finish time>`, a blank line after the heading and after each block.
7. Sherpa's event progress parsed properly (BATCH_MODE, EVENT_DISPLAY_INTERVAL; MPI noted).
8. Statistics from the pages: each curve's area, the absolute area between it and the reference data.

**What the code does today (read 2026-10-21):**
- **Replot (item 3) is blocked by identity.** `plot.pages` keeps `p for p in plans if is_complete(p)`
  (`framework/runner/plot.py:377`), and `record.is_complete` compares `.complete` with the identity planned
  *now* (`record.py:255`). Any card edit, a rebuilt binary (`exe_sha256`; the stack was just rebuilt on the
  conda base, N18), or a commented-out value drops those points from the pages. In the work dir,
  `records/<P>/<run>/04_generator_pdf/points.json` lists 38 complete points, but `common.toml` now has most
  PDFs commented out, so the config plans 6: the 38-point run cannot be redrawn. Compare figures re-plan
  the other configuration the same way (`cli.others_of`, `cli.py:362`).
- **The layout is built in a few places:** `tools.run_dir` / `tools.point_dirs` (`tools.py:605,624`:
  `logs/<run>/<point>`, `results/<run>/<point>`), `record.records_of` (`record.py:232`: logs → records,
  mirrored), and `plan.out.parent / "plots"` in `plot.pages` and `plot.point_yodas`. Identities hold
  `{out}`/`{res}` (`tools._argv`, `tools.py:1367`, `_portable_parts`), so moving a point's folders changes no
  identity (V132, V137). `heimdall migrate --layout` exists (V132: `output/` → records/logs/.cache).
- **Pages:** `plot._pages` groups the complete points by `plot_points` key into `by_page`
  (`plot.py:605`); curves get labels from the curve axes (`_curve_label`, `_curve_look`).
  `sweep.select_points` (`sweep.py:142`) already parses `--points` (tags, 1-based indices, names,
  `quantity=tag`). `--set` takes TOML literals (`config.apply_sets`).
- **Paint** does void → align → normalise → range per page (`src/Apps/Paint/main.cc:99–131`) and writes
  `<page>.toml.ranges.json` with `--ranges`; with several pages it prints a JSON line per page. `Transform.hh`
  has `rebinned` (a density onto a span).
- **The run's blocks** are `watch.PlainView._block` / `LiveView._block` (`watch.py:309,358`); the point's
  `done` event carries `t`. The live row's last column is `s.warning` (yellow) or, with no count, `s.last_line`
  (`watch.py:384`).
- **Sherpa** has no `filters.toml` (`status = "none"`), so the view shows its last line (often "Four momentum
  not conserved. Rejecting event."). Sherpa 3.0.5's own code (`SHERPA/Main/Sherpa.C:270–295`,
  `ATOOLS/Org/Run_Parameter.C:197`): with no `LOG_FILE`, `BATCH_MODE` is 1, so the counter is redrawn with
  `ESC[1A` and `\r` on two lines; it prints at 1–10, 20–100, …, then every 100 000 events (10M events: a line
  per ~13 min at these rates, hence `stall_after = 5200`). Bit 2: one line per print, `XS = …` on it. Bit 4:
  every `EVENT_DISPLAY_INTERVAL` events. Bit 16: `<s>s elapsed / <s>s left`, plain seconds.
- **Card lines and argv are in the identity** (`tools.py:1154,1367`), so a `BATCH_MODE` line in the card or
  argv would mark every Sherpa point changed: 21 h each. It must go to the process without entering the identity.
- A tool's output is kept in memory (last 200 lines), written only when it fails, or whole with `--logs`
  (`status.Reader`, V72); a filter's progress gives `done` (and `total` if printed), never a rate.

### Priority (the skill's score: (Impact + Risk) × (6 − Effort))

| Item | Impact | Risk if left | Effort | Score | Phase |
|---|---|---|---|---|---|
| H3 Sherpa progress | 4 (21 h points watched blind) | 3 (a hang hides 1.5 h behind `stall_after`) | 2 | 28 | 1 |
| H2 The live view's note line | 3 | 1 | 1 | 20 | 1 |
| H5 Replot from the record | 5 (a 38-point run cannot be redrawn) | 4 (any config or stack change orphans results) | 4 | 18 | 3 |
| H1 Finish time, blank lines | 2 | 1 | 1 | 15 | 1 |
| H6 Point sets and split pages | 4 | 1 | 3 | 15 | 4 |
| H4 One records/ tree | 3 | 3 (moving real results) | 4 | 12 | 2 |
| H7 Page statistics (table, legends) | 3 | 1 | 3 | 12 | 4 |
| H8 A page per statistic | 3 | 1 | 3 | 12 | 4 |

The layout (H4) comes before the record work (H5) despite its score: the snapshot and record-built pages are
then written once, in their final places. Phases are committed one at a time, each with its V-row (V156…),
and each phase ships only on the user's order.

### Phase 1: what a run shows (no identity or layout change)

#### H1. The run's blocks
- `watch.PlainView._block` and `LiveView._block`: `… ── ok after 21h 5min 20s at Tue 21 Oct 14:03`, the local
  time of the event's `t` (the finish; a stopped or failed point says it too). Then a blank line, the block's
  lines, and a blank line. `LiveView.render` drops its leading blank line (the block now ends with one).
  The plot stage's summary then stands apart on its own.
- `watch.finished(t)`: the format, one function; tests in `tests/runner/test_watch.py`.

#### H2. The live view's note on its own line
- `LiveView._rows`: the row is tool, phase, bar, count, rate and ETA. A warning or error goes on a line of its
  own under its row (`      ↳ <text>`, yellow or red, cut to the terminal's width). A tool with no count and no
  phase shows its last line there, dim, as its only sign of life. Lines with progress show no last line.
- `PlainView._tick` keeps its one line per running point, without the last line once a count exists.
- `status.Reader.output`: ANSI escapes stripped (`\x1b\[[0-9;?]*[A-Za-z]`) from what is shown and matched
  (Sherpa colours its messages); the log keeps the bytes.

#### H3. Sherpa's progress
- **Display arguments outside the identity:** a tool folder's `[command] display = [...]`, argv pieces that
  change only what the program prints, appended to `step.argv` after `identity_parts["argv"]` is taken
  (`tools._argv`); the folder check and 05 §9 document them ("never in the identity: they may not change what
  the tool makes"). Placeholders: `{events}`, and `{display_every}` = max(100, events // 1000).
- `framework/tools/sherpa/tool.toml`: `display = ["BATCH_MODE: 23", "EVENT_DISPLAY_INTERVAL: {display_every}"]`
  (1 + 2 + 4 + 16: batch, a line per print, fixed steps, seconds). Sherpa's command line wins over the card,
  so a card's `BATCH_MODE` no longer matters; 05 §13 says so. `status = "filters"`.
- **`framework/tools/sherpa/filters.toml`** (new; rules in order, first match wins):
  - progress: `^\s*Event (?P<done>\d+) \( ?(?P<elapsed>[\d.e+]+) ?s elapsed / (?P<left>[\d.e+]+) ?s left`, and
    the default form (`Xh Ym Zs`) for a card that overrides us;
  - xsec: `XS = (?P<value>\S+) pb \+- \( (?P<err>\S+) pb` (a new `emit = "xsec"` kind; `ToolState.xsec` exists);
  - phase `generating` on the first event line;
  - ignore: the routine `Four momentum not conserved. Rejecting event`, `FourMomentumConservation throws`,
    `not onshell`, `reduced overall prescale`;
  - warn `^Warning`, error `(?:^Error|ERROR|Exception)`.
- **Generic, in `status`:** a progress rule's `elapsed` group gives `rate = done / elapsed`; otherwise the
  rate is measured from successive counts (a smoothed rate, as App_Pythia's). A tool that makes or reads events
  (`produces_events`, `consumes_events`) starts with `total = plan.events`, so Sherpa and Rivet get a bar and an
  ETA (`execute.run_group` builds the `ToolState`).
- `stall_after` stays a user key; with a line per ~1000th of the run, the work dir's 5200 s can go back to the
  default (the user's file: say so, not change it).
- **Parallel generation:** the replicas recipe, documented (Decisions); MPI noted, not built.
- Ledger: an L-row for Sherpa's counter (the bits and the default cadence above, from its 3.0.5 source).
- Tests: the filter on lines from the real log (both forms, colours), `display` absent from the identity
  (a plan's identity with and without it is the same), the rate from `elapsed`, `total` from the events.

### Phase 2: one records/ tree (H4; amends V132)

**The layout** (`<run>` = `<P>/<name>/<NN_label>`):

```
records/<run>/points.json  status.jsonl (--journal)  cluster/
records/<run>/points/<point>/    provenance.json, identity.json, .complete   (kept)
records/<run>/logs/<point>/      the working folder: cards/, config/, <tag>.log, .lock, FIFOs while running
records/<run>/plots/             the page documents (and, with keep cache, the figures' working files)
records/<run>/config/            the run's snapshot (phase 3)
results/<run>/points/<point>/    the products
results/<run>/plots/<backend>/   the pages, index.html, statistics.csv (phase 4)
results/<run>/pre/, post/        unchanged: later stages name their products, so their paths stay
```

- **Lifecycle stays readable:** `records/<run>/logs/` is what `heimdall clean` removes (no plan's folders), as
  `logs/` was; `points/` is kept and touched only by `clean --records`; `.cache/` is unchanged. The working
  folder's `logs/` subfolder goes: a tool's log is `records/<run>/logs/<point>/<tag>.log` (no argv names it,
  so no identity moves). Point names no longer clash with `plots`, `pre` … in `points/`, but a stage still
  shares `logs/` and `points/` with them: `RESERVED` stays.
- **Code:** a `RunFolders` value in `tools.py` (record, results, and their `points`, `logs`, `plots`, `config`),
  made by `tools.folders(run, configuration)`; `point_dirs` returns `(folders.logs / name, folders.points_results
  / name)` (stages: `pre`/`post` results where they are); `record.records_of` becomes `record_dir(plan)` =
  `folders.points / name`; `plot.pages`, `plot.point_yodas`, `post.py:78`, `cluster.py:158`, `house.clean_targets`,
  `execute._tidy` (`is_relative_to(records_root())`), `cli.journal_path`, `cli` reproduce (`.reproduce` under
  `records/<P>/`), `deck.requested` (provenance in `points/`) use it. `paths.logs_root` and `$HEP_LOGS` go:
  `$HEP_LOGS` joins `paths.RETIRED` ("logs live in records/<run>/logs/"); `cluster.ROOTS` and `tests/conftest.py`
  drop it; CLAUDE.md's testing line too.
- **`heimdall migrate --layout`** gains the step from today's layout (it already moves `output/`): per
  configuration folder with a `points.json`, a dry run listing every move, then `--apply`: record folders into
  `points/`, `logs/<run>/<point>/` into `records/<run>/logs/<point>/` (its `logs/*.log` up one level),
  `logs/<run>/plots/` and `status.jsonl` into `records/<run>/`, `results/<run>/<point>/` into `points/`, and
  `points.json`'s `products`, `results`, `output` rewritten. Renames only (same filesystem), nothing deleted;
  an empty top-level `logs/` left for the user to remove. Every command in a work dir with the old layout says so
  (as `output/` does). The work dir's HEIMDALL.md folder table (`framework/templates/work/`) and `.gitignore`
  follow; `heimdall setup . --refresh` brings them.
- **Verification:** identities of the fixture's every configuration (`--dry-run`) before and after: equal for
  every point; a post stage that reads the points' products moves once (its argv names their new path), said in
  the V-row. If any point identity moves, stop and report. Then on the real work dir: dry run shown to the
  user, `--apply` only on their word, then `heimdall status` must show the same complete points.

### Phase 3: replot (and rerun) from the record (H5)

- **The snapshot.** When a configuration's points run (not `--only plot`), its folder gets
  `records/<run>/config/`: the run TOML and every file it imports, byte for byte, under `<project>/` as in
  `configs/`, the base cards they name (bare paths, the project's), and `snapshot.toml` (source paths and
  sha256s, the configuration's key, the `--set`s, Heimdall's revision, when). A few KB, a record. A later run
  of the same folder replaces it with its points.json (the record says what the folder holds); a serial keeps
  an old run whole. Files named `./…` or absolute (datasets, modules, tool folders) are read live, and
  `snapshot.toml` lists them.
- **A record is a config:** `heimdall plot|run|check RECORD`, where RECORD is `<P>/<name>/<NN_label>` (three
  parts; a config is two) or a path into `records/` or `results/`. It loads the snapshot with `configs_root()`
  set to `records/<run>/config/` (a `paths` override), so bare imports and cards resolve inside it, re-applies
  its `--set`s, and fixes the configuration. `heimdall run RECORD` then plans from the cards as they were:
  complete points skip, missing ones run into the same folder. Editing the snapshot's `[plot]` restyles that
  run alone.
- **Pages from what was recorded:** the plot stage takes members (`plot.Member`: name, choice, values, texts,
  YODA, run), built from plans (live) or from the record: `points.json` and each point's `.complete` equal to its
  recorded identity and its products present. `heimdall plot RECORD` plans no tool: no stack beyond Paint.
  `points.json` gains each point's `texts` (Rivet's `{opt:…}`) so record pages cite them.
- **The live config too** (the user's choice): `plot.pages` stops filtering on `is_complete(plan)`; a planned
  point is drawn when its record is complete, and the stage notes those whose recorded identity is not today's
  (`record.recorded_identity` vs `plan.identity`), at most a few names and the count, with the `--why` hint.
  `cli.others_of` (compare figures) does the same.
- **A compare figure may name a record** (`configurations = ["generator_pdf", "<P>/<run>/04_generator_pdf"]`),
  read as recorded.
- **Plot settings apart from the run's:** already possible by import (`[file] import = [{ from =
  "<run>_pages", only = ["plot"] }]`); 03 §3 says it as the way. New: `heimdall plot CONFIG|RECORD --plot FILE`,
  a TOML whose `[plot]` replaces the run's for that drawing (checked as a run's is).
- Code: `cli.cmd_plot`, `cli.build_plans` (a record argument), `paths` (the configs root override),
  `record.write_snapshot`, `results.py` (the manifest's reader, shared), `plot.py` (members), `status`
  (`heimdall status RECORD` reads the record as it does a config).
- Tests: a fixture run, then its card edited in the scratch copy: `heimdall plot RECORD` draws every point;
  `heimdall run RECORD` skips them all; a compare figure with a record; the snapshot's files and sha256s.

### Phase 4: pages from chosen points, and their statistics

#### H6. Point sets and split pages
- `[plot]` (and a defined or overlay figure, as page keys):
  ```toml
  sets  = [[1, 4, 6, 8], [1, 2, 4, 9], "all"]   # a page folder each: set1, set2, all
  split = 3                                       # at most 3 points a page, in order: py8-1, py8-2, …
  ```
  - A set is a list of selectors, or one selector, or `{ name = "lo", points = [...] }`. A selector is a
    1-based index (as "point 34/38" counts), a point name, a glob of names (`"sh3_NNPDF40*"`), a tag
    (`"py8"`: every point with it), `"quantity=tag"`, or `"all"`. `sweep.select_points` grows lists, globs and
    `"all"`, and keeps the order written. A string set names its folder (`"pdf=X"` → `pdf-X`); a list is
    `set<k>`.
  - `sets` replaces the `plot_points` cells for these pages; `split` cuts each cell (or set) into pages of at
    most N points, in order (`<cell>-<k>`, or `part<k>` with one cell). Ratios divide by a page's first point.
  - A curve is labelled by the quantities that differ among its page's points (all of them on a mixed set);
    `{cell}` is the set's or part's name.
  - merged, scan and compare figures page by `plot_points` only: `sets`/`split` there are refused, with the hint.
  - A selector matching no point is refused when the file is read (at plan time for a record); a set without
    complete points is skipped and said.
  - `heimdall plot … --points SEL`: one set from the command line (`--set 'plot.sets=[…]'` works too).
- Code: `plot._pages` (`by_page` from sets/split), `plot.check_figures`, `sweep.select_points`, the schema's
  `[plot]` and figure keys, 03 §3 and §7, 04 §11.

#### H7. Page statistics
- **Computed by Paint**, on the numbers it draws (after void, align and normalise, over the drawn x range), so
  every backend's pages agree: per curve `area` (Σ y·Δx) and its error; against the reference (the data, else the
  page's first curve, the ratio's): `abs_area` = Σ |y − y_ref|·Δx on the reference's bins (`rebinned`),
  `rel_abs_area` = abs_area / ref_area, `chi2` and `ndf` (bins compared).
  `Paint::statistics` in `Transform.hh`, printed as a JSON line per page; a C++ test in `tests/cxx/`.
- **The table, on by default:** the plot stage writes `results/<run>/plots/statistics.csv` (page, cell, object,
  curve, points, bins, area, area_err, reference, ref_area, abs_area, rel_abs_area, chi2, ndf, chi2_ndf) and
  says where in its summary line; `[plot] statistics = false` turns it off. With `--ranges` (the mpl and yoda
  backends) the same numbers go into `<page>.toml.ranges.json`, so no backend computes its own.
- **In the legends, when asked:** `[plot] legend_statistic = "chi2_ndf"` (or `abs_area`, `rel_abs_area`,
  `area`; a figure may set its own) appends it to each curve's legend entry (`… (χ²/ndf 1.31)`); Paint writes it,
  mpl reads it from the ranges file.
- Rebuilding Paint changes no identity (plot-only).

#### H8. A page per statistic (when declared)
- A figure class `statistic`: `statistic = "chi2_ndf"` (any column above), `objects = ["d01-*"]`, optional
  `sort = true` (best first) and `combine_objects = "sum"` (one page summing over its objects instead of a page
  each). Per cell (or set) and object: a page whose x axis is the cell's points by their curve labels, one bin
  each, y the statistic, drawn as markers.
- Built after the pages are drawn, from the statistics just computed: a ROOT file with labelled bins
  (`records/<run>/plots/statistic/<name>/`), drawn by Paint, which learns alphanumeric x labels (`x_bin_labels`
  in the page document → `TAxis::SetBinLabel`); mpl draws the same labels.
- Pages: `<cell>/<name>/<object>`; the figure table in 03 §7.9 and 04 §11.2; refused in a compare figure's list.

### Decisions (the user, 2026-10-21, while planning)

- **Live plot draws what was recorded, with a note:** `heimdall plot CONFIG CFG` (and a run's plot stage)
  draws every planned point whose record is complete (`.complete` there, products present), and names those
  whose recorded identity differs from today's plan: "12 points ran with other inputs than the config gives now
  (py8_NNPDF23lo, …): drawn as recorded; heimdall run … --why". A rebuilt stack no longer empties the pages.
- **Parallel Sherpa: the recipe, no new code.** Seed replicas with `combine` and `parallelism` already run K
  Sherpa processes with their own seeds and merge each value's YODAs (02 §7.3, V35, V36). Written up in 02 §7.3
  and 05 §13 with a Sherpa example (`to = { "sherpa/seed" = true }`, checked in the scratch work dir first; with
  a generator selector, both generators' seeds; `events` per replica = the total ÷ K). MPI is noted as what
  it is: it speeds the integration (the cached prepare), needs Sherpa built with `-DSHERPA_ENABLE_MPI=ON`, and is
  not built.
- **Statistics:** the CSV on by default (`[plot] statistics = false` turns it off); the legend's statistic and a
  page per statistic only when asked for (H7, H8).
- **The live view's note goes on its own line** below the tool's row (H2).

### Verification (each phase)
- `source gjallarhorn.sh`; the fast suite light (`taskset -c 0-5 nice -n 10 python -m pytest -q -m "not slow"`),
  one session at a time; the C++ tests for Paint; the slow suite once at the end, alone.
- Phase 1: a short Sherpa point in the scratch work dir (`--logs`): the live view's bar, rate and ETA; the
  log's lines one per print; identities before and after equal.
- Phase 2: the identity gate above; `heimdall migrate --layout` on a scratch copy of the real work dir's
  `records/ results/ logs/` first (copied, not moved), `heimdall status` equal before and after.
- Phase 3: the replot test above; then `heimdall plot <P>/<run>/04_generator_pdf` in the real work dir (after its
  migration): 38 points' pages.
- Phase 4: sets `[[1,20],"all"]` and `split = 8` on that record; `statistics.csv` checked by hand on one page
  against the YODA (every curve's area is 1 on a normalised page); `legend_statistic` on one page in Paint and
  mpl; a `statistic` figure of `chi2_ndf` over the 38 points, sorted.
- Docs: 02, 03, 04, 05, 06 §1 and §10, 07 (V156… in building order, the ledger row); `heimdall make --framework
  docs schema` after the schema's docs change.

## Task I: High-Energy cleaned up into a lean work dir; its aux/ into Heimdall as editor/ (done 2026-10-22, V161)

The user: "cleanup High-Energy and migrate it to Heimdall" (06_Workdirs.md's parked appendix, D31). Answers:
High-Energy keeps **Comparison and Lambda** (PhotoProduction is Brookhaven's since `ea43a70`); **aux/** (the VS
Code tooling) moves into Heimdall as **`editor/`**; untracked **debris deleted, data kept**; **local commits only**
(no branch change, no push). Task H phase 4 is uncommitted here (21 files, V159–V160): this task edits none of them.

1. Heimdall `editor/` from `git archive` of High-Energy's `aux/` (1,311 files), `aux/` paths in them → `editor/`,
   CLAUDE.md's layout row. Commit A.
2. High-Energy debris out: `py.py`, `MG5_debug`, `ME5_debug`, `output/`, `build/`, `.pytest_cache/`. v1 data out of
   Heimdall's layout readers (`migrate.logs_moves`, `deck_moves`): `results/PhotoProduction`, `reports/*` →
   `archive/v1/` (ignored). `literature/`, `cross_machine/`, `datasets/` stay.
3. `git rm` the move map's framework side (`utils/ tests/ bots/ Makefile pytest.ini`, `docs/` but `Untitled-1.md`),
   `aux/`, `configs/PhotoProduction`, `modules/PhotoProduction`: 24 tracked paths stay.
4. `heimdall setup --adopt ~/Github/High-Energy` (recognised in workdirs.toml).
5. `heimdall migrate` then `--v3` (diffs kept), comments naming `utils/` or `hep` → Heimdall's names.
6. One local commit by path; 7. `heimdall build` (light), `heimdall check`, `heimdall run … --plan` for both.
8. 06_Workdirs.md appendix and 01_Target.md §4.4/§7 say it was done; V161; commit B.

Done: Heimdall `2186975` (editor/) and the docs commit; High-Energy `b637599` (local, on `rework`; 28 tracked
files; build and check pass; recognised in workdirs.toml). Not done: a real run of either study; the push.

## Task F: generators and tool setups compared in one configuration (done 2026-10-15, V151–V154)

Built in the order F3, F4, F1, F2, F5 (`3bdd4ea`, `292546d`, `8d75401`, `31f24be`, and the docs commit). As planned,
with these differences: the record rows are numbered in building order; a `@q` alone in a one-member group
(`["@q"]`) is a chain entry too (the parser cannot tell the two apart); a listed group's page key is a tuple
of its paged members' indices; the slow test runs listed points in a work dir of its own (a new fixture config
would need a v2 reference text, which the rules do not allow adding).

**The user's questions (2026-10-14):** "How about being able to sweep across tools configurations (such
as for comparative studies of event generators); or we just execute separate runs overlay run results."
Then: "make plan; also for three, make value = ["A", ["B","C"]] turn ["@var", "D"] into ["A", ["B","C"],
"D"] (as far as the final nesting is valid/permitted/makes sense, else throw an error). Also look into
coupling of vars: ["@var1", "@var2"] and points are [A,E] [B,E] [B,G] [C,F]", "simultaneous setting of
multiple vars for a point". Nothing is built before the user's order.

**What exists (read from the code, and dry-run in a scratch copy of the fixture work dir):**
- A quantity chooses a tool (V19): `chain = [["@generator", "spectra"], "yd2rt"]`, the values tool
  tables (`Generators/generators`: Pythia, Herwig, Sherpa; one page per object, a curve per generator).
  Two tables of one tool (`[tools.monash]` and `[tools.a14]`, both `uses = "pythia"`, own cards) make
  `@tune` compare tool setups.
- **Coupled selectors already plan:** a compound quantity whose fields are selector names,
  `fields = { gen = "gen", ana = "ana" }` with rows AE, BE, BG, CF and `chain = [["@gen", "@ana"]]`, gave
  4 points with pythia+spectra, herwig+spectra, herwig+spectra2, sherpa+spectra2. Undocumented and
  untested.
- Across configurations: the `compare` figure (same page and curve axes; another run TOML's too);
  `heimdall overlay` for any files.

**Found limits:**
- **L-a. Chains of different shapes** cannot be alternatives: `@q` stands for one tool table, so
  MadGraph → Pythia against Sherpa alone needs two configurations and a `compare` figure.
- **L-b. A varied value one alternative does not read multiplies its points.** `vary = ["generator",
  "pt0ref"]`, pT0Ref Pythia's only: hw7_p30 and hw7_p34 (and Sherpa's two) planned and would run, the
  same physics with different seeds, curves labelled by a value they never read; no warning. C7 counts
  consumers per configuration (any alternative), not per point.
- **L-c. One `pdf` cannot feed several generators.** V40: Pythia takes `LHAPDF6:<set>` and refuses the
  bare installed name; Sherpa refuses the prefix (both refusals seen); Herwig's folder maps no `pdf`.
- **L-d. A coupled group is one plot axis:** `plot_points` naming a member selects the whole group, so
  "a page per PDF, a curve per generator that ran it" cannot be drawn from a coupled sweep.

### F1. A selector's value may be a piece of chain (the user's form)

A selector quantity's value is a tool tag (as today) or a **fragment**: a list whose items are tags or
groups (lists of tags). It is spliced where the `@q` entry stands:
- **At the chain's top level** (`["@var", "D"]`): a tag is one group (today); a fragment's items become
  the chain's entries in its place: `value = ["A", ["B", "C"]]` → `["A", ["B", "C"], "D"]`, A then B
  and C together, then D.
- **Inside a group** (`[["@var", "D"]]`): a tag is a member (today); a fragment of tags joins the group
  (`["A", "B"]` → `[["A", "B", "D"]]`, all together); a fragment holding a group is refused (groups nest
  one level: "the value 'mg5py8' of [quantities.var] puts a group inside the group of @var; write
  @var at the chain's top level").
- **`[]`** splices nothing: an alternative without a step ("with and without Delphes"). A group left
  empty is refused (as a written one is).
- **The result is checked as a written chain is**, for every value of the quantity (not only the
  points run), when the file is read: each tag a `[tools.<tag>]` table (C5), a tool at most once in a
  resolved chain (its outputs would collide: refused, naming the value), and the interfaces (F1's last
  point). A value's tags are what `heimdall clean` and the alternatives' consumer table see
  (`house.py`, `tools.py` alternatives, flattened).
- **The interfaces (FIFO or file, `[prelim]`) are inferred per resolved chain**, memoised by its groups:
  today `_inferred` unions the alternatives, which cannot work once alternatives have different groups
  (one may read an output in its own group, another later). A point's `prelim` (and so its identity)
  is its own chain's. Identities stay as they are where the alternatives share their interfaces: the
  fixture's do (checked by hand: `Generators/generators --dry-run` identities before and after, on one
  machine). The only other `@` user found is High-Energy's legacy `Comparison/generators.toml`, not a
  work dir.
- `pre` and `post` keep what they take today (`@` is resolved for the points' chain only).
- Code: `config.py` (`_groups` accepts `@` entries as now; a new `_splice(groups, quantities, tools)`
  checks every value at load), `tools.py` (`_resolve_chain` splices; `plan_point` takes the resolved
  chain's prelim; the alternatives flattened), `house.py` (tags flattened), `v3.py` (a selector's value
  may be a list: no shape refusal).

### F2. Points that set several quantities at once

Two forms, both kept:
- **A compound quantity** (exists, 04 §8.4): new values written row by row, one axis. **Documented and
  tested now with selector fields** (`fields = { gen = "gen", ana = "ana" }`, `chain = [["@gen", "@ana"]]`,
  rows AE, BE, BG, CF: the user's example, which plans today). Values may be fragments (F1).
- **New: listed combinations of quantities already declared**, in `vary`:

  ```toml
  [cfgs.compare]
  vary  = ["sqrts", { points = [
    { generator = "py8", pdf = "nn23" },
    { generator = "py8", pdf = "ct14" },
    { generator = "hw7", pdf = "ct14" },
    { generator = "sh3" },                  # Sherpa at its own card's PDF
  ] }]
  chain = [["@generator", "spectra"]]
  ```

  - Each row names one point of each quantity it sets, by tag (or `"#N"`), keeping that quantity's
    value, label and style; the group is one axis of the grid, crossed with the others (`sqrts`).
  - **A row may leave a quantity out:** that point sets nothing for it (the card's own value stands,
    no line written, no consumer needed there). This is how one alternative skips a setting only
    another reads (L-b's fix, beside F3's refusal).
  - The point's name joins the row's tags in the order the quantities first appear in the rows
    (`py8_nn23`, `sh3`). Two equal rows are refused.
  - **`plot_points` may name a member** (L-d): the pages are its tags, the curves the rows on each page
    (`plot_points = ["pdf"]`: a page per PDF, a curve per generator that ran it). A row that leaves the
    page's member out is refused there, with the hint to set it or not page by it. Naming every member,
    or `[]`, works as for a group today.
  - A quantity's `exclude` does not apply to listed rows (they are explicit); `combine` may not name a
    member (refused: replicas are a quantity of their own).
- Code: `v3.py` (the `vary` entry `{ points = [...] }`; a quantity's tags), `quantities.py` (points
  expanded from rows: a choice per row, members left out absent from `point.choice`), `config.py`
  (C3 for listed groups: each member declared, each tag one of its points, no equal rows), `plot.py`
  (page axes by a member of a listed group), `schema` (run.toml: `vary`'s table entry; `make docs`).

### F3. A varied value no tool of a point reads is refused (L-b)

- C7 stays per configuration and gains a per-point rule: every **varied** quantity of a point has a
  consumer among the tools of **that point's** resolved chain (and its `generate_cards`). Otherwise the
  plan is refused: "hw7_p30: pt0ref is varied, but no tool of this point reads it (herwig, spectra,
  yd2rt): its points would differ only by their seeds", hint: "list the combinations, leaving pt0ref
  out of herwig's rows (vary = [{ points = [...] }]), or vary it in a configuration of its own".
- A **fixed** value a point does not read stays accepted (the fixture's `beams`, which Herwig's pp
  snippet sets itself): it multiplies nothing.
- Code: `tools.py` (`plan_point`: the consumer table filtered by the point's own tags; the refusal),
  docs 04 §8.1 and §13 (C7).

### F4. One `pdf` for every generator (L-c)

- **A provider check may return the value as its tool writes it** (core, generic: `check_provider`
  returns the value `apply` writes; None keeps it). `lhapdf`'s forms:
  - `pythia`: a bare installed LHAPDF set (`CT14lo`, `CT14lo/3`) is written `LHAPDF6:CT14lo[/3]`; a
    prefixed one, one of Pythia's own set numbers or a grid file as written (V40's reason holds:
    numbers are never prefixed). Today's prefixed values write the same line: identities unchanged.
  - `bare` (Sherpa): `LHAPDF6:<set>` is written `<set>` instead of refused.
  - `set` (new, Herwig): the set's name; a `/member` is refused (Herwig's is `:Member`, in the card).
- **A scalar to a `keys` mapping is written to every key** (today it is refused as "expected N
  values"); a list still spreads over them.
- **Herwig maps `pdf`**: `pdf = { keys = ["/Herwig/Partons/HardLOPDF:PDFName",
  "/Herwig/Partons/ShowerLOPDF:PDFName", "/Herwig/Partons/MPIPDF:PDFName",
  "/Herwig/Partons/RemnantPDF:PDFName"], check = "lhapdf:set" }`: the four objects Herwig's own
  defaults set (`CT14lo` each, `share/Herwig/defaults/PDF.in`), as Pythia's `PDF:pSet` covers its hard
  process, shower and MPI. The NLO objects stay the card's. A tune is fitted with its PDF, for every
  generator alike (L24: matching PDFs is part of a fair comparison); the manual says so.
- The ledger gains a Herwig PDF row (none exists; CLAUDE.md asks to read a tool's rows first).
- Code: `quantities.py` (`check_provider`), `tools.py` (`apply`: the returned value; `keys` with a
  scalar), `framework/tools/lhapdf/provider.py`, `framework/tools/herwig/quantities.toml`,
  `framework/tools/sherpa/quantities.toml` (unchanged form), docs 05 (pythia, sherpa, herwig rows).

### F5. Docs and record

02 §5.3 rewritten as "comparing generators and tool setups" (selector values and fragments, listed
combinations, one `pdf`, the per-point refusal, when a `compare` figure is still the way); 04 §5.1
(`vary`'s listed form), §5.2 (`plot_points` by a member), §5.3 (fragments), §8.1 and §13 (C5, C7), §8.4
(selector fields); 05 (the pdf rows); 06 (config: resolved chains and their interfaces); 07, numbered in
building order: V151 (the per-point consumer rule), V152 (one `pdf` for every generator; amends V40),
V153 (fragments), V154 (listed combinations; compound selector fields recorded), a ledger row for
Herwig's PDFs.

### Order, and verification

Order: F3 (small, a safety net), F4, F1, F2, F5; a commit each, the fast suite light between.

- Fast tests (new `tests/runner/test_selectors.py`, with a new fixture config
  `tests/fixtures/work/configs/Generators/combos.toml` added with it): F1's splices at the top level and
  in a group, `[]`, the refusals (a group in a group, a tool twice, an unknown tag in a value never
  run), per-chain interfaces; F2's rows (names, a member left out writes nothing, equal rows refused,
  `plot_points` by a member, a row without the page's member refused), compound selector fields (AE,
  BE, BG, CF); F3's refusal and a fixed unread value accepted; F4's spellings both ways, a scalar over
  `keys`, Herwig's four lines, and Pythia's own set number untouched.
- Identities: `Generators/generators --dry-run` before the first change and after the last, on one
  machine: the same identities and seeds.
- The slow suite once at the end (the generators' tests need a machine whose Herwig and Sherpa run:
  the new one).

## Notes from the fresh stack build (2026-10-15)

The reinstall is postponed (the USB would not boot: TPM/encryption). The user builds a fresh stack on this
machine instead, in a terminal of their own. What they say while it runs, to act on when ordered:

- **N1. A progress indicator while downloading.** Today `build_stack.download` copies the response in 1 MB
  chunks (`shutil.copyfileobj`) with no progress shown; a large tarball (ROOT, Geant4's data) looks like a hang.
  Wanted: bytes so far / total (`Content-Length`), the rate and an ETA, on the live line `Progress` already
  draws (`self.live`); one line per finished file when plain (`HEP_PLAIN`, no tty); the same for `fetch`'s
  downloads and pixi's (its own output, passed through).

- **N2. ROOT from source on the base: fixed (2026-10-15).** Its configure stopped on `gl2ps` (needed with
  `opengl`), and found libxml2's headers but not its library, so it turned `xml` off (conda-forge split
  `libxml2-devel` off `libxml2`). Both added to `base.toml`'s `[base.libraries] root`. CFITSIO is found the same
  half way, but ROOT does not ask for it.

- **N3. A test that reads the machine's Python path.** `test_stack_build.py::test_the_old_way_is_apt_and_a_venv`
  asserts the `base=system` script never says "pixi"; its venv is made from the running Python, which on a
  machine root with a conda base is `base/.pixi/envs/default/bin/python3`, so it fails there (not a change in
  behaviour). Fix: assert on the script's pixi commands, not on any path containing the word.

- **N4. CMake took the OS's headers on the base: fixed (2026-10-15).** ROOT's configure found gl2ps, libxml2,
  nlohmann/json, OpenGL, X11's Xinerama/Xrandr, VDT and CFITSIO in `/usr/include`, which conda's compiler never
  searches, so `TBufferJSON.cxx` failed on `nlohmann/json.hpp`. And a retry kept `forge/build/<pkg>/`, whose
  CMake cache still held those paths. Now: a CMake build starts from an empty build folder; on a Linux base,
  CMake ignores `/usr` and `/usr/local` (`build_stack.BASE_CMAKE`); the base gives ROOT `nlohmann_json` and
  OpenGL (`libgl-devel`, `libopengl-devel`, `libglx-devel`, `libglu`). The base changed, so every package built
  on it rebuilds once. A test that a CMake build on the base names those prefixes is still to write.

- **N5. YODA's HDF5 support was off: fixed (2026-10-15).** YODA's `m4/ax_lib_hdf5.m4` takes the HDF5 type from
  the wrapper's name (`*h5cc` serial, `*h5pcc` parallel, else "neither" and `.yoda.h5` off), and ours was
  `h5cc-plain`; YODA's headers still include HDF5's, so it failed on `H5Ipublic.h`. The wrapper is now
  `plain-h5cc` (`recipes/helpers/h5cc_plain.py`, the hdf5 and yoda recipes).

- **N6. A helper script's change rebuilds nothing.** `digest` hashes a recipe's fields, not the files its
  `pre`/`post` run (`recipes/helpers/h5cc_plain.py`), so N5's rename needed the helper run by hand or
  `--rebuild hdf5`. Wanted: a recipe's helpers hashed with it, as its patch is (`patch_sha256`).
  And YODA's configure keeps `.yoda.h5` on when the wrapper it is given does not exist ("HDF5 libraries... no",
  then the same compile error), so the yoda recipe should check `{dir_hdf5}/bin/plain-h5cc` exists first.
- **N7. ROOT built at `root_cores = 12` on this machine (14 GB of RAM, the conda base, 2026-10-15)**, the user's
  setting: the "3 GB a compiler" rule behind `root_cores = 0` (one per 3 GB) is cautious for ROOT here. Rivet
  built at 12 too. The rule may be loosened (or measured: peak memory per compiler).

- **N8. Rivet's analyses could not link on the base: fixed (2026-10-15).** `rivet-build` dedups its flags word
  by word (`xargs -n1 | sort -u`), which split `-isystem <base>/include` and left the bare folder on the
  linker's line ("ld: …/include: read: Is a directory"). `-isystem` is now joined to its path (`base.toml`'s
  `CPPFLAGS`, `build_stack`'s `{cflags}`, `rules.mk`'s `ON_BASE`), which GCC takes as one word.

- **N9. Pythia8's check read a PDF set not yet installed: fixed (2026-10-15).** Its check runs 100 events with
  `LHAPDF6:CT14lo`, and `pdfsets` came last in the build, so on a fresh root init failed ("unknown PDF CT14lo");
  the old machine had the sets already. `pdfsets` now comes right after `lhapdf` (in `standard.toml`, so the file
  is the order) and `pythia8` needs it.

- **N10. ThePEG took the OS's Boost: fixed (2026-10-15).** Its `boost.m4` found Boost 1.90 in `/usr/include`
  (unseen by conda's compiler) before the base's 1.92, so its unit-test check failed. `--with-boost={base}` for
  ThePEG and Herwig in `base.toml`, as zlib and GSL already were. Autotools packages have no CMake-style switch
  to keep out of `/usr` (N4): each macro that searches the OS needs pointing at the base.

- **N11. ThePEG's libraries lost crtendS.o: fixed (2026-10-15).** conda-forge's GCC 15 specs add `-L <dir>` with a
  space; the libtool in ThePEG's and Herwig's `configure` tests `x-L = "$p"` (never true; fixed in libtool 2.4.7 as
  `"x$p"`), so `postdeps` got two bare `-L`s, and `-L crtendS.o` took the end file for a folder ("undefined
  reference to __TMC_END__"). A `pre` step in `base.toml` makes the upstream fix to their `configure`. Checked: the
  other packages downloaded (LHAPDF, HepMC3, FastJet, YODA, Rivet, Pythia8, Sherpa, Whizard, Delphes, Geant4,
  MadGraph) do not carry that line.

- **N12. Whizard found OCaml 4.06: fixed (2026-10-15).** `ocaml-findlib` (in the base's Linux lists) holds OCaml at
  4.14.x, whose conda-forge builds need GCC 13 or 14; beside the base's GCC 15 the solve fell back to OCaml 4.06.1,
  too old for Whizard 3.1.8 ("found version 4.06.1, too old"). Whizard does not use findlib: dropped, and the solve
  gives OCaml 5.4.0 with GCC 15.3. But the base's lock kept 4.06.1, which `ocaml = "*"` still allows: OCaml is
  now asked for as `ocaml >=4.08` (Whizard's floor), and as a base tool, not a library (a compiler: its version
  rebuilds nothing). Whizard on OCaml 5 is yet to be built.
- **N13. Any change of the base marks the whole stack.** `base_hash` covers the versions of every library the
  base lists, and every package built on the base records it, so N12's change names ROOT and the rest as changed
  since built (not rebuilt on its own: `--rebuild` does it). The notice is noise for a package the change does not
  touch. Wanted: each
  package's digest takes the compilers and runtime, plus the base libraries it builds against (its own list and
  what its recipe names), so OCaml's change rebuilds Whizard alone.

- **N14. Whizard's OCaml build took conda's GPROF: fixed (2026-10-15).** conda's activation exports `GPROF` (its
  gprof's name); Whizard's Makefiles put `$(GPROF)` in `OCAMLOPTFLAGS` as a profiling flag and never set it, so
  ocamlopt got "x86_64-conda-linux-gnu-gprof" ("Don't know what to do with …"). `base.toml` gives Whizard
  `GPROF = ""`. The base's activation exports other tool names too (AR, NM, LD, …): a package that uses one
  of those names for something else will meet the same.

- **N15. Whizard's mcfio wanted `rpc/types.h`: fixed (2026-10-15).** glibc no longer ships SunRPC; Whizard asks
  pkg-config for `libtirpc`, which the base now gives (Whizard's list in `base.toml`).

- **N16. Whizard built without LHAPDF, as on both machines before: fixed (2026-10-15).** Its configure tests LHAPDF
  with `lhapdf-config --cxxflags` (LHAPDF 6.5: the build flags, no `-I`) and `--ldflags` (`-L` alone, no `-lLHAPDF`),
  so the test could not compile and Whizard built a dummy; the recipe's "linked" check caught it. Whizard's recipe
  now sets `CPATH` (the headers) and `LIBS` (`-lLHAPDF`, with its rpath); its configure then says "LHAPDF: yes,
  v6.5.6" (checked in the built tree).

- **N17. Geant4's data downloads inside its build, all or nothing (2026-10-15).** `geant4_data = ON` has CMake fetch
  ~2 GB of datasets during `cmake --build`; one truncated transfer (G4EMLOW 8.8, "Transferred a partial file")
  failed the package, and since N4 a retry recompiles Geant4 from an empty build folder (~20 min) before fetching
  again. Wanted: the datasets fetched by `build_stack`'s own downloader (resumed, checked, kept in forge/downloads,
  N1's progress) and given to CMake (`GEANT4_INSTALL_DATADIR` or unpacked into place), with the code built once.

- **N18. `@primary` built from source on the conda base, whole (2026-10-15)**, after N2–N17: every package and its
  checks, Geant4 on the second try (N17), MadAnalysis5 (a `status = "new"` recipe) installed. G11's first proof.
  The build's last step wrote the shell block into the real ~/.bashrc (`shell_rc` defaults on), which the user had
  asked to be asked about first: an agent running a build here passes `shell_rc=false` unless told otherwise.
  Next: `heimdall build --framework` (the apps against the new stack: identities change, the user's call) and the
  suites.

- **N19. Heimdall's apps built on the base (2026-10-15).** `App_Pythia` failed to link (`pthread_join`): the base's
  glibc 2.28 keeps threads in libpthread, which nothing linked; `rules.mk`'s `BASE` now has `-pthread`. The C++ tests
  pass. The fast suite then showed a point identity that moved with the machine root: the Delphes chain's script
  runs the base's Python, written `{machine}/base/…`, so a base kept where it was while the root's name moved
  changed it (V137's test). `paths` gains `{base}` ($HEP_BASE), longest-first like the others.
- **N20. Tests a conda-base root skips.** Seven shell tests (`test_setup.py`, `test_shellrc.py`) skip "no venv in
  the machine root": they know the venv only, so on the base they never run. The editor-schema test (`test_v3.py`)
  skips without `jsonschema`, which the venv had and the base lacks (`base_pypi` or the base's Python list).
- **N21. MadGraph made whole (2026-10-21).** The user: Pythia with HepMC2 too, for MadGraph's showers; HepMC2 in
  `@primary`; MadAnalysis 5 used by MadGraph without `install MadAnalysis5`; QCDLoop, Ninja, OneLOop, CutTools,
  IREGI, COLLIER. `hepmc2` and `qcdloop` recipes; Pythia `--with-hepmc2` (optional) and `--with-gzip` (MadGraph
  hands it `.lhe.gz`), `main164` built in its post (HepMC2 output: MadGraph's Delphes step is `DelphesHepMC2`);
  `recipes/madgraph.py` (the options, the loop libraries through MadGraph's offline installer and the tarballs
  it ships) and `recipes/madanalysis5.py` (`version.txt`, the base's zlib, SampleAnalyzer); `HEPTools/lib` on
  `LD_LIBRARY_PATH`. Seen: e+e- → μ+μ- at LO with MA5 at parton level, the shower writing HepMC2, MA5's
  reconstruction and hadron-level analysis; `check timing u u~ > d d~ [virt=QCD]` with Ninja, COLLIER, IREGI
  and CutTools. Not done: the MG5aMC_PY8 interface (MadGraph 3.8 showers with `main164`), Herwig's paths.
  Then the user's NLO shower: aMC@NLO's Pythia 8.3 driver includes two plugin headers that each define
  `PYTHIA8_PLUGIN_VERSIONS`' functions in 8.318; `madgraph.py noplugin` compiles it with `-DNOPLUGIN`.

## Audit 4: ghosts and gaps (2026-10-15)

[docs/audit_4/](../docs/audit_4/README.md), ordered by the user with task F ("initiate an audit for features and
capabilities that are present but not documented or used, abandoned halfway or not fully developed, deprecated
but still lingers as a ghost, hard to discern its purpose or usefulness"). Findings G1–G23 and a plan in four
phases; nothing built until the user orders a phase. The user decided Phase 2 on 2026-10-15 (retire G13, G14,
G15, G3, G5, G18, G16; keep G4; rename `hep.toml` to `heimdall.toml`; fix G12's messages, keep reading v2; mark
G7's unproven toolkits): docs/audit_4/02_Plan.md has the steps. Phases 1 and 2 are ready to build.

## Next: the reinstalled lab PC

The runbook is [docs/framework/](../docs/framework/README.md), P0–P4, from a clone of Heimdall (or the
bundle kept before the wipe). What it proves for the first time:
- **Rivet, ROOT, Pythia 8 and the rest built from source on the conda base.** Never finished on the old
  machine (it went down once at every core; the last try was stopped for the reinstall). `@primary`'s
  first build is the test; `root_cores` keeps ROOT's and Rivet's compilers to ~3 GB each.
- **The slow suite on a conda base.** Last baseline (old machine, `base = "system"`): 36 passed, 3 failed
  on the OS's libraries (Herwig, Sherpa, the three-generator test: exit 127).
- **The shell block.** The build writes `gjallarhorn` and `bifrost` into ~/.bashrc and ~/.zshrc
  (`shell_rc`); the old machine's real ~/.bashrc never had one (asked before writing, then the wipe).

## Not yet proven anywhere

- A real Apptainer image (`heimdall image build packages=@core-conda`, minutes; ask before the
  downloads). The old machine's `singularity` was broken (libsubid.so.4), so the tests use a fake runtime.
- Tasks A–E on the Mac.
- **`[cluster] image` is half a way (found 2026-10-14, in the cleanup pass).** The jobs run in the image,
  but `heimdall cluster` plans every point on the login node, outside it (planning reads the PDF sets,
  Rivet's data, the card checker), so the login node still needs a stack; inside the image there is no
  `sbatch`. Options, for the user: plan inside the image and have it write a `submit.sh` the host runs
  (chaining the job ids itself), or bind the site's Slurm client into the image. The docs say the limit.
- `heimdall cluster` on a real Slurm (an emulated one only; `--dry-run` first).
- docs/conda/03_Plan.md phase 3: the physics against the old stack, the tracked multi-platform lock, a
  bootstrap for clusters with Python < 3.11.

## Held: ask the user first

- **Identities:** `src/Module.hh` says `hep run` in an error string and `hep explain` in a comment;
  `src/App_yd2rt.cc` says `hep plot` in a comment. Editing Module.hh changes every module binary, so
  every point that ran one: rename them with the next deliberate rebuild.
- **The frozen fixture:** its `Makefile`'s error string names `setup.sh`; its configs' comments and
  `modules/Decay/README.md` say `hep run` (and `tests/reference/v2_configs/` mirrors the configs).
  Fixtures change only together with a test that needs it.

## Later, on the user's word

- [docs/audit_2/01_Health.md](../docs/audit_2/01_Health.md)'s R0–R3: verify the mpl pages against
  mkhtml's, after which the yoda backend goes (H11); quick fixes (a compare figure drawn once, H2);
  `runner/figures.py` and the figure-class rules in the schema; sheets, tests and docs.
- `heimdall migrate --stamp`: the stack's versions into `[config.meta].versions`.
- F8 `--more`; HTCondor and PBS for `heimdall cluster`; Paint's PDF line widths (about 2× too thick);
  the held C++/Rivet items (K3, K4, K7, K8, K10, yd2rt's dead parameter); `extends`/`common.toml` for
  validation ("not now").

## Standing constraints

- **Commits:** local, never pushed without asking, with the Co-Authored-By line; stage named paths only,
  never `commit -a`; the stack lives in the machine root `~/Himinbjorg`, outside the tree.
- **Tests:**
  - `source gjallarhorn.sh` (this Heimdall's) before make or pytest;
  - they run in the fixture work dir's copy, `$HEP_FORGE/scratch/work/` (V52, V112), never a real one;
  - one pytest session at a time, the slow suite on its own, and light: `taskset -c 0-5 nice`, and
    pytest directly rather than `make test` (its `make all` rebuilds the machine's apps);
  - a long build starts detached (`setsid nohup … < /dev/null &`), or a session's end kills it.
- **Approvals:**
  - the stack and every download need the user's approval; never write into `~/HEP` or its venv;
  - a rebuilt App_Pythia, App_yd2rt, InprocJets or Rivet plugin changes the identity of every point
    that ran it, so ask before rebuilding (Paint is plot-only and safe).
- **Docs:** after changing a schema key's `doc`/`notes`, base.toml's comments or the CLI's help, run
  `heimdall make --framework docs schema`.
- **Way of working:** never implement without an explicit order; plans first (saved here as they grow),
  questions when a request is ambiguous.
