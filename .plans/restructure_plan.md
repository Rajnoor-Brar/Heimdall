# Plan: resolve every issue in ISSUES.md (79 issues, M0–M13)

Approved 2026-10-25. Moved here from the plan-mode file on 2026-10-26; its pending work is [ISSUES.md](ISSUES.md)'s, and its progress the Plan section there.

## Context

ISSUES.md (commit `5c271a0`, was `29b27ae`) holds all of Heimdall's pending work: Task L's follow-ups, the restructure
the 2026-10-23 audit proposed, stack and machine-root items, unproven targets, and ideas. You asked for
a plan that resolves all of them, asking where your intent or the file's wording was uncertain.
Six rounds of questions settled that.

Each issue ends one of three ways:
- **built:** code, tests, docs, a V-row, a commit, and the issue deleted;
- **closed by decision:** deleted, with the reason in the phase's V-row;
- **parked:** kept in ISSUES.md as `held`, waiting on something only you have (the Mac, a Slurm site,
  image downloads, the reinstall).

## Decisions taken (your answers, 2026-10-25)

| Issue | Decision |
| --- | --- |
| I-04 `[heimdall]` | **Keep, narrowed to preference switches:**<br>• allowed: `rerun`, `wait`, `detach`, `plain`, `journal`, `logs`, `replot`, and `keep = [...]`;<br>• refused, each with its reason: modes (`plan`/`dry-run`, `why`, `show-config`, cluster `status`/`cancel`/`dry-run`, plot `plan`/`style-sync`/`across`, `status --stack`), targets (`card`, `pid`, `file`, plot FILE) and selections (`points`, `sets`, `stages`, `only`);<br>• `no-plot`/`no-stats` point to `[run].plot`/`[run].stats = false`;<br>• precedence written down: the command line, then `[heimdall.<cmd>]`, then `[heimdall]`, then `[run]`. |
| I-08 + I-64 | **The build adapts to the load:**<br>• `settings.toml` back to `cores = 0`, `root_cores = 0`, and nothing goes into `machine.toml`;<br>• `0` now means: compilers = the CPUs not busy (load average), and ROOT/Rivet compilers = available memory (MemAvailable, not total) ÷ about 1.3 GB (12 work on an idle 16 GB). |
| I-20 | Drop v2. The fixtures migrate to v3; Brookhaven's `configs/legacy/` stays as unreadable history. |
| I-40 | **Kept:** `results/<run>/plot.toml` stays the source of a drawing. Closed. |
| I-41 | Retire `plot_points`. Old plot documents (16 have it in `[axes]`) keep drawing (it is read as `totality`'s page axes); configs refuse it. |
| I-43 | Delete the yoda backend; mpl may drift from mkhtml. |
| I-50, I-36, I-45, I-71 | All built: subpackages, `heimdall plan`, `plot --stats-only`, and `make`/`image`/`doctor`/`status --stack` folded. |
| I-70 | `--logs` and `--journal` stay, as shorthands for `--keep logs`/`--keep journal`. Only the stage selector and `--plain` are unified. |
| I-81 | `editor/` stays as it is. Its roadmap stays an idea (not built here). |
| I-11 | The golden file is written (approved). |
| I-17, I-57, I-90 | Approved: delete the checkout's `forge/` and `.setup/`; rename Himinbjorg's downloads; rebuild for the `hep` strings. |
| Work dirs | **You edit Brookhaven and High-Energy.** Each phase lists the exact edits; I never touch them. |
| I-83 | The reinstall was postponed and is still wanted: parked. |
| I-86 | Plan inside the image; write `submit.sh`, which the host runs. |
| I-59 | `stack doctor --record` writes `~/Himinbjorg/support.toml`; `--publish` copies it into `recipes/support/`. |
| I-66 | Yes: Herwig as MadGraph's shower (its paths in MadGraph's options), plus MG5aMC_PY8. |
| Ideas | Built: throughput (I-95, I-96, I-98, I-67), plots (I-97, I-99, I-48), inspection (I-100, I-101, I-102). Outside this plan: the editor roadmap. |
| I-103, I-104 | Built: an ep Delphes card, a Geant4 module, BeAGLE. Herwig photoproduction stays an idea. |
| I-105 | Following my recommendation: build the deck `template` key; drop "F8 `--more`" and the stack-version stamp; HTCondor and PBS go with I-87 (parked, since there is no site to test on). |
| Docs | Updated with each phase (`make docs` and `test_docs.py` green throughout). |
| Pace | **Phase by phase:** each phase is built, committed and reported, then I wait for your word. |

## How every phase runs

- **Order** is my recommendation; any phase can wait. Within a phase, one commit per coherent change,
  by named paths, ending with the attribution line. Each finished step gets its V-row in
  `docs/07_Record.md` (the next is V190). In the same commit, its issue is deleted from ISSUES.md.
- **Gates**, run at a phase's end unless said otherwise:
  - **F:** the fast suite, `taskset -c 0-5 nice -n 10 python -m pytest -q -m "not slow"`, with the
    environment loaded.
  - **S:** the slow suite, alone, for phases that touch execution or drawing.
  - **I:** the golden file unchanged (from Phase 2 on).
  - **B:** `heimdall status` of each Brookhaven config, read-only, the same as Phase 2's snapshot.
- **Ask first,** as CLAUDE.md says:
  - any download (file, source, size);
  - any rebuilt `App_*`/module/Rivet plugin not approved above;
  - any write into Himinbjorg beyond the approved rename;
  - every work-dir edit (handed to you).
- **Hard stops:** a failed test is reported, never restored on its own. A gate I failure stops the
  phase.

## Phase 1 — Task L's follow-ups, and quick fixes (S)

- **I-02:** `runs.prune` (`framework/runner/runs.py:173`) deletes `path.with_suffix(".log")`; reading
  skips an entry whose `id` does not match `new_id()`'s shape. Test: `id = "../x"` deletes nothing.
- **I-03:** `runs.entries(mine=True)` filters by `uid`. `house.runs_listing`, `cli.cmd_watch`'s last-run
  hint and `cli.cmd_stop`'s cluster lookup use it; `prune` touches only your own entries. Test: a
  foreign-uid entry is invisible.
- **I-04:**
  - in `cli.py`, an allow-list in `_options()`/`heimdall_flags()` (the `FLAGGED` block, `cli.py:1971`),
    and a refusal per class (mode, target, selection) saying why;
  - `no-plot`/`no-stats` refused with `[run].plot`/`[run].stats` as the hint;
  - `tests/runner/test_flags.py` extended; docs 04 §3 and 05 (the precedence).
- **I-07:** the worker is told its real log path (`runs.log_file` → `runs.spawn` → the greeting,
  `cli.py:653`). Then the slow suite, alone, on Task L's commits. Then **your 15 minutes at the lab
  PC** (detach with `d`, close the terminal, `runs`/`watch`/`stop`, the same over ssh). The cases where
  a worker still dies go into docs 02 §2.
- **I-08 + I-64:**
  - `recipes/build_stack.py` (`ram_kb`, `:573`; the `cores`/`root_cores` rule in `context`, `:658`):
    available memory from `/proc/meminfo` (macOS: total, as now) and `os.getloadavg()`;
  - `git checkout recipes/settings.toml`, its comments rewritten to say what 0 means now;
  - tests in `tests/runner/test_stack_build.py`, with meminfo and load injected.
- **I-14:** `python3 recipes/build_stack.py --sha256` over `~/Himinbjorg/forge/downloads/` (read-only),
  with the lines added to `recipes/toolkits/standard.toml`. The digest excludes `sha256`
  (`build_stack.digest`, `:725`), so nothing is marked changed. A missing one is a warning in
  `--check-urls` and `stack doctor`.
- **I-15:** `config.OWN` (`:166`, `:858`), `runs._namespace` → `events.namespace`, and the `render` form
  (`quantities.py:234`).
- **I-16:** control characters refused in `config.check_cluster`.
- **I-17:** after `find ~/Himinbjorg -lname '/home/rajnoor/Github/Heimdall/*'` finds nothing, `rm -rf` the
  checkout's `forge/` and `.setup/` (untracked).
- **Gates:** F, S.

## Phase 2 — The safety net (M)

- **I-10:** `tests/conftest.py` builds `$HEP_FORGE/scratch/machine/`:
  - links to the real `stack/`, `base/`, `apps/` and `forge/downloads/`;
  - the tests' own empty `machine.toml` and `recipes.toml`, and an empty `runs/` and `workdirs.toml`;
  - `HEP_MACHINE` set to it (`test_keep.py` and `test_cluster.py` write the shadow's `machine.toml`);
  - the session guard (`the_fixtures_are_left_alone`) also hashes `stack/.stamps/` and `apps/`.
- **I-11:** `tests/golden/identity_parts.json`, written once under the shadow root:
  - `record.identity_parts` of every fixture configuration's points, with sha256 values masked;
  - `tests/runner/test_identity_golden.py` compares against it.
- **I-12:** F and S baselines, and Brookhaven's `heimdall status` saved for gate B, both into
  ISSUES.md's Phase 2 note; `git tag pre-restructure` (local).
- **I-13:** `pyproject.toml` (ruff F, B, redefinitions; report-only, the findings fixed or listed);
  `make check` = ruff + `test_imports.py` + F.
- **I-76:** a `work` fixture: its own copy of the fixture work dir for a test that writes, `build/`
  linked to the session's.
- **I-77 (part):** `test_the_old_way_is_apt_and_a_venv` asserts on pixi commands, not the word; the
  seven shell tests run against the conda base's Python.
- **I-78:** `test_deck_build` uses a local template, with no web font.
- **Gates:** F (also in random order), S.

## Phase 3 — One run-TOML dialect (L)

- **I-21:**
  1. A `heimdall migrate --v3` dry run over the 11 fixture configs (`migrate.v3_text`, `migrate.py:591`).
     Anything it cannot express is reported to you before going on.
  2. The fixtures to v3, in one commit with the tests that read them. **Gates I and F unchanged.**
  3. `config` models v3 directly (dataclass fields in v3's names), and `identity_parts` maps them to
     the frozen JSON keys.
  4. Delete `v3.py`, the v2 branches (`_form`, `_marks`, `strict=False`), `run.schema.json` (v2) and
     the rename tables (`schema.HOMES`/`V3_HOMES`, `house.V3_NAMES`, `docs.py:80`, `cli.py:946`).
     `schema/run.toml` in v3's names; one JSON schema.
- **I-91:** the fixture's `setup.sh`/`hep run` strings change with this migration.
- **I-20** is closed by it (decided).
- **Docs:** 04 rewritten in v3's names; 02's examples.
- **Gates:** F, S, I, B.

## Phase 4 — Retirements and record formats (M)

- **I-25:** first, `heimdall migrate --layout` dry runs over Brookhaven and High-Energy (expected:
  nothing to move). Then delete everything I-25 lists:
  - `migrate.py`, keeping a v2→v3 converter as `tools/convert_v2_to_v3.py`, outside the package;
  - `main()`'s probes (`cli.py:2256`) and `check_retired()`;
  - `HEKIT_*`, `{repo}`, `formerly`, the export keys, `master`, `plotmerge/`, `machine.py adopt` and its
    `.gitignore` lines, `build_by_hand.txt`;
  - the shell helpers, and `strict=False`.
- **I-26:** `core/retired.py` (`{old: (new, since)}`), the one table every refusal reads; a v1 file is
  refused by name.
- **I-27:**
  - `heimdall.toml` is the marker; `hep.toml` is read for one release; `heimdall setup --refresh`
    renames it.
  - **For you:** in Brookhaven and High-Energy, `git mv hep.toml heimdall.toml`, then
    `heimdall setup --refresh .` (Brookhaven's Makefile and comments).
- **I-28:**
  - `format = 1` in `points.json`, `provenance.json`, `identity.json` and `plot.toml`, and a `FORMAT` file
    per record folder;
  - `heimdall records upgrade [--apply]`, dry run by default, which also takes over the old
    `migrate --snapshot` and `--plot-docs` jobs.
  - It writes into your work dirs' records: **you** run it, after its dry run.
- **I-68:** `workdirs.toml` gains `format = 1`, written only when the file is next written; a reader
  for each old form; a backup before any rewrite.
- **I-29:** the dead names and stale hints; `{repo}` → `{hep}` in the recipes.
- **I-30:** `proven = [...]` in toolkit files; `stack list --toolkits` shows "unproven". `@primary`,
  `@core-conda` and `@loops` are marked from the recorded builds.
- **I-105:** "F8 `--more`" and the stack-version stamp closed (dropped).
- **Gates:** F, I, B.

## Phase 5 — The session layer and the CLI (M)

- **I-35:**
  - `session/request.py` holds `RunRequest`. `session/session.py` holds `build_plans` → `plan`,
    `_numbered`, `run_one`, `draw_run` and `refuse_overwrites`, with **one** sweep executor
    (`_runs`/`_pipelined` merged: a gate per run).
  - `session/worker.py` holds `background`, `catch_signals` and `live`.
  - The six fabricated `Namespace`s become requests.
- **I-36:** `heimdall plan CONFIG [CFG] [--why|--config|--card T|--points|--json]`. `run --plan` and its
  kin are refused with the new spelling; `check` = `plan` of everything, quiet.
- **I-37:** `--json` on `plan`, `status`, `runs`, `tools` and `stack status`, from `cli/views.py`.
- **I-70:** `--stages` is the stage selector (`--only X` = stages X plus a rerun of X; `--no-plot` an
  alias); `--plain` global only.
- **I-71:**
  - `make` → `build TARGET`; `image` → `stack image`; `doctor` and `status --stack` → `stack doctor` and
    `stack status`, each old spelling refused with its new one;
  - `main()` from a dispatch table.
- **I-72:** `heimdall show RECORD[/POINT]`: provenance, identity parts, products, σ, counts, the logs'
  tail.
- **I-73:** `heimdall completion bash`.
- **I-100:** `heimdall plan --check`: each tool folder's cheap preflight (a new `[checks] preflight`
  argv; Pythia's `init()` through `App_PythiaCheck`, `rivet --list-analyses`). Never a FIFO.
- **I-101:** `heimdall plan --config` and `heimdall explain` say where each resolved value came from,
  style layers included.
- **Docs:** 05 (commands), 02 (the CLI's examples).
- **Gates:** F, S, I, B; the help diff reviewed.

## Phase 6 — The plot model (L)

- **I-40:** closed as kept.
- **I-41:**
  - configs refuse `plot_points`, naming the set that says the same; `totality` reads an old
    document's `[axes].plot_points` as its page axes, so recorded runs draw as before.
  - **For you:** set lines replacing `plot_points` in Brookhaven's `eic/{dis,photoproduction,zeus,baseline}`
    and `zeus/{photo,dis}`, and High-Energy's `Lambda/lambda.toml`.
- **I-42:** a `[figure_class.*]` table in `schema/run.toml`; one dispatcher; `_pages`' two loops become
  one; a `_cached()` helper for the five stamp sites.
- **I-43:** the transforms mpl takes from `framework/plot/yoda/backend.py` move into the mpl backend.
  Then delete `yoda/`, `backend.toml`, `"both"` and the pixel test.
- **I-44:** `viewer.page` for every index (`plot.write_index`, `write_sets_index`).
- **I-45:** `heimdall plot --stats-only`; `stats` refused with its new spelling.
- **I-46:** compare figures get their own step after their configurations' runs (and `--across`), drawn
  once.
- **I-47:** Paint's PDF line widths, measured against its PNGs and fixed. Paint is plot-only and safe
  to rebuild.
- **I-48:** heat maps in mpl; non-numeric scan axes (PDF sets); a sheet's shared y title and legend.
- **I-97:** weight variations (`/x[MUR2_MUF2]`) kept in the merged file and drawn as an envelope band (a
  curve style key).
- **I-99:** `heimdall plot --suggest-data-map`.
- **I-105:** the deck `template` key.
- **Gates:** F, S, B, plus one Brookhaven run drawn **into scratch** and compared page by page with its
  `plots/`.

## Phase 7 — The package restructure (M)

- **I-50:**
  - `runner/{core,stack,config,plan,run,draw,session,machine,cli}/`, moved module by module in layer
    order, with F after each move;
  - `test_imports.py` by package;
  - `runner/errors.py`, `runner/results.py` and `hepkit.py` keep their paths.
- **I-51:** the plugin loader serves tool folders only. `bars`, `derive`, `layout` and the mpl backend
  become normal modules, with matplotlib and YODA imported lazily. A test pins the dependency set.
- **I-52:** `env/hep_env.sh` → `shell/`; `rules.mk`, `work.mk` and `flags.sh` → `framework/make/`. The
  template's `include` follows; `pth.py` exposes only `runner` and `hepkit`. **For you:** `heimdall setup
  --refresh` in each work dir (the Makefile's include path).
- **Gates:** F per move; S, I, B at the end.

## Phase 8 — The stack (M)

- **I-55:** `runner/stack/`, made from `build_stack.py`'s functions, with exceptions in place of
  `die()`. `recipes/build_stack.py` becomes a thin CLI. **Gate:** `--dry-run` byte-identical for
  `@primary`, `@core-conda` and `packages=all`.
- **I-56:** recipes gain `flags`/`version`; `hep_env.sh` reads `.stamps/folders` alone (`PATH` and
  `LD_LIBRARY_PATH` diffed in a fresh shell). Delete `env/stack.toml`, `env/stack.py`, `env/packages.sh`
  and `make registry`.
- **I-57:** the build reads `<root>/downloads/`, then the old place for a release. Then (approved)
  `mv ~/Himinbjorg/forge/downloads ~/Himinbjorg/downloads`, and CLAUDE.md's `forge/` line is updated.
- **I-58:** `apps/.source`, with warnings on a mismatch.
- **I-59:** `support.toml` in Himinbjorg; `--publish`.
- **I-60:** download progress.
- **I-61:** helper scripts in the digest; yoda's `plain-h5cc` check.
- **I-62:** a per-package base digest (the compilers and runtime, plus the base libraries it builds
  against).
- **I-63:** Geant4's data through the build's downloader.
- **I-65:** the CMake-on-base test.
- **I-66:** MG5aMC_PY8 (`main164`) and Herwig's/ThePEG's paths in MadGraph's options (`recipes/madgraph.py`).
- **I-77 (rest):** `jsonschema` in the base's Python list, after I-62, so it marks only Python. The base
  rebuild is named before it runs.
- **I-88:** a tracked multi-platform pixi lock (linux-64, osx-arm64; repodata fetches named first); a
  bootstrap note for Python < 3.11; the GL viewers opened once at the lab PC. The comparison against
  the old stack is **closed**: that stack is gone, and the legacy gates in `tests/reference/` stand for it.
- **Gates:** F, S, the dry-run diff, `stack status` unchanged.

## Phase 9 — Roots, and cluster images (M)

- **I-75:**
  - `core/roots.WorkDir`, resolved once and passed down;
  - a record's snapshot run is `WorkDir(configs=…)`, so `paths.configs_at` and `cli.opened`'s
    `os.environ` writes go;
  - `HEP_RESULTS`/`RECORDS`/`CACHE`/`REPORTS`/`DECKS`/`CONFIGS`/`RUNS`/`WORKDIRS` dropped
    (`cluster.ROOTS` follows; the shadow root replaces `RUNS`/`WORKDIRS`).
- **I-86:** `heimdall cluster` with `[cluster] image` plans inside the image (`launch.sh --image`) and
  writes `submit.sh` (sbatch lines chained by job id), which the host runs. Tested emulated (the fake
  runtime of `test_image.py`, the emulated Slurm of `test_cluster_emulated.py`).
- **Gates:** F, S, I.

## Phase 10 — Throughput and provenance (L)

- **I-95 first:** per-group identities, recorded beside each point and derivable from old
  `identity.json` files. A point reruns only the groups whose identity changed. The point identity is
  untouched (gate I).
- **I-90 then:**
  - `Module.hh`'s `hep` strings fixed (module programs rebuilt: their points rerun, now group by group);
  - `App_yd2rt.cc`'s comment edited with its line count kept, the binary's sha256 checked
    **unchanged**. If it changes, stop and ask: yd2rt is in nearly every Brookhaven and High-Energy
    chain.
- **I-96:** one generation shared by points whose generator identity agrees; Rivet runs every variant in
  one pass.
- **I-98:** shards on other folders (a module with a merge tool); K from `threads`; the parallel-points
  timing measured.
- **I-67:** a `[tools.sherpa] mpi = N` option, never in the identity: `prepare.py` runs the integration
  under `mpirun -n N` (OpenMPI from `@loops`).
- **I-102:** the point, its identity and revision written into its YODA (`/_EVTCOUNT` annotations, by the
  runner); `heimdall show`'s index over provenance (SQLite, stdlib). A TNamed in the ROOT file needs
  App_yd2rt rebuilt: **asked first**, as only the yd2rt groups would rerun after I-95.
- **Gates:** F, S, I, B.

## Phase 11 — Physics set-ups (L)

- **I-103:**
  - an ep Delphes card (from the EIC's published Delphes cards, the download named first);
  - a Geant4 simulation module (`// requires: geant4 hepmc3`, Module.hh's kit, a HepMC3 input);
  - each with a fixture-free test and a Brookhaven example config **for you** to add.
  - Herwig photoproduction stays an idea.
- **I-104:**
  - `private = [...]` recipes (built into `stack/<dependent>/private/<name>/`, rpath-linked, in the
    dependent's digest), `scope = "private"`, a tool folder's `{package}`, and a prepend form of
    `[command] env`;
  - then BeAGLE (DPMJet 3, Pythia 6 with LHAPDF, RAPGAP 3.302), after reading its README; every download
    named first.
- **Gates:** F, S.

## Parked (they stay in ISSUES.md as `held`)

| Issue | Waits for |
| --- | --- |
| I-80, I-82 | the Mac (I-80 then retires `base = "system"`) |
| I-83 | the reinstall, when you do it |
| I-85 | your yes to the Apptainer image's downloads |
| I-87 | a real Slurm site; HTCondor and PBS join it |
| I-81's roadmap, Herwig photoproduction | kept as ideas |

## Verification (the end state)

- F and S pass. Gate I holds against the golden file (written in Phase 2) after every phase.
- Brookhaven's `heimdall status` gives the same complete points as the Phase 2 snapshot, except where a
  phase said otherwise (I-90's module programs).
- `heimdall plan`, `show`, `--json` and `completion` work on Brookhaven read-only.
- One Brookhaven run is drawn into scratch with the same page names.
- ISSUES.md holds only the parked issues, and `docs/07_Record.md` holds V190 onwards.
