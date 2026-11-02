# Issues

Pending work, one issue a task: what, why, done when. Rules: [work](../docs/rules/work.md). Rebuilt 2026-11-02, each checked against the code.

**Status:** `open` · `decision` (waits for the developer) · `blocked` · `held` (ask first) · `idea`. **Priority:** P1 this cycle · P2 next · P3 when convenient.

**Order of phases:** 2 safety net (I-10, I-11, I-12, I-13, I-76, I-77) → 3 one dialect (I-20, I-21, I-91) → 4 retirements (I-25, I-26, I-28, I-29, I-30, I-68) → 5 session and CLI (I-35–37, I-70–73, I-100, I-101) → 6 plot model (I-41–48, I-97, I-99) → 7 packages (I-50–52) → 8 stack (I-55–66, I-88) → 9 roots, cluster images (I-75, I-86) → 10 throughput (I-95, I-96, I-98, I-67, I-102) → 11 physics (I-103, I-104). The safety net matters before any change to identity or records. Parked: I-80, I-82, I-83, I-85, I-87, I-81.

**Decided (2026-10-25), standing:** drop v2 (a work dir's `configs/legacy/` stays as history) · `plot.toml` stays a drawing's source · retire `plot_points`, old documents still draw · delete the yoda backend, mpl may drift from mkhtml · `[heimdall]` keeps preference switches only · `editor/` stays · doctor's row goes to Himinbjorg, published on purpose · downloads to `<root>/downloads/` · identity golden file approved · `--logs` and `--journal` stay as shorthands · plan inside the image · Herwig for MadGraph, plus MG5aMC_PY8.

## Next pieces

### I-120 Rework the scoring · P1 · decision
Scoring and drawing sit in one 875-line `figures/bars.py`; fixed points by place, five overlapping statistics summed, no score across Runs. Context: [notes](plans/scoring/notes.md). **Done when:** a plan is agreed, scoring is a module of its own (rows in, scores out), and the summary and reports use it.

### I-121 A points library · P1 · decision
A pooled collection of points per Assignment that any Errand and Run can use, rather than per-Run folders. Context: [notes](plans/points-library/notes.md). Needs I-10, I-11, I-28 first. **Done when:** a plan settles the key, layout, seeds, invalidation and migration, and two Errands share a point without rerunning it.

### I-122 Commit the migrated work dirs · P2 · held
The names' migration (`[errand]`, `heimdall.toml`) is applied uncommitted in two work dirs. They are the developer's. **Done when:** the developer has reviewed and committed them, or says otherwise.

## Safety net

### I-07 Task L's checks by hand · P1 · open
By hand on the lab PC: a run, `d`, close the terminal; `heimdall runs`, `watch` (`q`), `runs` again; the same over ssh. **Done when:** the verdict shows in each.

### I-10 A shadow machine root for the tests · P1 · open
Tests run with the real `HEIMDALL_MACHINE`, so live `machine.toml` and `recipes.toml` decide what they keep and see. `conftest` builds `forge/scratch/machine/`: real `stack/`, `base/`, `apps/`, `forge/downloads/` linked, own empty `machine.toml`, `recipes.toml`, `runs/`, `workdirs.toml`. **Done when:** suites pass as before, and no test touches `~/Himinbjorg`'s own files; a guard checks stamps and apps unchanged.

### I-11 An identity golden file · P1 · held
`tests/golden/identity_parts.json`, every fixture point's parts, binaries' sha256 masked, written under I-10. **Done when:** a test compares it, and each refactor leaves it unchanged.

### I-12 Baselines before the restructure · P1 · open
**Done when:** fast and slow suite results, and `heimdall status` of a real study's configs (read-only), are recorded, and a local tag `pre-restructure` exists.

### I-13 Static checks · P2 · open
No `pyproject.toml`, ruff or mypy. **Done when:** ruff (report-only, then enforcing) and mypy on new modules, and `make check` = ruff + import layers + fast suite.

### I-76 Tests independent of their order · P2 · open
Every test shares one scratch work dir whose records accumulate. **Done when:** a writing test has its own copy, and `pytest -n` works.

### I-77 Tests a conda-base root skips · P3 · open
Seven shell tests know only a venv. `test_v3`'s schema test needs `jsonschema`. `test_the_old_way_is_apt_and_a_venv` fails on a conda root, as it asserts "pixi" appears nowhere and the path holds it. **Done when:** they run on the base, or go with I-80.

### I-79 Legacy gates differ by one digit on the conda base · P2 · decision
`test_gates_p1.py::test_the_legacy_reference_is_reproduced_byte_for_byte[MSTW|NNLO]`: byte 323 of the YODA. It comes from the rebuilt stack, not the runner; references are never regenerated. Yours: accept the digit with a written tolerance, or find which package moved it.

### I-124 Figure paths no test covers · P3 · open
`derive.scan_value`'s `integral`, `mean`, `entries`; `projection-y`; a sheet's error paths. **Done when:** each has a test.

## One dialect

### I-20 Drop v2 errand files · P1 · decided
The 11 fixture configs migrated once; a converter kept outside the package for a while. **Done when:** a v2 file is refused with its way on.

### I-21 v3 as the form and the model · P1 · blocked on I-10, I-11, I-20
v3 is translated into v2 tables; the rename table is written many times; errors speak v2 to a v3 user. Fixtures to v3, the model in v3's names with `identity_parts` mapping to frozen keys, then delete `v3.py`, v2 branches, `run.schema.json`, the rename tables. **Done when:** gate I-11 is unchanged, and messages use the file's own names.

### I-91 `hep` and `setup.sh` in the frozen fixture · P3 · blocked on I-21
**Done when:** the fixture's Makefile error, config comments, `modules/Decay/README.md` and its old doc cites (`docs/02_…`, `04 §9`) use today's names and `doc:` ids, changed with I-21's migration. `test_docs.py` exempts the fixture until then.

## Retirements

### I-25 Retire migrations and guards for retired names · P1 · blocked on I-21
First `migrate --layout` dry runs over the real work dirs. Delete: `migrate.py`; legacy probes and `check_retired()`; `paths.RETIRED`, `HEKIT_*`, `{repo}`, `[tool] formerly`, `tools.EXPORT`; `[file].master`; `framework/tools/plotmerge/`; `machine.py adopt`; `recipes/build_by_hand.txt` (drifted: 404s, no base); the shell's `quit`, `heimdall_status`, `heimdall_stash`, `heimdall_forge`, `heimdall_stack`; `strict=False`. **Done when:** gone, with refusals naming the new form.

### I-26 One table of retired names · P2 · blocked on I-25
`retired.py`: `{old: (new, since)}`, read by the schema check, CLI and shell. **Done when:** it replaces the ad-hoc refusals.

### I-28 Record files with a format version · P2 · open
`points.json`, `provenance.json`, `identity.json`, `plot.toml` carry none; layouts are recognised by heuristics. **Done when:** `format = N` in each, and one `heimdall records upgrade` (dry run first) does the migrate jobs.

### I-29 Leftover names and stale hints · P3 · open
`plot.BACKENDS`, `layout.TILED`, `tools.ENV`; hints naming `heimdall plot FILE` rather than `overlay`; wrappers `objects_of`, `raws_of`, `_sha`, `base_of`; `{repo}` in the recipes. **Done when:** gone.

### I-30 Mark unproven toolkits · P3 · open
`proven = [...]` in a toolkit file after a recorded build; `--toolkits` shows "unproven". **Done when:** listing says so.

### I-68 Live-state files keep a reader for old forms · P2 · open
`workdirs.toml`, `.stamps/` carry no version. **Done when:** a `format` key, a reader kept per change, and a backup beside itself before a rewrite.

## Session and CLI

### I-35 `RunRequest` and a session module · P1 · blocked on I-25
`cli.py` (2,887 lines) holds orchestration, two sweep executors, 62 `getattr(args…)`. **Done when:** `session.plan`, `session.run` with one executor; `cli` parses, dispatches and prints.

### I-36 `heimdall plan` · P2 · decided
`plan CONFIG [CFG] [--why|--config|--card TAG] [--points] [--json]`, replacing `run --plan` and kin; old spellings refused for a release. **Done when:** so.

### I-37 `--json` · P2 · blocked on I-35
**Done when:** `plan`, `status`, `runs`, `tools`, `stack status` have it from one renderer.

### I-70 One stage selector, one keep flag, one `--plain` · P2 · blocked on I-35
**Done when:** `--stages` selects (`--no-plot` an alias), `--keep WORDS` is the flag (`--logs`, `--journal` shorthands), `--plain` global.

### I-71 Fewer commands for one job · P2 · open
**Done when:** `doctor` and `status --stack` → `stack doctor`, `stack status`; `make` → `build TARGET`; `image` → `stack image`; `main()` dispatches from a table.

### I-72 `heimdall show` · P3 · open
**Done when:** `show RECORD[/POINT]` prints provenance, identity parts, products, σ, counts, logs' tail.

### I-73 Shell completion · P3 · open
**Done when:** `heimdall completion bash` covers commands, configs, configurations, point tags.

## Plot model

### I-41 Sets as the one grouping; retire `plot_points` · P2 · decided
`[cfgs.x] plot = [...]` and `totality` carry what it said; a file with it is refused with the set that says the same. **Done when:** so.

### I-42 Figure classes as a table · P2 · open
Classes are dispatched by `kind ==` loops, and `check_plot` hand-codes rules. Also `_pages`' near-duplicate loops, five stamp-and-rebuild sites, `figures(run)` parsed repeatedly. **Done when:** a `[figure_class.<c>]` schema table, one dispatcher, one `_cached` helper.

### I-43 Delete the yoda backend · P2 · decided
mpl loads it for transforms. Its pixel test already fails alone (ratio antialiasing). **Done when:** transforms move to mpl; `yoda/`, `"both"` and that test go.

### I-44 One HTML index writer · P3 · open
**Done when:** `write_index`, `write_sets_index` use `viewer.page`.

### I-45 `heimdall stats` → `heimdall plot --stats-only` · P3 · decided
**Done when:** so, `stats` refused for a release.

### I-46 Compare figures: their own stage · P2 · open
Drawn as a side effect of each configuration's stage, up to N times, not on plot documents. **Done when:** drawn once, in its own step.

### I-47 Paint's PDF line widths · P3 · open
About twice too thick; not measured lately. **Done when:** measured and fixed, or closed.

### I-48 Known plot limits · P3 · idea
Heat maps Paint-only; scan x must be numeric; sheets have no shared title or legend.

## Packages

### I-50 `runner/` as subpackages · P2 · decided
God modules: `cli.py`, `plot.py`, `tools.py`, `config.py`. **Done when:** `core/`, `stack/`, `config/`, `plan/`, `run/`, `draw/`, `session/`, `machine/`, `cli/`, moved one at a time, `test_imports` by package.

### I-51 The plugin loader for tool folders only · P2 · blocked on I-50
`bars.py`, backends, `build_stack.py` load as plugins though `tomli_w` is imported anyway. **Done when:** imported normally, the dependency set pinned by a test.

### I-52 `env/` into `shell/` and `framework/make/` · P3 · blocked on I-50
**Done when:** moved; `pth.py` puts only `runner` and `heimdallkit` on the path.

## Stack

### I-55 The stack builder as a library · P2 · open
**Done when:** a `stack` package with exceptions; `build_stack.py` a thin CLI; `--dry-run` byte-identical for `@primary`, `@core-conda`, `packages=all`.

### I-56 One stack registry · P2 · blocked on I-55
Four say what a package is. **Done when:** recipes gain `flags`, `version`; `heimdall_env.sh` reads `.stamps/folders`; `env/stack.toml`, `stack.py`, `packages.sh` go.

### I-57 Downloads out of `forge/` · P2 · decided
`forge/` may be emptied, losing 3.3 GB. **Done when:** `~/Himinbjorg/downloads/`, old place read for a release; the move done with the developer's yes.

### I-58 Which checkout built `apps/` · P2 · open
**Done when:** `apps/.source` records checkout, revision, `src/` digest; `run` and `doctor` warn on a mismatch.

### I-59 `doctor --record` into Himinbjorg · P3 · decided
It writes into the checkout, and `recipes/support/`'s one row is a removed system's. **Done when:** `~/Himinbjorg/support.toml`, `--publish` copies it, the old row dropped or dated.

### I-60 Download progress · P3 · open
**Done when:** bytes, rate and ETA live; a line per file when plain; pixi's too.

### I-61 A recipe's helper scripts in its digest · P3 · open
**Done when:** changing `recipes/helpers/*` rebuilds; yoda's recipe checks `plain-h5cc` first.

### I-62 A base change marks only what it touches · P3 · open
**Done when:** a digest takes compilers, runtime, and the base libraries a package builds against.

### I-63 Geant4's data through the downloader · P3 · open
**Done when:** resumed, checked, kept; CMake pointed at them.

### I-65 A test that CMake on the base ignores `/usr` · P3 · open
**Done when:** the test exists.

### I-66 MadGraph: the MG5aMC_PY8 interface, Herwig's paths · P3 · open
**Done when:** both work in a shower through `main164`.

### I-67 Sherpa's integration over MPI · P3 · idea
`mpirun -n N` in the prepare step, in no identity.

### I-88 The conda base's phase 3 · P3 · open
**Done when:** physics compared against the old stack; a tracked multi-platform lock; a bootstrap for Python < 3.11; ROOT's and Geant4's GL viewers opened once.

### I-123 CI that has never run · P3 · decision
`.github/workflows/stack.yml` and its Dockerfile have no run on record. **Done when:** run once, or retired.

## Roots and machine

### I-75 A `WorkDir` value · P2 · blocked on I-10
Eight root variables, `os.environ` mutated for a record's configs. **Done when:** resolved once and passed down; the variables go.

### I-80 Retire `base = "system"` · P3 · blocked on I-82
**Done when:** the venv, apt and Homebrew paths are gone.

### I-81 `editor/`'s roadmap · P3 · idea
Stays here (decided); check the icon bank's Vecteezy licence before any public repository. Left: `.cmnd` PDG subscope, C++ string injection, snippets; theme's ROOT tokens; new packages `pythia-hover`, `hep-snippets`, `hep-tasks`, `hep-statusbar`, `yoda-syntax`.

### I-82 The Mac on the conda base · P2 · held
Unproven on macOS. **Done when:** rebuilt there, suites run, a support row recorded.

### I-83 The lab PC's reinstall · P3 · decision
Postponed 2026-10-15; the stack was rebuilt in place. Confirm if still wanted.

### I-85 A real Apptainer image · P2 · held
Fake runtime only; `apptainer` is now on this machine. Name downloads first. **Done when:** built and run.

### I-86 `[cluster] image` plans inside · P2 · decided
**Done when:** planning runs in the image and writes a `submit.sh` the host runs.

### I-87 `heimdall cluster` on a real Slurm · P3 · open
**Done when:** `--dry-run`, then a submission, on a real site.

## Ideas

- **I-95** Per-group identity and skip: changing yd2rt's `select` reran a 16.1 s point instead of 0.2 s.
- **I-96** Shared generation for analysis-option sweeps; needs I-95.
- **I-97** Weight variations as a band: scale and PDF uncertainty without extra generations.
- **I-98** Shards beyond Rivet; K from threads. Parallel-points timing unmeasured.
- **I-99** `heimdall plot --suggest-data-map`: lines matched by name, to check and paste.
- **I-100** `heimdall run --check`: each tool's cheap preflight, never opening a FIFO.
- **I-101** `--explain KEY`: the layer that set a value.
- **I-102** Products that identify themselves; a SQLite index of provenance.
- **I-103** Physics set-ups: an ep Delphes card (ATLAS's finds a jet in 0.9 % of events), Herwig photoproduction, a Geant4 module.
- **I-104** A tool's private dependencies (BeAGLE): `private = [...]`, set aside 2026-10-15.
- **I-105** Leftovers: `migrate --stamp`; HTCondor and PBS; "F8 `--more`", undescribed: confirm or drop; `--plan`'s "note: folder 01" wording is cryptic.
