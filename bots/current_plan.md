# Current plan

**What is open:**
- [docs/audit_2/01_Health.md](../docs/audit_2/01_Health.md): findings H1–H16 and phases R0–R3, each
  step only on the user's order.
- The decisions are in docs/07_Record.md, and finished task logs in [archive.md](archive.md).

**Finished, and in git:**
- audit 1 (V52–V89, `git show 3a5ec16:docs/audit_1/06_Plan.md`);
- the figures (V80–V89);
- the manual's rebuild (V90–V92, `git show 3a5ec16:docs/audit_2/02_Manual.md`).
- `[config]` (V93–V97): it replaces `[master]`; `import` nests, crosses projects and takes `only` a part; `drop`; `vars`; `meta` (version warnings). The doc is 04 §3.
- `[run.cfgs.<cfg>]` (V98–V100): configurations moved out of `[run]`; `[run]` gives every configuration its keys (`[run.defaults]` gone); an import's location rule is per folder.
- Decks, `hep deck` (V102–V104, docs/reporter, 2026-10-10): `figures/layout.py` (sheets and composites: pdflatex, PNG by pdftoppm), `runner/deck.py` (blocks from result folders or a folder's files; composites; deck.md through pandoc to Beamer, pptx, dzslides HTML, an Overleaf zip), `runner/viewer.py`; the manual's 03 §11, 04 §15, 05 §1.8.

## Now (2026-10-14): the conda base is in; task B next, on the reinstalled lab PC

**Task A, the conda base (V140, V141; docs/conda/), committed, not pushed.** The machine root is built on
a pixi/conda-forge base by default; the tools still from source inside it; `@core-conda`, `@lab-conda`,
`@primary-conda`, `@generators-conda` take conda-forge's ready-made packages; old roots (a `venv/`, no
`base/`) stay `base = "system"`. Proven: the base and LHAPDF, HepMC3, FastJet, fjcontrib, YODA from
source in a scratch root; `@core-conda` whole (apps built, doctor, the guide's example run). Open:
- Rivet (and ROOT, Pythia 8, the rest) from source on the base: never finished here (the machine went
  down once at -j24; the user stopped the last try before the reinstall). On the new machine, the
  first `@primary` build proves them;
- the slow suite was not run on this commit (the fast suite was: 790 passed, 2 skipped);
- docs/conda/03_Plan.md phase 3 (physics against the old stack, the Mac), the tracked multi-platform
  lock, a bootstrap for clusters with Python < 3.11.

**Task B (the user's order, 2026-10-14; decisions taken, nothing of it committed):**

> have terminal call be "heimdall" not "hep". when setting up, have heimdall put in bashrc or zshrc
> "bifrost" command. bifrost loads the env (setup.sh/bifrost.sh), and "heimdall recognise" which
> recognises work dirs and if not in Himinbjorg states files, records/log it as a work dir in a toml
> file which tracks existence of work dirs. then "bifrost <work_dir_title>" loads env and cd to dit
> location

Steps, each a commit by path with the fast suite passing; the slow suite once at the end; V142 (the
command `heimdall`, `bifrost.sh`) and V143 (`recognise`, `workdirs.toml`, the rc block).

1. **The command is `heimdall`; `hep` goes, with no alias.** `git mv framework/bin/hep
   framework/bin/heimdall`, `git mv setup.sh bifrost.sh`, then [drafts/rename_b1.py](drafts/rename_b1.py)
   (regexes over the tracked files; history excluded: 07's old rows, audit_2/3, reporter/,
   framework/01_Target.md, bots/, tests/reference/, docs/conda/01–03), then by hand: `prog`, the error
   prefix `hep: ` (errors.py, build_stack.py `die()`), the shell function `hep()` → `heimdall()` and its
   `hep_*` helpers → `heimdall_*` (env/hep_env.sh), notify-send's app name, `stacks/<kit>/setup.sh` →
   `bifrost.sh` (build_stack's STACK_SETUP; cluster.py's loader), the commit message `heimdall setup: …`
   (tests: test_setup, test_workdir_repo), `make docs` (the generated CLI and schema blocks). Keep: the
   `HEP*` variables, `hep.toml`, `hepkit`, `HepError`, `where --hep`. Every `source …/bifrost.sh` that
   could inherit positional parameters passes none explicitly (launch.sh's one-command form: `source
   "$0" ""`), since bifrost.sh will read `$1` as a title.
2. **`heimdall recognise [PATH] [--as TITLE] [--list] [--forget TITLE] [--path TITLE]`**, the registry
   `<machine root>/workdirs.toml` (`$HEP_WORKDIRS` replaces it; the tests' conftest points it into
   forge/scratch). [drafts/workdirs.py](drafts/workdirs.py) → `framework/runner/workdirs.py`, rank 1
   (RANKS in runner/__init__.py; 06 §2.1). One table per title (`["<title>"] path, recognised`); the
   title is `[work] name`, else the folder's. PATH a work dir or inside one: record it; else scan below
   it (4 deep; not hidden folders, results/ records/ logs/ build/, Heimdall's checkout, the machine
   root). Known path: "known"; a title whose path is gone: replaced ("moved"); a title another existing
   work dir holds: refused, hint `--as`. `--list`: title, path, state. `heimdall setup` records what it
   makes (a clash is said, not fatal).
3. **`bifrost`.** `source bifrost.sh [title]`: the environment, then `cd "$(command heimdall recognise
   --path "$1")"` (after hep_env.sh, before the last `return 0`; an unknown title: did-you-mean,
   return 1, the environment kept). [drafts/bifrost.py](drafts/bifrost.py) → `framework/runner/
   bifrost.py`, rank 0, standard library only (build_stack.py loads it by path, as verify.py): the
   marked block `# >>> Heimdall: bifrost >>>` … `# <<< … <<<` in ~/.bashrc (`bifrost() { source
   <HEP>/bifrost.sh "$@"; }`, completion from workdirs.toml's headers) and ~/.zshrc (`bifrost() {
   <HEP>/launch.sh --bifrost "$@"; }`); `export HEP_MACHINE` only for a root not the default.
   `launch.sh --bifrost [title]`. Written at the end of a real build (setting `shell_rc`, default
   true; a block for another checkout or root is left, and said), and by `heimdall bifrost
   [--install|--remove]` (status without a flag). Files: ~/.bashrc when the login shell is bash or it
   exists; ~/.zshrc likewise. **Ask the user, showing the block, before writing the machine's real
   rc files.** Tests: HOME a temp dir; install twice gives one block; remove leaves the rest; a shell
   test `bifrost Demo` → `pwd` in the work dir with the environment loaded.
4. **Docs:** 00, 02 (setting up: bifrost), 05 (recognise, bifrost), 06 (workdirs.toml, bifrost.sh),
   README, CLAUDE.md, the template's HEIMDALL.md/README; 07 V142, V143.

**Lessons of 2026-10-14:** start a long build detached (`setsid nohup … < /dev/null &`), or a session's
end kills it; ROOT's and Rivet's compilers take ~3 GB each (`root_cores`, now Rivet's too): at every
core a 14 GB machine went down; run tests light (`taskset -c 0-5 nice`), and pytest directly rather
than `make test` (its `make all` rebuilds the machine's apps).

## Before (2026-10-10 to 2026-10-13)

**Heimdall (2026-10-10):** split from High-Energy at `split/base` (5e0a913) and built here, in its own
repository at `~/Github/Heimdall`, on the old lab PC's stack. Since V122 the machine root
`~/Himinbjorg` holds it: `stack` and `venv` are links to `~/HEP/install` and `~/HEP/.venv`, and `apps/`
and `forge/` are real folders there.
- **Done:** the seed (`99da1d3`), the recipes and toolkits (`@primary` = the lab set plus
  MadAnalysis5; isolated C++20 stacks), the seam (two roots, `hep setup`/`hep where`, the build split
  on `framework/rules.mk`, provenance across both repositories, portability), the tests on the
  fixture work dir, the manual re-rooted (V105–V113), and
  [docs/framework/](../docs/framework/README.md) rewritten as the fresh-machine runbook (P0 Preflight,
  P1 Stack `@primary`, P2 Framework, P3 Work dirs, P4 Verify).
- **Numbers here:** `hep build --framework` 4 s; 3 C++ tests pass; fast suite 629 passed; slow suite
  37 passed (about 9 min, the byte-identical legacy gate and the emulated cluster included); `test_stack_build` 27; the
  starter in a scratch Top-Quark: 2 points, 35 pages, 9 s.
- **Next, the user's:**
  - publish Heimdall (a gate: a private `Rajnoor-Brar/Heimdall`), or keep a bundle;
  - before the reinstall, 01 §8's checklist (Heimdall's bundle or push; High-Energy pushed; the
    kept files and the reference point);
  - on the new machine, the runbook from 02 §1.
- **`hep cluster` (2026-10-11, V114):** a configuration as Slurm jobs (pre job → points array →
  finish job, each an ordinary `hep run --stages …`), `[cluster]` in hep.toml, the run TOML, the
  configuration, `--set`. Tested against an emulated Slurm only: the first real submission (on a
  cluster the user has) is a by-hand check, `--dry-run` first.
- **The fixture holds no study by name:** the projects are `Demo` (ep jets, the
  validation against ZEUS 2012, the generators), `Decay` (Λ → p π⁻) and `Generators`; the physics
  and the frozen references are as they were.
- High-Energy itself is untouched (only the tag `split/base` was added); its conversion to a work
  dir is parked (06's appendix).

Otherwise nothing is in progress. Waiting on the user:

- **Audit 3** (2026-10-12, [docs/audit_3/](../docs/audit_3/README.md)): a user-experience audit after the
  first Mac build (U1–U66). Remediation in seven phases (06_Plan.md: build reliability,
  verification/`hep doctor`, the machine root `$HEP_MACHINE` and the shell, one tool system, the work
  dir's lifecycle, schema v3, the CLI and first run). Nothing built until the user orders a phase.
  The Mac build's notes and `check_stack.sh` are in the ignored `.setup/`.
- **R0:** verify the mpl pages against mkhtml's, after which the yoda backend goes (H11).
- **R1–R3** of the health check: quick fixes (a compare figure drawn once, H2), then structure
  (`runner/figures.py`, the figure-class rules in the schema), then sheets, tests and docs.
- **`hep migrate --stamp`** (the [config] plan's optional C3 S3): it would write the stack's versions into `[config.meta].versions`. Only if wanted.
- **Later**, on the user's word:
  - F8 `--more`;
  - HTCondor and PBS for `hep cluster` (Slurm is V114); an Apptainer image for its jobs;
  - Paint's PDF line widths (about 2× too thick);
  - the held C++/Rivet items (K3, K4, K7, K8, K10, yd2rt's dead parameter);
  - `extends`/`common.toml` for validation ("not now").

## Standing constraints

- **Commits:**
  - local, never pushed without the gate, with the Co-Authored-By line;
  - stage named paths only, never `commit -a`; the stack lives in `~/Himinbjorg`, outside the tree.
- **Tests:**
  - tests run in the fixture work dir's copy, `$HEP_FORGE/scratch/work/` (V52, V112), never a real one;
  - one pytest session at a time, and the slow suite not while the user's long runs share the cores;
  - `source setup.sh` (this Heimdall's) before make or pytest.
- **Approvals:**
  - the stack (`~/Himinbjorg`'s `stack/`, `venv/`; here, links to `~/HEP`) and downloads need the user's
    approval; never write into `~/HEP` or its venv;
  - a rebuilt App_Pythia, App_yd2rt, InprocJets or Rivet plugin changes the identity of every point
    that ran it, so ask before rebuilding (Paint is plot-only and safe).
- **Docs:** after changing a schema key's `doc`/`notes`, base.toml's comments or the CLI's help, run
  `hep make --framework docs schema`.
- **Way of working:** never implement without an explicit order; plans first, questions when a
  request is ambiguous.
