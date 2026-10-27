# `hep` → `heimdall`: the framework's names (I-109)

Asked by the user on 2026-10-27, after I-108: "migrate all 'hep' references to 'heimdall'". This file holds the
inventory (§1), the proposal (§2), the decisions it needs (§3) and the execution map (§4), written progressively.
Nothing is renamed until §3 is answered.

## 1. Inventory (main at `63c28ea`, `git grep`)

| Kind | What | Uses | Who reads it |
|---|---|---|---|
| **A. The framework's environment** | `HEP` (Heimdall's folder), `HEP_MACHINE`, `HEP_WORK`, `HEP_RESULTS`, `HEP_RECORDS`, `HEP_CACHE`, `HEP_REPORTS`, `HEP_RUNS`, `HEP_WORKDIRS`, `HEP_FORGE`, `HEP_APPS`, `HEP_CONFIGS`, `HEP_INSTALL`, `HEP_BASE`, `HEP_STACK`, `HEP_VENV`, `HEP_ENV_LOADED`, `HEP_OUTPUT`, `HEP_STACK_REQUEST`, `HEP_DETACH`, `HEP_CLUSTER_JOB`, `HEP_SETUP`, `HEP_LOGS`, `HEP_PLAIN`, `HEP_BUILD_SH`, `HEP_KIT`, `HEP_FW`, … (about 30) | runner 75, `env/` 59, `recipes/` 92, `gjallarhorn.sh` 24, Makefiles 23, tests 254, docs 399 | the runner, the shell (`gjallarhorn.sh`, `launch.sh`, `env/`), `build_stack.py`, `rules.mk`, `work.mk`, the container, cluster job scripts; **every work dir's `Makefile`** (`ifndef HEP … include $(HEP)/framework/work.mk`) |
| **B. The tool contract** | `HEP_CONTEXT` (a point's `context.toml`), `HEP_STATUS_FD` (the status pipe), `HEP_MAKELIBS_JOBS` (Sherpa's prepare) | about 100 | **compiled readers:** `src/Module.hh`, `src/Status.hh`, so App_Pythia and every module program; `framework/hepkit.py` (Python modules); tool folders' `tool.toml`; every record's `commands.sh` |
| **C. Files** | `hep.toml` (a work dir's marker), `env/hep_env.sh`, `framework/hepkit.py` | 142, 77, 72 | the runner, `heimdall setup`, every work dir (Brookhaven's, High-Energy's, the fixture's), modules that `import hepkit` (Brookhaven's `delphes_jets.py`), `recipes/platforms/mac/mac.toml` |
| **D. Python and shell names** | `HepError` (943), `hep_root` (122), `HEP_VAR`, gjallarhorn's `hep_run`, `hep_ok`, `hep_status`, `hep_refresh`, `hep_stash`, `hep_cd`, …, a recipe's `{hep}` placeholder | about 1200 | Heimdall; `HepError` also by tool folders' plugins (25 in `framework/tools/`, and any work dir's or machine root's `tools/`) |
| **E. Editor** | `editor/hep-contrast-theme/`, `editor/hep-icons/` (VS Code extensions, installed by id) | 2 | the user's VS Code |
| **F. Physics, not Heimdall** | HepMC (190), HepForge, "HEP" for high-energy physics in prose, `runner/hepfiles.py` (the HEP file formats: YODA, `.plot`) | — | — |
| **G. History** | 07's rows, `docs/audit_*`, `docs/reporter/`, `docs/conda/`, `docs/framework/01_Target.md`, done plans in `.plans/`, the old CLI's `hep` | — | — |

**Outside Heimdall** (read only for this inventory, never written without asking):
- **the machine root:** `machine.toml` and `recipes.toml` name `$HEP_MACHINE` and `hep.toml` in comments only;
  nothing there is read under a `HEP_` name;
- **work dirs:** Brookhaven's and High-Energy's `hep.toml` and `Makefile` (`$(HEP)`); Brookhaven's
  `delphes_jets.py` imports `hepkit`; High-Energy's `lambda.toml` and `generators.toml` cite `$HEP/docs/…` in
  comments; their `CLAUDE.md` and `HEIMDALL.md`;
- **`~/.bashrc`:** `gjallarhorn()` names paths only; `load_hep` (line 119) is the user's own;
- **records made so far:** `commands.sh` exports `HEP_CONTEXT` (to rerun a tool by hand).

**What moves no identity:** a point's identity hashes its tools' rendered parts, not the environment, so
exporting a second name for B reruns nothing. Rebuilding App_Pythia or a module program does move every
point that ran it (CLAUDE.md: ask first).

## 2. Decided (the user, 2026-10-27)

1. **Scope:** Heimdall's own names (A, C, D); F (physics: HepMC, HepForge, "HEP" in prose, `hepfiles`) and
   G (history) stay.
2. **The tool contract (B): renamed, and every compiled reader rebuilt now:** App_Pythia, App_yd2rt, Paint
   and the module programs (the fixture's, Brookhaven's, High-Energy's). This moves the identity of every point
   that ran App_Pythia, App_yd2rt or a module: those points rerun.
3. **A clean break, no fallback:** the old names stop working; Brookhaven and High-Energy are migrated now.
4. **E:** the editor's extensions renamed (reinstalled in VS Code by the user).
5. **The machine root:** `machine.toml`'s and `recipes.toml`'s comments updated, each backed up first; no
   setting changes.

### The names

| Old | New |
|---|---|
| `HEP` (Heimdall's folder; `$(HEP)` in Makefiles) | `HEIMDALL` |
| `HEP_<X>` (every one: `HEP_MACHINE`, `HEP_WORK`, …, `HEP_CONTEXT`, `HEP_STATUS_FD`, `HEP_MAKELIBS_JOBS`) | `HEIMDALL_<X>` |
| the shell's privates `_HEP_*`, `_hep_*`, `_hepm_*` | `_HEIMDALL_*`, `_heimdall_*`, `_heimdallm_*` |
| `hep.toml` (a work dir's marker) | `heimdall.toml` |
| `env/hep_env.sh` | `env/heimdall_env.sh` |
| `framework/hepkit.py`, `import hepkit` | `framework/heimdallkit.py`, `import heimdallkit` |
| `HepError` | `HeimdallError` |
| `hep_root()`, `HEP_VAR` | `heimdall_root()`, `HEIMDALL_VAR` |
| `{hep}` (a placeholder) | `{heimdall}` |
| `heimdall where --hep` | `heimdall where --heimdall` |
| tests' `hep_run`, `hep_ok`, `work.hep`, `hep_toml`; `hep_yoda_backend` | `heimdall_run`, `heimdall_ok`, `work.heimdall`, `heimdall_toml`; `heimdall_yoda_backend` |
| `editor/hep-contrast-theme/`, `editor/hep-icons/` and their ids, icon keys `_hep_*` | `heimdall-contrast-theme`, `heimdall-icons`, `_heimdall_*` |

**Kept:** HepMC (`hepmc`, `HEPMC*`), HepForge, `hepfiles`, StdHEP, HEPTools, `g4hepem`, `edm4hep`, the retired
`HEKIT_*` (tests of their refusal), "HEP" for high-energy physics, `tests/reference/`, and history: 07's rows,
`docs/audit_*`, `docs/reporter/`, `docs/conda/`, `docs/framework/01_Target.md`, `.plans/` plans that are done.

**Outside the repository:** the built stack bakes in none of these names (its `HEP_` and `CLHEP_` are
StdHEP's and Geant4's own). `~/.bashrc`'s `gjallarhorn()` names `gjallarhorn.sh` and `launch.sh`, whose names
stay. Every open shell must load the environment again (`gjallarhorn`).

## 3. Phases

Built in a worktree, branch `names` (from main at `63c28ea`); main fast-forwarded at N4. Each phase tested
light and committed by named paths.

| Phase | What | Then |
|---|---|---|
| N1 | the rename in Heimdall: the code (runner, `bin/`, tools, `src/`, `env/`, `recipes/`, Makefiles, templates, container, editor), its tests and fixtures, the docs (00–06, the setup runbook, CLAUDE.md, open issues), 07's V213 | the fast and slow suites |
| N2 | main fast-forwarded; every compiled reader rebuilt (App_Pythia, App_yd2rt, Paint; the fixture's modules by the tests; Brookhaven's and High-Energy's by `heimdall build`) | straight on |
| N3 | the work dirs migrated (each one's `heimdall.toml`, `Makefile`, `CLAUDE.md`, `HEIMDALL.md`, `{hep}`, `import hepkit`, comments), left uncommitted for the user; the machine root's comments, backed up | `heimdall ls`, `check` in each |
| N4 | the extensions' `.vsix` rebuilt; this plan's log, memory | **pause** |

## 4. Execution map

| Phase | V-row | Commit | State |
|---|---|---|---|
| N0 this plan, I-109 | — | | decided 2026-10-27 |

## 5. Log

- 2026-10-27, **N1** (V213), in the worktree, branch `names`:
  - **The sweep** (`scratchpad/names_sweep.py`, its rules §2's table): 184 files, then by hand what a rule
    cannot tell: the venv's `(HEP)` prompt kept (the physics stack); `support.HEP` → `HEIMDALL`; local `hep`
    variables (one f-string had read `{hep}` as the placeholder); runtime names (`heimdall-watch-<pid>`, threads,
    `heimdall-runs-<uid>`, Slurm jobs); Whizard's `# heimdall:`; the extensions' display names.
  - **Found on the way:** no identity holds `{hep}` or `HEP_` (Brookhaven's 579 `identity.json`; I-27 had said
    they did), and the recipes' stamps hash none of the names, so the stack is not marked. `RETIRED`'s
    `HEP_OUTPUT` and `HEP_LOGS` (retired names) had been swept: kept as they were; every renamed `HEP_*` is
    retired too (`OLD_NAMES`), `heimdall_env.sh` unsets them, the test session drops them.
  - **`heimdall migrate --names`**, for any work dir from before: limited to the top-level files, `.vscode/`,
    `configs/`, `modules/` and `*.code-workspace` (High-Energy's `docs/Untitled-1.md` uses `$HEP` for the old
    `~/HEP` stack: not Heimdall's); the old CLI name `hep <command>` too.
  - **Tests**, with the apps built from the branch into `scratchpad/apps-names/`: the fast suite 1100 passed, 10
    skipped, 1 failed (the old `test_stack_build` one; 25 more cases: `RETIRED`'s new names). The slow suite: the
    5 known, and 6 more of the mixed set-up: `test_modules_p4`'s 5 (the fixture's modules were not rebuilt: their
    deps name main's `Module.hh`; pass once `forge/scratch/work/build/` is cleared) and `test_cluster_emulated`
    (`gjallarhorn.sh` gives a job the machine root's apps, built before: its points ran the old App_Pythia, so
    `status` saw another identity; again at N2, with the apps rebuilt).
