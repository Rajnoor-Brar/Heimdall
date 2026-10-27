# Issues

Heimdall's pending work, one issue each: what is open, why, the fix, and when it counts as done.
Compiled on 2026-10-25 from `bots/current_plan.md`, `bots/intent.md`, `bots/archive.md`, `.plans/`
(audit 5 and its plan), `docs/Notes.md`, `.setup/`'s notes and `editor/Report.md`, which it replaces.
Each item was checked against the code and the machine root. What was already done was left out
(for example the held C++ fixes K3–K10, built as V63; Sherpa's progress lines, BATCH_MODE 23; Whizard
on OCaml 5; the Mac notes, now in `mac.toml`).

**How to use it**
- One issue per task. A plan being made is written into its issue as it grows. An idea is an issue
  labelled `idea`.
- **Status:** `open` · `decision` (waits for your choice) · `blocked` (waits for another issue) ·
  `held` (ask before doing: identities, downloads, your files) · `in progress`.
- **Priority:** P0 blocks a commit · P1 this cycle · P2 next · P3 when convenient.
- A finished issue is **deleted** from this file. Its history is its V-row in `docs/07_Record.md` and
  its commit.
- Nothing is built without your order. `docs/` is left for the docs pass, and an issue that changes
  what the manual says names the section it leaves stale.

## Plan (approved 2026-10-25)

The whole plan is [restructure_plan.md](restructure_plan.md); this section tracks it. Phase by phase,
each built, committed with its V-rows and reported, then the next on your word. A phase deletes the
issues it resolves. Gates:
- **F:** the fast suite.
- **S:** the slow suite, alone.
- **I:** the identity golden file unchanged (from Phase 2 on).
- **B:** Brookhaven's `heimdall status` unchanged (read-only).

Work-dir edits (Brookhaven, High-Energy) are listed for you; Heimdall never makes them.

| Phase | Issues |
| --- | --- |
| 1 Task L's follow-ups, quick fixes | **done** (V190–V194), but I-07's checks by hand |
| 2 The safety net | I-10, I-11, I-12, I-13, I-76, I-77 (part) |
| 3 One dialect | I-20, I-21, I-91 |
| 4 Retirements, record formats | I-25, I-26, I-28, I-29, I-30, I-68, I-105 (drops) |
| 5 Session layer, CLI | I-35, I-36, I-37, I-70, I-71, I-72, I-73, I-100, I-101 |
| 6 Plot model | I-40 (closed: kept), I-41, I-42, I-43, I-44, I-45, I-46, I-47, I-48, I-97, I-99 |
| 7 Package restructure | I-50, I-51, I-52 |
| 8 The stack | I-55 … I-63, I-65, I-66, I-77 (rest), I-88 |
| 9 Roots, cluster images | I-75, I-86 |
| 10 Throughput, provenance | I-95, then I-96, I-98, I-67, I-102 |
| 11 Physics set-ups | I-103 (ep Delphes card, Geant4 module), I-104 (BeAGLE) |
| parked | I-80, I-82 (the Mac), I-83 (the reinstall), I-85 (image downloads), I-87 (a Slurm site; HTCondor and PBS with it), I-81's roadmap and Herwig photoproduction (ideas) |

**Your decisions (2026-10-25):**
- **D1:** drop v2; Brookhaven's `configs/legacy/` stays as history.
- **D2:** `plot.toml` stays the source of a drawing (I-40 closed as kept).
- **D3:** retire `plot_points`; old documents still draw.
- **D4:** delete the yoda backend; mpl may drift from mkhtml.
- **D5:** `[heimdall]` keeps preference switches only (`rerun`, `wait`, `detach`, `plain`, `journal`, `logs`,
  `replot`, `keep`); modes, targets and selections are refused; `no-plot`/`no-stats` are `[run]`'s.
- **D6:** after the Mac.
- **D7:** `editor/` stays as it is.
- **D8, D9:** built.
- **D10:** the doctor row goes into Himinbjorg, published on purpose.
- **D11:** downloads to `<root>/downloads/`.
- **I-08:** cores adapt to the load (0 = the idle CPUs; ROOT compilers from available memory, about 1.3
  GB each).
- **I-11:** the golden file is approved.
- **I-17:** approved. **I-90** went into I-109 (2026-10-27: the user chose to rebuild every reader of the renamed
  tool variables, App_yd2rt too, so its binary no longer stays byte-identical).
- **I-86:** plan inside the image.
- **I-66:** Herwig for MadGraph, plus MG5aMC_PY8.
- **I-70:** `--logs` and `--journal` stay, as shorthands.
- **I-105:** F8 and the stamp are dropped (the deck `template` key went with deck, V212).

## Index

| # | Title | P | Status |
| --- | --- | --- | --- |
| **M0** | **Task L's follow-ups** | | |
| I-07 | Task L: the checks by hand | P1 | open (needs you) |
| I-09 | The plot stage fails for `combine` and for listed points (`KeyError`) | P0 | open |
| **M1** | **The safety net** | | |
| I-10 | A shadow machine root for the tests | P1 | open |
| I-11 | An identity golden file | P1 | held (a new frozen file) |
| I-12 | Baselines before the restructure | P1 | open |
| I-13 | Static checks: ruff, mypy, `make check` | P2 | open |
| **M2** | **One run-TOML dialect** | | |
| I-20 | Drop v2 run TOMLs | P1 | decision (D1) |
| I-21 | v3 as the form and the model | P1 | blocked on I-10, I-11, I-20 |
| **M3** | **Retirements** | | |
| I-25 | Retire the migrations and the guards for retired names | P1 | blocked on I-21 |
| I-26 | One table of retired names | P2 | blocked on I-25 |
| I-28 | Record files with a format version; `heimdall records upgrade` | P2 | open |
| I-29 | Leftover names and stale hints | P3 | open |
| I-30 | Mark unproven toolkits | P3 | open (decided) |
| **M4** | **The session layer** | | |
| I-35 | `RunRequest` and a session module | P1 | blocked on I-25 |
| I-36 | `heimdall plan` | P2 | decision (D9) |
| I-37 | `--json` output | P2 | blocked on I-35 |
| **M5** | **The plot model** | | |
| I-40 | `[plot]` lives in the config; the record keeps facts | P1 | decision (D2) |
| I-41 | Sets as the one grouping; retire `plot_points` | P2 | decision (D3) |
| I-42 | Figure classes as a table, one dispatcher | P2 | open |
| I-43 | Delete the yoda (mkhtml) backend | P2 | decision (D4) |
| I-44 | One HTML index writer | P3 | open |
| I-45 | `heimdall stats` → `heimdall plot --stats-only` | P3 | decision (D9) |
| I-46 | Compare figures: their own stage, drawn once | P2 | open |
| I-47 | Paint's PDF line widths | P3 | open |
| I-48 | Known plot limits | P3 | idea |
| **M6** | **The package restructure** | | |
| I-50 | `runner/` as subpackages by layer | P2 | decision (D8) |
| I-51 | The plugin loader for tool folders only | P2 | blocked on I-50 |
| I-52 | `env/` into `shell/` and `framework/make/` | P3 | blocked on I-50 |
| **M7** | **The stack** | | |
| I-55 | The stack builder as a library | P2 | open |
| I-56 | One stack registry: the recipes | P2 | blocked on I-55 |
| I-57 | Downloads out of `forge/` | P2 | decision (D11) |
| I-58 | Which checkout built `apps/` | P2 | open |
| I-59 | `stack doctor --record` writes into Himinbjorg | P3 | decision (D10) |
| I-60 | Download progress | P3 | open |
| I-61 | A recipe's helper scripts in its digest | P3 | open |
| I-62 | A change of the base marks only what it touches | P3 | open |
| I-63 | Geant4's data through the build's downloader | P3 | open |
| I-65 | A test that CMake on the base ignores `/usr` | P3 | open |
| I-66 | MadGraph: the MG5aMC_PY8 interface, Herwig's paths | P3 | open |
| I-67 | Sherpa's integration over MPI | P3 | idea |
| I-68 | Live-state files keep a reader for their old forms | P2 | open |
| **M8** | **The CLI and its knobs** | | |
| I-70 | One stage selector, one keep flag, one `--plain` | P2 | blocked on I-35 |
| I-71 | Fewer commands for one job | P2 | open (G15 decided) |
| I-72 | `heimdall show` | P3 | open |
| I-73 | Shell completion | P3 | open |
| **M9** | **Roots and tests** | | |
| I-75 | A `WorkDir` value; no root variables, no `os.environ` mutation | P2 | blocked on I-10 |
| I-76 | Tests independent of their order | P2 | open |
| I-77 | Tests a conda-base root skips | P3 | open |
| I-79 | The legacy gates differ by one digit on the conda base | P2 | decision |
| **M10** | **The machine and the repository** | | |
| I-80 | Retire `base = "system"` | P3 | blocked on I-82 (D6) |
| I-81 | `editor/` to its own repository; its roadmap | P3 | decision (D7) |
| I-82 | The Mac on the conda base | P2 | held (the Mac) |
| I-83 | The lab PC's reinstall | P3 | decision |
| **M11** | **Not yet proven** | | |
| I-85 | A real Apptainer image | P2 | held (downloads) |
| I-86 | `[cluster] image` plans outside the image | P2 | decision |
| I-87 | `heimdall cluster` on a real Slurm | P3 | open |
| I-88 | The conda base's phase 3 | P3 | open |
| **M12** | **Held: ask first** | | |
| I-91 | `hep` and `setup.sh` in the frozen fixture | P3 | blocked on I-21 |
| **M13** | **Ideas** | | |
| I-95 | Per-group identity and skip | P3 | idea |
| I-96 | Shared generation for analysis-option sweeps | P3 | idea |
| I-97 | Weight variations as a band | P3 | idea |
| I-98 | Shards beyond Rivet; K from threads | P3 | idea |
| I-99 | `heimdall plot --suggest-data-map` | P3 | idea |
| I-100 | `heimdall run --check`: preflight without events | P3 | idea |
| I-101 | Where a resolved value came from (`--explain KEY`) | P3 | idea |
| I-102 | Products that identify themselves; an index of provenance | P3 | idea |
| I-103 | Physics set-ups to settle | P3 | decision |
| I-104 | A tool's private dependencies (BeAGLE) | P3 | idea (set aside) |
| I-105 | Smaller leftovers | P3 | idea |
| I-110 | A report's look, native statistics, and its data | P2 | in progress (asked 2026-10-27) |

---

## M0 — Task L's follow-ups

### I-07 Task L: the checks by hand
**P1 · verification · open**
- **By hand, on the lab PC** (your 15 minutes):
  - `heimdall run eic/zeus dis_generator_pdf --points 1`, press `d`, close the terminal;
  - `heimdall runs`, then `heimdall watch` (`s`, `y`), then `heimdall runs` again for the verdict;
  - the same from an ssh session.
- The worker's log path and the docs of where a detached worker still ends are done (V191).

### I-09 The plot stage fails for `combine` and for listed points (`KeyError`)
**P0 · bug · open (found by the slow suite, 2026-10-25)**
- **Problem:** two slow tests fail in the plot stage after every point ran:
  - `test_gates_combine.py::test_each_pdf_is_its_seeds_merged_and_drawn_as_one_curve` (`KeyError: 'pdf'`);
  - `test_listed_points.py::test_listed_points_run_and_draw_a_page_per_pdf` (`KeyError: 'pt0ref'`).
- **Where:** `plot.check_figures` → `sweep.points(run, configuration)` → `sweep.kept`, `run.quantities[name]`.
  The `run` there is the plot document (`plotdoc.load`), whose quantities lack the configuration's swept one.
- **Since:** already failing at `fde73d0` (was `4477c17`; V163–V171, plot documents), and at Phase 1's base `5c271a0` (was `29b27ae`); not
  caused by Phase 1. A configuration with `combine` or listed points draws nothing.
- **Done when:** both tests pass, and a drawing of such a configuration from its record works.
- `--plan`'s page count (V195) meets the same `KeyError` on listed points (`eic/baseline`'s
  `generator_polarisation`) and falls back to `plot_points`' count.

## M1 — The safety net

### I-10 A shadow machine root for the tests
**P1 · test · open**
- **Problem:** by default the suite runs with the real `HEIMDALL_MACHINE` (`conftest.py:31`). Your live
  `machine.toml` decides what tests keep (`paths.keep`, `paths.py:144`) and their `[cluster]` defaults
  (`cluster.py:77`). Your `recipes.toml` and `toolkits/` decide `package_states`. Only `HEIMDALL_RUNS` and
  `HEIMDALL_WORKDIRS` keep tests off the registry and the work-dir map, and a test once matched a live run.
- **Fix:**
  - `conftest` builds `$HEIMDALL_FORGE/scratch/machine/`:
    - the real `stack/`, `base/`, `apps/` and `forge/downloads/` linked in;
    - the tests' own empty `machine.toml` and `recipes.toml`;
    - an empty `runs/` and `workdirs.toml`.
  - It sets `HEIMDALL_MACHINE` there.
  - The session guard checks `stack/.stamps/` and `apps/` are unchanged at the end, as it does for the
    fixtures.
- **Done when:** the suites pass as before, and no test reads or writes `~/Himinbjorg`'s own files.

### I-11 An identity golden file
**P1 · test · held (a new frozen file needs your yes)**
- **Fix:** `tests/golden/identity_parts.json`: every fixture point's `record.identity_parts`, with binaries'
  sha256 masked. Written once, under I-10's shadow root, and compared by a test. Every refactor (I-21,
  I-35, I-50, I-55) must leave it unchanged.

### I-12 Baselines before the restructure
**P1 · process · open**
- The fast and slow suites' results; `heimdall status` of every Brookhaven config (read-only, as gate
  B); a local tag `pre-restructure`.

### I-13 Static checks: ruff, mypy, `make check`
**P2 · tooling · open**
- **Problem:** no `pyproject.toml`, ruff or mypy. A shadowed constant (I-15) and duplicated helpers go
  unseen. CI is one manual, hours-long stack build (`.github/workflows/stack.yml`).
- **Fix:** `pyproject.toml` (tool config only). ruff report-only first (F, B, redefinitions), then
  enforcing. mypy on the new modules. `make check` = ruff + the import layers + the fast suite.

## M2 — One run-TOML dialect

### I-20 Drop v2 run TOMLs
**P1 · design · decision (D1)**
- **Recommended:** v3 only. The 11 fixture configs migrated once. For Brookhaven's `configs/legacy/`
  (D1a), convert them if they are still run, else leave them unreadable as history. A v2→v3 converter
  is kept outside the package for a while (D1b).

### I-21 v3 as the form and the model
**P1 · refactor · blocked on I-10, I-11, I-20**
- **Problem:** v3 is translated into v2 tables (`v3.translate`), and the schema and the model use v2's
  names. The rename table is written nine times: `v3.py:42-47`, `v3.py:376-378`, `schema.py:58-66`,
  `schema.py:271/285`, `migrate.py:436-438`, `docs.py:80-87`, `cli.py:946`, `house.py:162-175`. There are two
  JSON schemas, and messages are translated back (`cli.py:408`, `config.py:1243`). Every fixture is v2;
  the real study writes v3.
- **Fix:**
  1. `heimdall migrate --v3` dry run over the fixtures and `configs/legacy/`; settle what cannot be
     expressed.
  2. Fixtures to v3, with gate I-11 unchanged.
  3. The model in v3's names, with `identity_parts` mapping fields to the frozen JSON keys.
  4. Delete `v3.py`, the v2 branches, `run.schema.json` (v2) and every rename table; the schema in v3's
     names.
- **Docs pass:** 04 entirely, 02's examples.

## M3 — Retirements

### I-25 Retire the migrations and the guards for retired names
**P1 · cleanup · blocked on I-21 (decided by you 2026-10-15: audit 4's G13, G14, G15, G3, G5, G18, G16)**
- **First:** `heimdall migrate --layout` dry runs over Brookhaven and High-Energy (expected: nothing
  to move).
- **Delete:**
  - `migrate.py` (1,046 lines);
  - `main()`'s legacy-layout probes and `check_retired()` (`cli.py:2256-2270`);
  - `paths.RETIRED` and `HEKIT_*` (`paths.py:49-60`, `heimdall_env.sh:24-28`, `conftest.py:58`); `{repo}`
    (`tools.py:307`); `[tool] formerly`; the export keys (`tools.EXPORT`);
  - `[config].master` and its overlay; `framework/tools/plotmerge/`;
  - `recipes/machine.py adopt`, its messages (`gjallarhorn.sh:30-32`, `launch.sh:48-50`) and its
    `.gitignore` lines; `recipes/build_by_hand.txt`;
  - the shell helpers `quit`, `heimdall_status`, `heimdall_stash`, `heimdall_forge` and `heimdall_stack`;
  - the parser's lenient `strict=False` mode.

### I-26 One table of retired names
**P2 · design · blocked on I-25**
- `retired.py`: `{old: (new, since)}`, which the schema check, the CLI and the shell's refusals read,
  emptied on a schedule. It replaces ad-hoc refusals (39 "heimdall migrate" hints today). A v1
  (hekit) file is refused by name here (intent CF1).

### I-28 Record files with a format version; `heimdall records upgrade`
**P2 · design · open**
- **Problem:** `points.json`, `provenance.json`, `identity.json` and `plot.toml` carry no format version.
  Layouts are recognised by heuristics (`plotdoc.needs_upgrade`, `migrate.layout_moves`, three probes on
  every command).
- **Fix:** `format = N` in each, a `FORMAT` file per record folder, and one `heimdall records upgrade`
  (dry run first) that also does today's `migrate --snapshot` and `--plot-docs` jobs.

### I-29 Leftover names and stale hints
**P3 · cleanup · open (audit 4's G1, G9, G17)**
- Dead names: `plot.BACKENDS` (`plot.py:48`), `layout.TILED`, `tools.ENV`
  (`tools.py:40`), `paths.forge_dir` (tests only).
- Hints that name `heimdall plot FILE` instead of `overlay`. The wrappers `plot.objects_of`, `raws_of`,
  `_sha` and `base_of` inlined. `{repo}` → `{heimdall}` in the recipes.

### I-30 Mark unproven toolkits
**P3 · stack · open (decided: audit 4 G7)**
- `proven = ["<date> <platform> <base>", …]` in a toolkit file, added after a recorded build;
  `heimdall stack list --toolkits` shows "unproven" for the others. Add `@loops` once proven (V189).

## M4 — The session layer

### I-35 `RunRequest` and a session module
**P1 · refactor · blocked on I-25**
- **Problem:** `cli.py` (2,360 lines) holds the run orchestration: `build_plans`, `_numbered`,
  `run_one`, two sweep executors (`_runs` and `_pipelined`, each with its own error handling), signals
  and the worker. It reads arguments through 62 `getattr(args, …)` calls, and six call sites fabricate
  an `argparse.Namespace` (`cli.py:422`, `1173`, `1465`, `1564`, `1774`, `1861`).
- **Fix:** a `RunRequest` dataclass, and `session.plan(request)` and `session.run(planned)`, with **one**
  sweep executor (sequential is the pipeline with a gate at each run's end). `cluster` and `check` take
  a request. `cli` parses, dispatches and prints.

### I-36 `heimdall plan`
**P2 · CLI · decision (D9)**
- `heimdall plan CONFIG [CFG] [--why | --config | --card TAG] [--points] [--json]`, replacing
  `run --plan/--why/--show-config/--card`. `heimdall check` is `plan` of everything, quiet. The old
  spellings are refused with the new ones for a release.

### I-37 `--json` output
**P2 · feature · blocked on I-35 (intent U6)**
- On `plan`, `status`, `runs`, `tools` and `stack status`, from one renderer: for scripts and agents.

## M5 — The plot model

### I-40 `[plot]` lives in the config; the record keeps facts
**P1 · design · decision (D2)**
- **Problem:** a run copies `[plot]`/`[stats]` into `results/<run>/plot.toml`, and drawing reads that
  copy, so an edit of the run TOML does not reach the pages. Hence `--style-sync`, `--replot`, `--across
  --style-sync`, `migrate --plot-docs` and a "differs" note (`cli.py:1235-1440`).
- **Recommended:** the run writes `results/<run>/members.toml` (facts: source, axes, members, versioned).
  Drawing reads `[plot]`/`[stats]` from the config (the snapshot's, for a record); `--plot FILE`
  overrides. An existing hand-edited `[plot]` is kept as `plot.local.toml`. `--style-sync` and its kin go.

### I-41 Sets as the one grouping; retire `plot_points`
**P2 · design · decision (D3)**
- `plot_points`, sets (`pages`/`curves`), `totality` (which reads `plot_points`) and the figure classes
  overlap (`sweep.py:328-364`, `config.py:1188-1205`). `[cfgs.x] plot = [...]` and `totality` carry what
  `plot_points` said, and a file that has it is refused with the set that says the same.

### I-42 Figure classes as a table, one dispatcher
**P2 · refactor · open (audit 2 H5/H9; task K K3/K5)**
- Nine classes are dispatched by their own `kind ==` loops (`plot.py:495`, `502`, `591`, `696`, `882`,
  `1166`, `1554`, `1830`), and `config.check_plot` hand-codes their rules. Give them a
  `[figure_class.<c>]` table (needs, forbids, objects) in the schema, and one dispatcher.
- Also merge `_pages`' near-duplicate defined and overlay loops (audit 2 H6), and add one
  `_cached(target, stamp, digest, make)` helper for the five stamp-and-rebuild sites (H7).

### I-43 Delete the yoda (mkhtml) backend
**P2 · cleanup · decision (D4)**
- **Problem:** "frozen" (`framework/plot/yoda/backend.py:3`), yet the mpl backend loads it for its
  transforms (`framework/plot/mpl/backend.py:46-52`, `:78`, `:122`). Nobody draws with it; Brookhaven
  uses `["mpl", "root"]`.
- **Fix:** move the transforms into the mpl backend, then delete the yoda backend, `backend.toml` and
  `"both"`. Paint stays the page engine (ranges, voids, statistics); every backend draws from its JSON.
- Also known: the mpl-vs-mkhtml pixel test fails alone too (ratio-pad antialiasing since the conda
  base's matplotlib; task K's K4). It goes with the backend, or is relaxed.

### I-44 One HTML index writer
**P3 · cleanup · open**
- `plot.write_index` (`:1484`), `plot.write_sets_index` (`:1724`) and `viewer.page` (a report's `index.html`
  since the deck's retirement, V212; the best of them). Use the viewer for the plots too (the reporter plan's "later").

### I-45 `heimdall stats` → `heimdall plot --stats-only`
**P3 · CLI · decision (D9)**
- One command for drawing from the record; `stats` refused with its new spelling for a release.

### I-46 Compare figures: their own stage, drawn once
**P2 · design · open (task K's K6; audit 2 H2)**
- A compare figure is drawn as a side effect of each of its configurations' plot stages, waiting for
  whoever finishes last, and up to N times under `sweep_runs`. It was not moved onto plot documents
  (task K). Give it its own step, with the runs-together documents (`--across`).

### I-47 Paint's PDF line widths
**P3 · bug · open**
- Paint's PDF line widths are about twice too thick (noted in task logs since audit 2; not measured since).

### I-48 Known plot limits
**P3 · idea (audit 2 H15)**
- Heat maps are Paint's only (no mpl). A scan's x must be numeric (no PDF-set scans). A sheet has no
  shared y title or legend.

### I-110 A report's look, native statistics, and its data
**P2 · feature · in progress (asked 2026-10-27)**
- `reports/` a run's output in the work template; one look for `report.tex` (fonts, sizes, weights, colours,
  spacing, the running header); a set's sub-header; code highlighted; the statistics and bar graphs typeset in the
  report, their data beside them; Brookhaven's `zeus_report.toml`. The plan and its map:
  [report_look.md](report_look.md).

## M6 — The package restructure

### I-50 `runner/` as subpackages by layer
**P2 · refactor · decision (D8)**
- **Problem:** the flat package's god modules: `cli.py` (2,360), `plot.py` (2,001), `tools.py` (1,724:
  folders, placeholders, a subprocess merge, the stack's package states, run-folder layout, planning,
  cards, a presentation helper), `config.py` (1,459). There are also misplaced pieces: the keep policy
  and heimdall.toml's schema in `paths.py`, the plot vocabulary in `sweep.py`, `house.py` as a grab bag. The
  draw ↔ statistics ↔ statistic-figure cycle blocked task K's split.
- **Fix:** `core/`, `stack/`, `config/`, `plan/`, `run/`, `draw/`, `session/`, `machine/` and `cli/`, each a
  layer, and `test_imports.py` by package. `runner.errors`, `runner.results` and `heimdallkit` keep their
  import paths. Moved one module at a time, with the fast suite after each.

### I-51 The plugin loader for tool folders only
**P2 · refactor · blocked on I-50**
- `bars.py`, `derive.py`, `layout.py`, the backends, `build_stack.py` and `env/stack.py` are loaded as
  "plugins" (`plot.py:1744`, `report._layout`, `config.py:1289`, `tools.py:515`). The premise was "the
  runner stays standard library", but `tomli_w` is imported in five modules already. Import them
  normally, with matplotlib and YODA lazily, and pin the real dependency set in a test.

### I-52 `env/` into `shell/` and `framework/make/`
**P3 · layout · blocked on I-50**
- `env/` mixes the bash environment, the flag probe, the stack registry and a generated list.
  `heimdall_env.sh` goes to `shell/`; `rules.mk`, `work.mk` and `flags.sh` to `framework/make/`; the template's
  `include` path follows. `recipes/pth.py` puts only `runner` and `heimdallkit` on the path, not
  `framework/`'s generic names.

## M7 — The stack

### I-55 The stack builder as a library
**P2 · refactor · open**
- The runner loads `recipes/build_stack.py` (1,760 lines) as a plugin and catches its `SystemExit`
  (`tools.py:423-433`, `doctor.py:30`, `bifrost.py:37`, `:210`). Make it a `stack` package with exceptions
  (still standard library only, runnable before any environment), and keep `recipes/build_stack.py` as
  a thin CLI.
- **Gate:** `--dry-run` byte-identical for `@primary`, `@core-conda` and `packages=all`.

### I-56 One stack registry: the recipes
**P2 · refactor · blocked on I-55**
- Four registries say what a package is: `standard.toml`, `env/stack.toml` with `stack.py`,
  `env/packages.sh` and `stack/.stamps/folders`.
- `.stamps/folders` already lists every installed folder: all 18 in `~/Himinbjorg` (since V123).
- Recipes gain `flags` and `version`; `heimdall_env.sh` reads `.stamps/folders` alone (diff `PATH` and
  `LD_LIBRARY_PATH`: the order becomes build order). `env/stack.toml`, `stack.py`, `packages.sh` and
  `make registry` go.

### I-57 Downloads out of `forge/`
**P2 · machine root · decision (D11)**
- CLAUDE.md says the machine root's `forge/` may be emptied by hand. That loses
  `forge/downloads/` (3.3 GB), which rebuilds and I-14 need.
- **Recommended:** `~/Himinbjorg/downloads/`, the build reading the old place for a release, and the move
  a rename, done with your yes.

### I-58 Which checkout built `apps/`
**P2 · machine root · open**
- Several checkouts may share a root, but `apps/` is built from one checkout's `src/` and nothing
  records which. Another checkout's build replaces them, and every point that uses them reruns.
- `heimdall build --framework` writes `apps/.source` (the checkout, its revision, a digest of `src/`);
  `run` and `stack doctor` warn on a mismatch.

### I-59 `stack doctor --record` writes into Himinbjorg
**P3 · machine root · decision (D10)**
- It writes this machine's row into the git checkout (`doctor.py:152-155`,
  `recipes/support/linux-pp-exphep.toml`). Write `~/Himinbjorg/support.toml`, and `--publish` copies it
  into `recipes/support/`.

### I-60 Download progress
**P3 · feature · open (stack-build note N1)**
- `download` copies in 1 MB chunks with nothing shown (`build_stack.py:1089`). Show bytes so far of
  `Content-Length`, the rate and an ETA on the live line; one line per file when plain; the same for
  pixi's.

### I-61 A recipe's helper scripts in its digest
**P3 · stack · open (N6)**
- A recipe's patch is hashed (`patch_sha256`, `build_stack.py:738`), but the helper scripts its
  `pre`/`post` run (`recipes/helpers/h5cc_plain.py`) are not, so changing one rebuilds nothing.
- Also: the yoda recipe should check `{dir_hdf5}/bin/plain-h5cc` exists first.

### I-62 A change of the base marks only what it touches
**P3 · stack · open (N13)**
- `base_hash` covers every base library (`build_stack.py:621`), so OCaml's change marked ROOT and the
  rest as changed. Instead, each package's digest takes the compilers and runtime, plus the base
  libraries it builds against.

### I-63 Geant4's data through the build's downloader
**P3 · stack · open (N17)**
- `geant4_data = ON` has CMake fetch about 2 GB during the build, all or nothing; a truncated transfer
  recompiles Geant4 (about 20 min). Fetch the datasets with `build_stack`'s downloader (resumed,
  checked, kept), and point CMake at them.

### I-65 A test that CMake on the base ignores `/usr`
**P3 · test · open (N4)**
- The fix exists (`BASE_CMAKE`, empty build folders), but no test checks it.

### I-66 MadGraph: the MG5aMC_PY8 interface, Herwig's paths
**P3 · stack · open (N21)**
- MadGraph 3.8's showers through `main164`, and Herwig's paths in MadGraph's options, are not done.

### I-67 Sherpa's integration over MPI
**P3 · idea · open**
- Sherpa is built with MPI (OpenMPI 5.0.11, `@loops`). The prepare step (the integration,
  `framework/tools/sherpa/prepare.py`) still runs one process. Running it as `mpirun -n N` (a `[tools.sherpa]`
  option, never in the identity) would speed up the long integrations; event generation stays seed
  replicas with `combine`.

### I-68 Live-state files keep a reader for their old forms
**P2 · machine root · open**
- `runs/*.json`, `workdirs.toml` and `stack/.stamps/` are read by whichever checkout or worker runs
  next. `runs.VERSION` exists; `workdirs.toml` and `.stamps/` carry none.
- Give `workdirs.toml` a `format` key (comments kept). Every change keeps a reader for the old form, and
  a live file is backed up beside itself before a rewrite.

## M8 — The CLI and its knobs

### I-70 One stage selector, one keep flag, one `--plain`
**P2 · CLI · blocked on I-35**
- **Stages:** `--only`, `--stages`, `--no-plot`, `--no-stats`, `[run].plot` and `[run].stats` interleave
  (`cli.py:574-588`, `1035-1062`, `1139-1145`). Make `--stages` the selector, with `--no-plot` an alias.
- **Keep:** `--keep`, `--logs` and `--journal` overlap, besides heimdall.toml's and machine.toml's
  `[run] keep`. Make `--keep WORDS` the one flag.
- **Plain:** `--plain` is both global and per command; make it global only.

### I-71 Fewer commands for one job
**P2 · CLI · open (audit 4 G15 decided)**
- `heimdall doctor` and `status --stack` → `heimdall stack doctor` and `stack status` (decided).
- `heimdall make` → `heimdall build TARGET`; `heimdall image` → `heimdall stack image`.
- `main()` dispatches from a table, not an if-chain.

### I-72 `heimdall show`
**P3 · feature · open (intent U2)**
- `heimdall show RECORD[/POINT]`: provenance, identity parts, products, σ, counts, and the logs' tail.
  Today only `--why` reads the record.

### I-73 Shell completion
**P3 · feature · open (intent U5)**
- `heimdall completion bash`: commands, configs, configurations and point tags.

## M9 — Roots and tests

### I-75 A `WorkDir` value; no root variables, no `os.environ` mutation
**P2 · refactor · blocked on I-10**
- Eight root variables, and a record's configs root passed by mutating `os.environ`
  (`paths.configs_at`, `cli.opened`), plus a module-global keep set.
- A `WorkDir` resolved once and passed down. `HEIMDALL_RESULTS`, `HEIMDALL_RECORDS`, `HEIMDALL_CACHE`, `HEIMDALL_REPORTS`
  and `HEIMDALL_CONFIGS` go; `HEIMDALL_RUNS` and `HEIMDALL_WORKDIRS` go once I-10 is in.

### I-76 Tests independent of their order
**P2 · test · open**
- Every test shares one scratch work dir whose records accumulate (`conftest.py:56-66`). Give a test
  that writes its own copy (`build/` linked to the session's), so order stops mattering and
  `pytest -n` becomes possible.

### I-77 Tests a conda-base root skips
**P3 · test · open (N3, N20)**
- Seven shell tests (`test_setup.py`, `test_shellrc.py`) know only a venv, so on the conda base they
  never run.
- `test_v3`'s editor-schema test needs `jsonschema`, which the base lacks.
- `test_the_old_way_is_apt_and_a_venv` fails on a conda root: it asserts "pixi" appears nowhere, and
  the venv's path holds it. It goes with I-80, or asserts on the script's pixi commands.

### I-79 The legacy gates differ by one digit on the conda base
**P2 · verification · decision (first seen 2026-10-22)**
- `test_gates_p1.py::test_the_legacy_reference_is_reproduced_byte_for_byte[MSTW|NNLO]` fail: one digit of the
  YODA (byte 323) differs from `tests/reference/`. It fails before task H (`fb3eed8`, was `4bf2e06`) too, so it comes from the
  rebuilt stack's Pythia, Rivet or LHAPDF, not the runner. The references are never regenerated.
- **Yours to judge:** accept the stack's digit (the gate then compares with that one tolerance, written down),
  or find which package moved it (a rebuild against the old release, with your yes).

## M10 — The machine and the repository

### I-80 Retire `base = "system"`
**P3 · cleanup · blocked on I-82 (D6)**
- The venv/apt/Homebrew path is carried beside the conda base:
  - `gjallarhorn.sh:51-57` and `heimdall_env.sh`'s `deactivate` dance;
  - `framework/bin/heimdall:13`, `launch.sh:59-71`, `cli._system_python`;
  - `bifrost`'s pip branch, `build_stack.system()`, and `platforms/mac/{Brewfile,system.toml}`.
- Delete it once the Mac is on the conda base.

### I-81 `editor/` to its own repository; its roadmap
**P3 · layout · decision (D7; it came in from High-Energy on 2026-10-22, V161)**
- 8.9 MB of VS Code assets, including an icon bank of third-party Vecteezy SVGs. Check their licence
  before any public repository.
- **Recommended:** move it to its own repository, or keep it here and move the icon bank out.
- **What is left of its roadmap** (from `editor/Report.md`, removed; already done: `.cmnd`'s value,
  namespace and disabled-line scopes, the theme's dark sibling and its 16 ANSI colours, the `heimdall-icons`
  theme):
  - `cmnd-syntax`:
    - a PDG-id subscope;
    - an injection so `pythia.readString("…")` strings in C++ are highlighted;
    - snippets for the ~30 common keys;
    - version 0.1.0.
  - `heimdall-contrast-theme`: ROOT/Cling tokens (`gROOT`, `gStyle`, `gPad`, `R__LOAD_LIBRARY`); the README's
    palette table generated from the palette; the unused `fg4` slot and duplicated diff colours cut.
  - New packages, ranked:
    - `pythia-hover`: Pythia's settings from its manual XML, as hovers and completion in `.cmnd`;
    - `hep-snippets`: Pythia, ROOT, Rivet and HepMC boilerplate;
    - `hep-tasks`: VS Code tasks and launch configs over `heimdall build`/`run`;
    - `hep-statusbar`: the open run TOML's events, energies and seed;
    - `yoda-syntax`.

### I-82 The Mac on the conda base
**P2 · machine · held (the Mac)**
- Tasks A–E (conda base, `heimdall`/`bifrost`/`recognise`, own recipes and switches, minimal run output,
  images) are unproven on macOS.
- The first Mac build's 18 notes (2026-10-12) are applied: `mac.toml`'s ThePEG/Herwig/Whizard fixes,
  archive checks, the bash-only environment, the refusal of a direct `build_stack.py` run.
- Rebuild there, then run the suites and record the support row (I-59).

### I-83 The lab PC's reinstall
**P3 · machine · decision**
- It was postponed on 2026-10-15 (the USB would not boot: TPM/encryption), and the stack was rebuilt in
  place on the conda base instead. Confirm whether a reinstall is still wanted. The runbook is
  `docs/framework/` (P0–P4); the backups are on the Ventoy USB (`pre-wipe/`).

## M11 — Not yet proven

### I-85 A real Apptainer image
**P2 · verification · held (downloads)**
- `heimdall image build packages=@core-conda` has been tested with a fake runtime only. `apptainer` is
  now on this machine (`/usr/bin/apptainer`). Name the downloads before building.

### I-86 `[cluster] image` plans outside the image
**P2 · design · decision (audit 4 G6)**
- The jobs run in the image, but `heimdall cluster` plans on the login node, which then needs a stack,
  and the image has no `sbatch`.
- Either plan inside the image and write a `submit.sh` that the host runs (chained job ids), or bind the
  site's Slurm client into the image.

### I-87 `heimdall cluster` on a real Slurm
**P3 · verification · open**
- Only an emulated Slurm so far. Run `--dry-run` first on a real site. HTCondor and PBS are later.

### I-88 The conda base's phase 3
**P3 · verification · open (`docs/conda/03_Plan.md`)**
- The physics against the old stack; a tracked multi-platform lock; a bootstrap for clusters with
  Python < 3.11; ROOT's and Geant4's GL viewers opened once (`libglvnd` with the OS's driver).

## M12 — Held: ask first

### I-91 `hep` and `setup.sh` in the frozen fixture
**P3 · rename · blocked on I-21**
- The fixture's `Makefile` error names `setup.sh`; its configs' comments and
  `modules/Decay/README.md` say `hep run`. `tests/reference/v2_configs/` mirrors the configs. Change them
  with I-21's migration of the fixtures.

## M13 — Ideas

### I-95 Per-group identity and skip
**P3 · idea (intent T1)**
- A point reruns only the groups whose identity changed, when the earlier groups' products are
  complete. Measured: changing yd2rt's `select` reran a 16.1 s point instead of 0.2 s.

### I-96 Shared generation for analysis-option sweeps
**P3 · idea (intent T2; needs I-95)**
- Points with one generator identity share one generation, and Rivet runs every variant in one pass
  (`-a photo_eic:R=0.4 -a photo_eic:R=0.7`).

### I-97 Weight variations as a band
**P3 · idea (intent T4)**
- Rivet's `/x[MUR2_MUF2]` variations (Sherpa on the fly, Pythia's UncertaintyBands) drawn as an envelope
  instead of dropped. Scale and PDF uncertainty without extra generations.

### I-98 Shards beyond Rivet; K from threads
**P3 · idea (intent T5)**
- Shards on other folders (a module program with a merge tool), and K chosen from `threads`
  automatically.
- Also unmeasured: the parallel-points timing (V36).

### I-99 `heimdall plot --suggest-data-map`
**P3 · idea (intent U1)**
- Print `[plot.data.map]` lines matched by name, for you to check and paste. The map stays explicit.

### I-100 `heimdall run --check`: preflight without events
**P3 · idea (intent U8)**
- Each tool's cheap preflight: Pythia's `init()` on the point card, `rivet --list-analyses`, a card
  parse. It must never open a FIFO.

### I-101 Where a resolved value came from (`--explain KEY`)
**P3 · idea (intent CF3)**
- The layer that set a value: the file, an import, a configuration, `--set`; for a style key, base.toml,
  the style files, `[plot.style]` or the figure.

### I-102 Products that identify themselves; an index of provenance
**P3 · idea (intent P1, P2)**
- The point, its identity, the git revision and the config written into the YODA (annotations on
  `/_EVTCOUNT`) and the ROOT file (a TNamed).
- Later, a SQLite index over the provenance files ("every point with pdf = NNPDF23lo").

### I-103 Physics set-ups to settle
**P3 · decision (intent §5)**
- An ep Delphes card: the ATLAS card reconstructs a jet in 0.9 % of events at these energies.
- Herwig photoproduction: `dis_ep.herwig.in` is NC DIS, a chain check only.
- A Geant4 simulation module: Geant4 builds, but no program is written.

### I-104 A tool's private dependencies (BeAGLE)
**P3 · idea (task G, set aside by you 2026-10-15)**
- A recipe's `private = [...]`, each built into `stack/<dependent>/private/<name>/`, off the shell's
  paths, rpath-linked, hashed into the dependent's digest. `scope = "private"` for a recipe built only
  that way. A tool folder's `{package}` placeholder, and a prepend form of `[command] env`. For
  BeAGLE: DPMJet 3 and Pythia (linked to LHAPDF, for EPS09), RAPGAP 3.302's static libraries,
  `$BEAGLESYS`, FLUKA's `nuclear.bin` in the run folder, and its text output converted (eic-smear, or to
  HepMC) for Rivet. Check BeAGLE's README before writing the recipe.

### I-105 Smaller leftovers
**P3 · idea**
- `heimdall migrate --stamp`: the stack's versions into `[file.meta].versions`, if wanted.
- HTCondor and PBS for `heimdall cluster`.
- "F8 `--more`": named in older plans with no description anywhere. Confirm what it was, or drop it.
