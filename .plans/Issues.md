# Issues

Pending work, one issue a task: what, why, done when. Rules: [work](../docs/rules/work.md), whose pipeline ends every round here and in [Notes](Notes.md). Rebuilt 2026-11-02, each checked against the code; round 1's leftovers merged 2026-11-09.

**Status:** `open` · `decision` (waits for the developer) · `blocked` · `held` (ask first) · `idea`. **Priority:** P1 this cycle · P2 next · P3 when convenient.

**Next:** the developer's reads (I-136, and Notes' off-plan decisions); then plan one dialect (I-20, I-21), the snapshot question first. **Order of phases:** 2 safety net (I-13, I-76, I-77, I-129, I-135, I-138) → 3 one dialect (I-20, I-21, I-91) → 4 retirements (I-25, I-26, I-28, I-29, I-30, I-68) → 5 session and CLI (I-35–37, I-70, I-71, I-100, I-101, I-131, I-132, I-134, I-139) → 6 plot model (I-41–48, I-97, I-99, I-133, I-137) → 7 packages (I-50–52) → 8 stack (I-55–66, I-88) → 9 roots, cluster images (I-75, I-86) → 10 throughput (I-95, I-96, I-98, I-67, I-102) → 11 physics (I-103, I-104). The safety net matters before any change to identity or records. Round 1 (2026-11-09) and its review: [Notes](Notes.md). Parked: I-80, I-82, I-83, I-85, I-87, I-81.

**Decided (2026-10-25), standing:** drop v2 (a work dir's `configs/legacy/` stays as history) · `plot.toml` stays a drawing's source · retire `plot_points`, old documents still draw · delete the yoda backend, mpl may drift from mkhtml · `[heimdall]` keeps preference switches only · `editor/` stays · doctor's row goes to Himinbjorg, published on purpose · downloads to `<root>/downloads/` · identity golden file approved · `--logs` and `--journal` stay as shorthands · plan inside the image · Herwig for MadGraph, plus MG5aMC_PY8.

## Next pieces

### I-122 Commit the migrated work dirs · P2 · held
The names' migration (`[errand]`, `heimdall.toml`) is applied uncommitted in two work dirs. They are the developer's. `heimdall migrate --plot-docs --apply` (plot documents by tag) waits on the same yes. **Done when:** the developer has reviewed and committed them, or says otherwise.

### I-149 A rewritten config or card makes new points · P1 · decision
One physics should be one identity, whatever the writing. Today (`test_identity_order.py`; three strict xfails):
- **`vary`'s order:** quantity lines enter the cards in `vary` order, then the static ones (`tools.py:932`), so `["pdf", "energies"]` and `["energies", "pdf"]` give every point a new identity, library key and, by identity seeding, seed and events. The `[quantities.*]` tables' order is already safe.
- **A card's text:** the identity holds `base_sha256`, the raw base card's hash (`tools.py:1234`), beside its cleaned lines (V54). So a comment, a blank line or a trailing space in a `.cmnd` or `.yaml` is a new point. The prepare cache also keys on it, and MadGraph's prepare needs it there.
- **A card's line order:** the cleaned lines are hashed in the order written. For some tools order is physics: Pythia's `Tune:` resets what was set before it and a repeated key's last line wins, and Herwig's `.in` and MadGraph's cards are sequential. YAML mappings are not ordered.
Each fix changes what identities hash: all 885 of a real work dir's library entries carry `base_sha256`, and their lines are in written order. Yours, for each: (a) fix, with old markers accepted as complete and their seeds kept, and the library re-keyed by `heimdall records upgrade`, so nothing reruns; (b) fix and rerun; (c) leave, and say in the docs that it is part of the physics. Recommended: (a) for `vary`'s order (a canonical quantity order) and for the card's text (drop `base_sha256` from the identity, keep it in the prepare key); (c) for line order, except YAML mappings by parsed key. Two quantities writing one card key make the order physics; refuse that whichever is chosen. Independent-seed copies of one physics (random or manual seeds) are kept by `prune --duplicates`; merging them into one entry with summed events is a point of its own, not built. **Done when:** decided, and each xfail passes or is gone with a doc line.

### I-130 The points library on a real work dir · P2 · decision
`adopt` ran on 2026-11-09 over a real work dir's 42 Runs (886 entries; its 274 duplicates were byte-identical, same seed, and pruned): `verify` clean, every Run's `status` and drawable points the same as before ([live doc](../docs/live/adopted-runs.md)). A first try that day broke `plot` and the Run numbering and was reverted from its snapshot; the fixes are V263, V267. Left: `library = "only"` keeps a Run's `logs/` and `run.jsonl` in `records/<A>/<E>/<R>/` (the plan said no folder). **Done when:** the developer has confirmed where an `"only"` Run's log lives.

### I-136 The scoring, read by the developer · P1 · decision
Built 2026-11-07 and never read by the developer. Yours: read one real Run's `statistics/<set>/summary.pdf`; accept or reject each rule the implementer chose alone, defaults first: weights precedence (figure `weight` > first glob > 1), data pages beating curve-measured pages in a mixed table, an Errand's row over only the pages every Run has; then the opt-in ones (`mad`'s floor at 10 % of the good-to-bad span, `median` floored at \|good\|, `promethee` q = 0.1 and p = 1.0, `topsis` as 1 − closeness, `fisher`'s p capped at 1e-300, no renormalisation of a merged file, marginals over (cell, point) scores). Also: `[figure].weight` is checked but the summary never reads it (read it, or refuse the key); keep or drop the `<metric>:crossed` table and `statistics.csv`'s `area` column. **Done when:** each rule is a decision note or an issue, and the summary is read.

## Safety net

### I-07 Task L's checks by hand · P1 · open
By hand on the lab PC: a run, `d`, close the terminal; `heimdall runs`, `watch` (`q`), `runs` again; the same over ssh. And after a real reboot, `heimdall runs --resume-queue` on a sweep's queue: its test fakes the relaunch, so a sweep member's own command (`--sweep-member KEY --queued-to ID --detach`) has never run. **Done when:** the verdict shows in each, and the requeued sweep finishes in order.

### I-13 Static checks · P2 · open
No `pyproject.toml`, ruff or mypy. **Done when:** ruff (report-only, then enforcing) and mypy on new modules, first `runs.py` (`RunEntry`, `RunState`) and `record.py`, where a wrong key costs most, and `make check` = ruff + import layers + fast suite.

### I-129 Tests that list live runs see the machine's own · P2 · open
`heimdall runs` finds a run by its watch socket, which no test directory scopes, so a run of the user's that is live on the machine is `[1]` in a test's listing. `test_detached_runs.py` now finds its own block by its pid; `test_cluster.py:298` and the first listing of `test_detached_runs.py` read the whole listing. **Done when:** the sockets a test's runs open and read are the test's own (a root variable `conftest` sets), or each such test names its run by pid, and none depends on the machine being idle.

### I-135 Fixture identities hash an absolute cache path · P2 · decision
The Herwig, MadGraph and Sherpa fixtures' identities include a `.cache/…` absolute path, so a moved work dir or another checkout reruns every such point, and two clones' library entries never pool. Identity is ask-first. Yours: strip the path from the identity (every such point reruns once), from the library key only (nothing reruns), or leave it. **Done when:** decided, and the golden file says so.

### I-138 Sweeps the 2026-11-08 audit left · P3 · open
Each run from the checkout; the audit's text is in git at `7bed373` (`.plans/audits/2026-11-08-code/`). **Dead:** single-use helpers, unreached branches and keywords (`run_one`, `_cmd_run`, `plot._pages`), tool folders no test runs, shell functions, `src/` flags, methods per class. **Duplicated:** copied bodies, flags that mean the same, choices listed in help and code, numbers both Paint and `stats/` compute. **Structure:** the import graph, `tools.py`'s and `plot.py`'s cohesion. **Design:** keys read then ignored, silent fallbacks, stale module caches, writes past `write_atomic`. **Oversights:** free disk before a run, kill -9 per write path, two users on one Himinbjorg, clocks and time zones, 10⁴ points and 50 queued configurations. **Tests:** mutation of `wait_turn`, `library.key`, `library.link`; loosened asserts; fakes' types; `--durations`. **Process:** every open issue against the code; round 1's crystallise step 4 for the pages it did not touch. **Done when:** each is run and its findings are issues, or dropped with why.

### I-76 Tests independent of their order · P2 · open
Every test shares one scratch work dir whose records accumulate. **Done when:** a writing test has its own copy, and `pytest -n` works.

### I-77 Tests a conda-base root skips · P3 · open
Seven shell tests know only a venv. `test_v3`'s schema test needs `jsonschema`. `test_the_old_way_is_apt_and_a_venv` fails on a conda root, as it asserts "pixi" appears nowhere and the path holds it. The old-way test is skipped on a conda root until the base is decided. **Done when:** they run on the base, or go with I-80.

### I-79 Legacy gates differ by one digit on the conda base · P2 · decision
`test_gates_p1.py::test_the_legacy_reference_is_reproduced_byte_for_byte[MSTW|NNLO]`: byte 323 of the YODA. It comes from the rebuilt stack, not the runner; references are never regenerated. Yours: accept the digit with a written tolerance, or find which package moved it. (the gates are strict xfails until decided)

### I-124 Figure paths no test covers · P3 · open
`derive.scan_value`'s `integral`, `mean`, `entries`; `projection-y`; a sheet's error paths. **Done when:** each has a test.

## One dialect

### I-20 Drop v2 errand files · P1 · decided
The 11 fixture configs migrated once; a converter kept outside the package for a while. **Done when:** a v2 file is refused with its way on.

### I-21 v3 as the form and the model · P1 · blocked on I-20
v3 is translated into v2 tables; the rename table is written many times; errors speak v2 to a v3 user. Fixtures to v3, the model in v3's names with `identity_parts` mapping to frozen keys, then delete `v3.py`, v2 branches, `run.schema.json`, the rename tables. Its plan settles first: every older Run's snapshot (`records/…/<R>/config/`) is a v2 file that `plot`, `status`, `runs --resume` and `--again` read, so a loader refusing v2 breaks old records unless a snapshot-only v2 reader stays, records are migrated (a write into work dirs), or old records are refused with a way on. Rides with it: a v3 file without `[file]`, `[cfgs]` or a chain is read as v2 (`v3.is_v3`); all 11 fixtures are v2; `migrate.py`'s one-shot migrations, each to check by a read-only dry run over the real work dirs; `config.parse` (261 lines) split after. **Done when:** the identity golden file is unchanged, and messages use the file's own names.

### I-91 `hep` and `setup.sh` in the frozen fixture · P3 · blocked on I-21
**Done when:** the fixture's Makefile error, config comments, `modules/Decay/README.md` and its old doc cites (`docs/02_…`, `04 §9`) use today's names and `doc:` ids, changed with I-21's migration. `test_docs.py` exempts the fixture until then.

## Retirements

### I-25 Retire migrations and guards for retired names · P1 · blocked on I-21
`migrate --layout` dry runs over both real work dirs ran 2026-11-09: one moved nothing; the other wanted to move today's `statistics/` and an Errand's across folders into `points/`, now fixed (V264), after which it moves nothing. Delete: `migrate.py` (after `adopt_points` has moved to `runner/library.py`, round 1 P3); legacy probes and `check_retired()`; `paths.RETIRED`, `HEKIT_*`, `{repo}`, `[tool] formerly`, `tools.EXPORT`; `[file].master`; `machine.py adopt`; `recipes/build_by_hand.txt` (drifted: 404s, no base); the shell's `quit`, `heimdall_status`, `heimdall_stash`, `heimdall_forge`, `heimdall_stack`; `strict=False`. **Done when:** gone, with refusals naming the new form.

### I-26 One table of retired names · P2 · blocked on I-25
`retired.py`: `{old: (new, since)}`, read by the schema check, CLI and shell. Seven sites refuse today, each in its own words: `paths.RETIRED`, `config.RETIRED_BACKENDS`, `tools.EXPORT`, `{repo}`, `[run]`, `v3.refuse_old_names`, and the `stats` and `deck` stubs. Heimdall has no releases, so "for a release" never ends: yours, a date or rule for each row (30 days, the next tag). **Done when:** it replaces the ad-hoc refusals, each row has its date, and `heimdall --help` lists no command that only refuses.

### I-28 Record files with a format version · P2 · decision
`format = 1` and `heimdall records upgrade` are done ([provenance](../docs/stable/internals/provenance.md)); `upgrade` stamps files and leaves layout moves to `migrate --layout`, short of this done-when. The developer accepts that (the issue leaves) or keeps it open. `points.json`, `provenance.json`, `identity.json`, `plot.toml` carry none; layouts are recognised by heuristics. **Done when:** `format = N` in each, and one `heimdall records upgrade` (dry run first) does the migrate jobs.

### I-29 Leftover names and stale hints · P3 · open
`plot.BACKENDS`, `tools.ENV`; hints naming `heimdall plot FILE` rather than `overlay`; wrappers `objects_of`, `raws_of`, `_sha`, `base_of`; `{repo}` in the recipes. **Done when:** gone.

### I-30 Mark unproven toolkits · P3 · open
`proven = [...]` in a toolkit file after a recorded build; `--toolkits` shows "unproven". **Done when:** listing says so.

### I-68 Live-state files keep a reader for old forms · P2 · open
`workdirs.toml`, `.stamps/` carry no version. **Done when:** a `format` key, a reader kept per change, and a backup beside itself before a rewrite.

## Session and CLI

### I-35 `RunRequest` and a session module · P1 · blocked on I-25
`cli.py` (2,887 lines) holds orchestration, two sweep executors, 62 `getattr(args…)`; internal callers forge `argparse.Namespace`s (11), so a new option read in planning breaks them. The audit of 2026-11-08 found a frozen `RunRequest` buildable from `args` today, without waiting for I-25. **Done when:** `session.plan`, `session.run` with one executor; `cli` parses, dispatches and prints.

### I-36 `heimdall plan` · P2 · decided
`plan CONFIG [CFG] [--why|--config|--card TAG] [--points] [--json]`, replacing `run --plan` and kin; old spellings refused for a release. With I-145, it says what a run will cost. **Done when:** so.

### I-37 `--json` · P2 · blocked on I-35
**Done when:** `plan`, `status`, `runs`, `ls`, `library list`, `tools`, `stack status` have it from one renderer (`show`, `diff`, `score` have it already).

### I-70 One stage selector, one keep flag, one `--plain` · P2 · blocked on I-35
**Done when:** `--stages` selects (`--no-plot` an alias), `--keep WORDS` is the flag (`--logs`, `--journal` shorthands), `--plain` global.

### I-71 Fewer commands for one job · P2 · open
**Done when:** `doctor` and `status --stack` → `stack doctor`, `stack status`; `make` → `build TARGET`; `image` → `stack image`; `main()` dispatches from a table.

### I-132 TAB completion goes silent after `=` or `:` · P2 · open
`env/complete.bash` passes `COMP_WORDS`, which bash splits at `COMP_WORDBREAKS` (`=` and `:` among them). So `heimdall run Demo/jets --set a=b <TAB>` reaches `complete.py` as `--set a = b` and offers nothing, where unsplit it offers all 13 configurations, and `runs --state=ru<TAB>` offers nothing (seen 2026-11-09 by `heimdall __complete` on the fixture work dir). The tests set `COMP_WORDS` unsplit, so they never meet it. **Done when:** the words are rebuilt from `COMP_LINE` and `COMP_POINT` (or `_get_comp_words_by_ref -n =:` where bash-completion is loaded), and a test drives bash with a split line.

### I-134 A sweep is a queue on a terminal and one process without · P2 · decision
With `--detach` or a terminal, a sweep is N workers and N entries; with `--plain`, a pipe, cron or a worker, one process and one entry. So `runs`, `--resume`, `--dispatch` and the logs behave differently for one command. Yours: one model (`--plain` queues too, followed in turn), or the difference said in `heimdall run --help`. **Done when:** so.

### I-139 Round 1's review nits · P3 · open
`cli.resume_queue` reads `house._states`, private across modules; `complete.NAMES` is module state rewritten on every call; `:files:` with an empty pattern lists folders twice (`compgen -d`, then `-f`, which lists them too). **Done when:** each is gone.

### I-131 TAB completion, by hand · P2 · open
Tested by a driver and 22 tests, not in a terminal on a real work dir, nor under a cluster login node's bash (its `compopt` is unchecked: bash before 4 gets no `nospace`). **Done when:** TAB after `heimdall `, `heimdall run `, `heimdall plot Demo/…/` and `heimdall runs --resume-queue ` answers in the lab PC's shell and on the cluster's, or a note says which bash lacks what.

## Plot model

### I-41 Sets as the one grouping; retire `plot_points` · P2 · decided
`[cfgs.x] plot = [...]` and `totality` carry what it said; a file with it is refused with the set that says the same. **Done when:** so.

### I-42 Figure classes as a table · P2 · open
Classes are dispatched by `kind ==` loops, and `check_plot` hand-codes rules. Also `_pages`' near-duplicate loops, five stamp-and-rebuild sites, `figures(run)` parsed repeatedly; `plot._pages` (272 lines, 150 branches) and `plotdoc.load_across` (143, 112), which every drawing passes, want their stages named. **Done when:** a `[figure_class.<c>]` schema table, one dispatcher, one `_cached` helper.

### I-44 One HTML index writer · P3 · open
Five writers today: `plot.write_index`, `write_sets_index`, `report._index`, `figures/webpage.py`, `viewer.py`. **Done when:** one page helper, one `<!DOCTYPE` in framework Python.

### I-46 Compare figures: their own stage · P2 · open
Drawn as a side effect of each configuration's stage, up to N times, not on plot documents. **Done when:** drawn once, in its own step.

### I-47 Paint's PDF line widths · P3 · open
About twice too thick; not measured lately. **Done when:** measured and fixed, or closed.

### I-133 Five ways to merge points · P2 · decision
`combine` (recorded, rivet-merge `-e`), the `merge` post tool (rivet-merge of every point), `plotmerge` (every point in one file, merging nothing), the `merged` figure, and a set's `merge` and `band`. Proposed: a set's `merge` is the one merge at drawing time, the `merged` figure becomes a set (with I-41), `combine` stays the recorded merge. Yours: is there a use of the `merge` post tool `combine` does not cover; is `plotmerge` renamed `bundle`. **Done when:** a decision note names one mechanism a job, the rest front ends or gone.

### I-137 `plot --style-sync` leaves `[score]` alone · P3 · open
`plotdoc.write_chosen` syncs `[plot]` and `[stats]` into a Run's `plot.toml` but not `[score]`, so a redraw scores as the first run did after the errand's `[score]` changed. **Done when:** synced, or the help says it is not.

### I-48 Known plot limits · P3 · idea
Heat maps Paint-only; scan x must be numeric; sheets have no shared title or legend.

## Packages

### I-50 `runner/` as subpackages · P2 · decided
God modules: `cli.py` (3600 lines, eight jobs), `house.py` (listing, show, ls, status), `report.py` (2443), `plot.py`, `tools.py`, `config.py`, and `record.py`, whose identity and seeds (ask first) should sit apart and frozen. 14 tests patch `cli.<name>`: re-point them to the owner as each moves. After the split, only numpy, yoda, matplotlib and `stats` import lazily. **Done when:** `core/`, `stack/`, `config/`, `plan/`, `run/`, `draw/`, `session/`, `machine/`, `cli/`, moved one at a time, `test_imports` by package.

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

### I-75 A `WorkDir` value · P2 · open
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
Also whether `flock` (`PointLock`, the library, the prepare cache) holds across nodes there: on Lustre's `localflock` or old NFS it may not, then `lockf` or an `O_EXCL` lock file with host and pid. **Done when:** `--dry-run`, then a submission, on a real site, and two nodes contend for one library entry.

## Ideas

- **I-95** Per-group identity and skip: changing yd2rt's `select` reran a 16.1 s point instead of 0.2 s.
- **I-96** Shared generation for analysis-option sweeps; needs I-95.
- **I-97** Weight variations as a band: scale and PDF uncertainty without extra generations. Not a set's `band`, which is drawn from separate points: this one reads one point's weights.
- **I-98** Shards beyond Rivet; K from threads. Parallel-points timing unmeasured.
- **I-99** `heimdall plot --suggest-data-map`: lines matched by name, to check and paste.
- **I-100** `heimdall run --check`: each tool's cheap preflight, never opening a FIFO.
- **I-101** `--explain KEY`: the layer that set a value.
- **I-102** Products that identify themselves; a SQLite index of provenance.
- **I-103** Physics set-ups: an ep Delphes card (ATLAS's finds a jet in 0.9 % of events), Herwig photoproduction, a Geant4 module.
- **I-104** A tool's private dependencies (BeAGLE): `private = [...]`, set aside 2026-10-15.
- **I-105** Leftovers: `migrate --stamp`; HTCondor and PBS; "F8 `--more`", undescribed: confirm or drop; `--plan`'s "note: folder 01" wording is cryptic.
- **I-140** One ask channel to a running worker: `runs/<id>.ask.json` and one signal for every non-destructive ask (jobs, dispatch, forget, pause), where today stop, pause and jobs are signals and dispatch a file polled every 5 s; then a two-way watch socket could carry the same asks.
- **I-141** One wait helper, `runs.wait_for(predicate, every, deadline)`, for the ten polling loops that wait on the registry.
- **I-142** `heimdall docs --drift` flags a code cite of a superseded `V<n>`.
- **I-143** `heimdall runs --queued-to M` on a run already queued: move it within or between queues.
- **I-144** `notify = "command"`: a run detached over ssh notifies by the user's own command (mail, ntfy, a webhook); `notify-send` needs a desktop.
- **I-145** Cost estimates from the records: the median duration and size of complete points with the same tools, scaled by events, in `--plan`, `runs` (an ETA) and `status`.
- **I-146** The library beyond generation points (combine groups, post stages, across Assignments), and its follow-ups: whether `results/` links are still needed, `record.FORMAT` 1 (an older Heimdall takes a library point as stale), an adopted Run's plot document naming the old identities.
- **I-147** `heimdall du`: the sizes of `records/`, `results/`, `.cache/` and the library, per Assignment and Run, with what `clean` and `library prune` would free.
- **I-148** Paint's statistics totals, now that `stats/` computes the same from the measured bins: drop them, or keep them as the check.
