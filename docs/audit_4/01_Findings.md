# 01 — Findings

Each finding has an id (G1…), what was seen and where, and what would settle it. "Checked" says how it was
seen on 2026-10-15, at `d9d6374`. Findings of earlier audits that are still open are carried here once
(G9), with today's state.

## 1. Present, but not documented or not used

**G1. Definitions nothing uses.** Checked: every module-level name in `framework/`, `recipes/` and `env/`,
counted in all code and scripts outside its own definition.
- `deck.deck_dir` (a wrapper of `deck_dirs`), `plot.BACKENDS`, `setup.REFRESHED` (the list `refresh` does
  not read), `figures/layout.TILED` and `tools.ENV` (the tool search path replaced it, V125) are named
  nowhere else.
- `paths.forge_dir` is used by tests only.

Settle: delete them, or use `REFRESHED` in `refresh`.

**G2. Switches the code honours and the manual does not name.** Checked: every environment variable the
code reads, against 02, 04, 05, 06 and recipes/README.
- `HEP_PLAIN` turns off the stack build's live progress; `NO_COLOR` turns off colour in `heimdall doctor` and
  the build.
- `APPTAINER_CONTAINER` and `SINGULARITY_CONTAINER` decide whether provenance records an image (V150).
- `HEP_ENV_LOADED` and `HEP_STACK_REQUEST` are the shell's own bookkeeping, and need no row.

Settle: rows in 05 §2's table for the first four.

**G3. Shell helpers named only by `heimdall_help`.** `heimdall_stash`, `heimdall_forge` and `heimdall_stack`
`cd` to the downloads, the builds and the installs. The manual never names them, and `heimdall_stash` is
named after `stash/`, which became `forge/downloads/` at V122. Settle: name them in 02 §1.1, or drop them
(`cd $HEP_FORGE` says the same); rename `heimdall_stash`.

**G4. A CI workflow that has never run.** `.github/workflows/stack.yml` (V120: "a second machine in the
loop") starts only by hand, and GitHub lists no run of it. It builds the stack through
`recipes/platforms/container/Dockerfile`, which nothing else uses since Apptainer images (V150). Settle:
run it once, or retire the workflow and the Dockerfile (an Apptainer image on a second machine is the
same check).

**G5. The project master: v1's form, for a second way to do one thing.** `[file].master` names a
`configs/<project>/master.toml` whose `[quantities.<tool>.compatible_quantities]` overlay how a tool
takes a quantity (04 §3). A work dir's own tool folder that `extends` the shipped one does the same in
today's form (V125). No fixture config and no ported study uses a master. Internally, `load_master` still
builds v1's `compatible_quantities` shape out of every folder's flat `quantities.toml`. Settle: retire the
master, with a `heimdall migrate` rewrite into a work dir tool folder; or keep it and say when to use which.

## 2. Abandoned halfway, or not fully developed

**G6. `[cluster] image` is half a way.** Found in the cleanup pass of 2026-10-14. The jobs run in the
image, but `heimdall cluster` plans every point on the login node, outside it, and planning reads the PDF
sets, Rivet's data and the card checker; inside the image there is no `sbatch`. The docs state the limit.
Settle (a design): plan inside the image and have it write a `submit.sh` the host runs, chaining the job
ids itself; or bind the site's Slurm client into the image.

**G7. Recipes and toolkits never built.** `recipes/toolkits/standard.toml` has 25 recipes with
`status = "new"`: written from each project's instructions, never proven by a build. Among them are
MadAnalysis5, Contur, Professor, JETSCAPE, the Key4hep set and the GPU simulation set. The record shows
builds of `@primary`, `@lab` and `@core-conda` only. `@bsm-models`, `@bsm-recast`, `@cms`, `@detector`,
`@exclusive`, `@fixed-order`, `@fluka`, `@gpu-sim`, `@heavy-flavour`, `@heavy-ion`, `@key4hep`,
`@key4hep-src`, `@tuning`, `@data`, `@generators`, `@generators-conda`, `@lab-conda` and
`@primary-conda` were planned and dry-run (`test_stack_build.py`), never built. A recipe is marked
(`heimdall stack list` says "recipe not yet proven by a build", recipes/README explains `status =
"new"`); a toolkit is not, so `@heavy-ion` reads as ready as `@primary`. Settle: mark a toolkit no build
has proven (where toolkits are listed), prove the ones the user needs, and prune those nobody will.

**G8. Two 1D plot backends for one purpose (audit 2's H11, pending since V71).** `framework/plot/yoda/`
(mkhtml) and `framework/plot/mpl/` both draw 1D pages, and mpl follows mkhtml. The removal of the yoda
backend waits on the user comparing mpl's pages with mkhtml's. Settle: that comparison (R0), then one
backend.

**G9. Audit 2's findings still open.** Re-checked today:
- **Still true:**
  - H3: the hint at `cli.py:932` tells the user to run `heimdall plot FILE…`, which became `heimdall
    overlay` at V74, and `plot.py:1230`'s section comment says the same.
  - H8: `plot.objects_of`, `raws_of`, `_sha` and the alias `base_of` are still wrappers.
  - H10: `figures(run)` is parsed at 9 call sites per draw.
  - H7: the stamp-beside-target pattern still appears 5 times.
  - H2, H5, H6, H9, H13, H14, H15 and H16 were not re-measured.
- **Resolved:** H1 (`ep_validation.cmnd` is tracked in the fixture), H4 (High-Energy's configs, not
  Heimdall's), H12 (no hard-coded sheet size in `figures/layout.py`).

Settle: H3 and H8 are small fixes; the rest is audit 2's R1–R3.

**G10. `bots/intent.md` says what is not true.**
- Its header says "None of this is implemented", yet T3 and T5 are struck through as built.
- F11, F12 and F13 are listed with fixes to make, but the code no longer has them: no `render = "fn"`, no
  `"prepend"` card style, no `[defaults] last_line`.
- CF4 ("a machine file") is `machine.toml`. U5 (completion) exists for `gjallarhorn`'s titles.
- F14 concerns the old lab PC's venv, which the reinstall removed.

Settle: close those rows, and keep the open ones.

**G11. Built, never run on a real system.** These are recorded in bots/current_plan.md and listed here so
the audit is whole:
- an Apptainer image (the tests use a fake runtime);
- tasks A–E on the Mac;
- a real Slurm (an emulated one only);
- Rivet, ROOT and Pythia built from source on the conda base;
- the tracked multi-platform lock;
- the generators' slow tests, which fail on the old system's libraries (exit 127).

Settle: the new machine's first build and slow suite.

## 3. Deprecated, but lingering

**G12. The v2 run TOML, and its names in a v3 user's errors.** v3 files are translated into v2 and read
as v2 (V128); a file with `[file] schema = 2` stays v2 "for now" (`v3.py:65`). So the errors a v3 user
reads speak v2. Checked with a v3 file:
- `vary = ["nosuch"]` gives "sweeps names 'nosuch' …", where `[run.cfgs.a].sweeps`;
- `fixed = { nosuch = 1 }` gives "static sets 'nosuch' …", where `[run.cfgs.a].static`;
- the user wrote neither `sweeps`, `static` nor `[run.cfgs]`. "a configuration needs tools = [...]" and
  "no event_count" are the same.

Settle: messages in the file's own form (the v3 name when the file is v3, as `a_cfg` already does in
one place); and decide when v2 input retires (`tests/reference/v2_configs/` pins it today).

**G13. Migrations that are done, still shipped.**
- `framework/runner/migrate.py` (839 lines) rewrites v1's `[master]` into `[config]` and `{repo}` into
  `{work}`; renames tools (`formerly`); converts exports and v2 into v3 (`--v3`); and moves `output/` into
  `records/`, `logs/` and `.cache/` (`--layout`, V132).
- `recipes/machine.py adopt` moves a stack out of a checkout (V122); CLAUDE.md's rule about an "un-adopted
  stack" protects the same case.
- `labels.py` converts TLatex labels "(configs not yet migrated)".

After the reinstall no checkout holds a stack, and the fixture and the ported study are v3. Settle: run
`heimdall migrate` (a dry run) over every recognised work dir. If nothing is left to migrate, retire
these paths, keeping the refusals that name the new form.

**G14. Guards against retired names.**
- `HEKIT_*` variables (`paths.check_retired`, `env/hep_env.sh`; K15);
- `{repo}` (`tools.py:307`);
- the `pythia_cmnd`-style export keys (`tools.py:59`);
- `HEP_SETUP` (`hep_env.sh:28`);
- a tool folder's former name (`[tool] formerly`);
- the v2 key names a v3 file is refused for (`v3.RUN_RENAMED`, `QUANTITY_RENAMED`).

Each costs a few lines and turns a stale shell or file into a clear error. Settle: keep them for a set
time, then drop the oldest (High-Energy's `HEKIT_*` and `{repo}` date from the split).

**G15. Old entry points beside new ones.**
- `heimdall doctor` is `heimdall stack doctor`, and `heimdall status --stack` is `heimdall stack status`.
  The `stack` noun gathered them (U60); the old ones stayed.
- The shell keeps `heimdall_status` "for a release", and `quit`, `heimdall_cd` and `heimdall_refresh` as
  old names.
- `recipes/platforms/mac/launch.sh` passes on to `launch.sh` "for a release" (V124).

Settle: one name each; the old ones say the new name for one release, then go.

**G16. `recipes/build_by_hand.txt` has drifted.**
- It downloads Pythia 8317 from `pythia.org/download/`, which returns 404 since 2026; the recipe is 8318,
  from `/releases/`.
- It knows nothing of the conda base (V140).

Nothing in the manual points to it; `build_stack.py --dry-run` prints the same build as a script, from
the recipes, always current. Settle: retire it, pointing to `--dry-run`.

**G17. `{repo}` means two things.** The runner refuses `{repo}` as retired (High-Energy's name). The
recipes still use `{repo}` for Heimdall's checkout (`standard.toml`: `{repo}/recipes/helpers/h5cc_plain.py`).
Settle: `{hep}` in the recipes too, as the runner says.

## 4. Hard to discern its purpose or usefulness

**G18. The `plotmerge` tool.** It writes, as a post tool, the file the plot stage already makes
(`plots/root/<cfg>.root`). 05 §8 gives its use as "a copy elsewhere, or a YODA version". No fixture
config or study uses it; one integration test does. Settle: drop it, or say in 05 when one would want it.

**G19. Verbs that overlap.**
- For the stack and packages: `heimdall stack build|list|status|doctor`, `heimdall doctor`, `heimdall
  status --stack`, `heimdall tools` (each tool built, ready-made or missing), `bifrost` (the base's packages;
  `-c`/`-b` switch a recipe), `heimdall image build`, and the shell's `heimdall_status`.
- For compiling: `heimdall build`, `heimdall make`, and `--framework` on both.

Each is documented, but nothing says which to reach for. Settle: retire the duplicates (G15), and put one
"which command" table in 00 and 05.

**G20. The stack's settings are in five files.**
- `recipes/settings.toml` (defaults), `recipes/base.toml` (the conda base) and `recipes/toolkits/*.toml`;
- the machine root's `machine.toml` and `recipes.toml` (its own recipes);
- and `machine.sh` beside them.

`machine.toml` alone holds four concerns: build settings, where each package comes from, the base's added
packages, and `[run]`/`[cluster]` defaults. The precedence is in recipes/README, but scattered. Not a
defect. Settle: one map of the files and who writes each, in recipes/README §1.

**G21. `framework/bin/run` beside `framework/bin/heimdall`.** The Python entry point is named `run`, the
word of `heimdall run`; `heimdall reproduce` calls it by path. Settle: a name that says what it is, or
leave it (low).

**G22. What is left of `hep` after the rename (V142, on purpose).** `hep.toml` (the work dir's marker),
`$HEP` and every `HEP_*`, `hep_root()`, `{hep}`, `env/hep_env.sh`, the shell's `_hep_*`, `hepkit`. These
were kept on purpose, but a newcomer meets two names: the command `heimdall` and the marker `hep.toml`.
Settle: keep them, said once in 01; or rename the user-facing ones (`hep.toml` → `heimdall.toml`, read
either way for a release).

**G23. The support matrix's one row is the old machine's.** `recipes/support/linux-pp-exphep.toml`
(`heimdall doctor --record`, 2026-10-12) describes a system the reinstall removed. Settle: record the new
machine, and drop or date the old row.
