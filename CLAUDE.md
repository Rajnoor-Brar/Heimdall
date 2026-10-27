# Heimdall: rules for agents

## Plan approval

- During planning, do not solicit go-ahead or ask to proceed; transition to implementation only when
  the user explicitly triggers it (e.g. "Implement the plan").
- Pending work is [.plans/ISSUES.md](.plans/ISSUES.md), one issue per task. An idea is an issue labelled `idea`.
- Plans, audits and plan execution maps go in `.plans/` (the default place, the user's rule of
  2026-10-25). Write one progressively while planning, to avoid loss on context reset, and link it
  from the issue it serves.
- A finished issue is deleted from `.plans/ISSUES.md`: its history is its V-row in docs/07_Record.md and its
  commit.

## Ask first

- Never push. Name a download's file, source and size before fetching it.
- Rebuilding App_Pythia, App_yd2rt, a module program or a Rivet plugin changes the identity of every
  point that ran it (Paint is plot-only and safe).
- The machine root holds live state: never rewrite its `machine.toml`, `recipes.toml`, `toolkits/` or
  `tools/`, and back up any live file before changing it.
- Start a long build detached (`setsid nohup … < /dev/null &`), or a session's end kills it.
- After changing a schema key's `doc`/`notes`, base.toml's comments or the CLI's help, run
  `heimdall make --framework docs schema`.

## Layout

Heimdall is the framework: `$HEP` is this folder, what is authored, nothing built (V105, V122; the manual's
[06 §1](docs/06_Internals.md#1-layout-heimdall-and-work-dirs)). The manual's index is
[docs/README.md](docs/README.md); setting Heimdall up on a fresh machine is [docs/framework/](docs/framework/README.md).

| Path | Holds |
| --- | --- |
| `gjallarhorn.sh`, `launch.sh` | the environment, bash only (`source <Heimdall>/gjallarhorn.sh [title]`; the shell function `gjallarhorn [title]` the build writes into ~/.bashrc); `launch.sh` is it from any shell |
| `recipes/` | the stack's recipes: `build_stack.py`, `base.toml` (the conda base), `toolkits/` (`standard.toml`: every recipe; one file per toolkit), `settings.toml`, the machine's templates, `patches/`, `platforms/{mac,container}/` (`container/heimdall.def`: the Apptainer image) |
| `env/` | `hep_env.sh`, `flags.sh`, `stack.toml`, `stack.py` |
| `framework/` | `bin/` (`heimdall`, `bifrost`, `run`), `runner/` (the Python package), `tools/<folder>/` (the tool folders), `plot/` (the plot backends and figures), `schema/`, `templates/work/`, `rules.mk`, `work.mk`, `hepkit.py` |
| `src/` | the C++ kits (`Status.hh`, `Kit.hh`, `Module.hh`, `PythiaRun.hh`) and the apps' sources (`App_*.cc`, `Apps/Paint/`) |
| `docs/` | the manual `00`–`07`, `framework/` (the setup runbook), `conda/` (the base's design), `reporter/` (the retired decks' plan, history), `audit_2/`, `audit_3/`, `audit_4/` |
| `.plans/` | `ISSUES.md` (pending work, one issue per task); plans, audits and plan execution maps (`restructure_plan.md`, `run_logging_audit.md`, `run_logging_plan.md`, `statistics_a4_plan.md`, `report/`: `heimdall report`'s audit and phases, `heimdall_names.md`: I-109) |
| `tests/` | `runner/`, `integration/`, `cxx/`, `reference/`, `fixtures/work/` (the frozen work dir the tests use) |
| `editor/` | the VS Code tooling: `cmnd-syntax/` (Pythia `.cmnd` highlighting), `hep-contrast-theme/`, `hep-icons/`, `icon-bank/` (from High-Energy's `aux/` at 2c4fcad) |

What this machine built is in the **machine root**, `~/Himinbjorg` (`$HEP_MACHINE`), outside git:
`base/` (the conda base; `venv/` in an older root), `stack/`, `apps/` (`$HEP_APPS`), `forge/` (`$HEP_FORGE`:
downloads, sources, builds, logs, the tests' scratch), `stacks/<toolkit>/`, `images/` (Apptainer images),
`machine.toml`, `machine.sh`, `recipes.toml` (its own recipes), `workdirs.toml` (`heimdall recognise`),
`runs/` (the run registry, `heimdall runs`), `toolkits/`, `tools/`. `recipes/machine.py adopt`
moves an older in-checkout stack there.

Work dirs (configs, modules, results) live elsewhere, one per workspace, made by `heimdall setup <dir>`.

- v1 is at High-Energy's tag `rework/v1-final`, and Heimdall's history before its import commit is
  High-Energy's (`split/base`): consult it there, never restore it wholesale.

## Never

- **Never `git clean -x` here** while a checkout still holds an un-adopted stack (`stack/`, `env/venv/`,
  `framework/Apps/`): hours of building. The machine root's `forge/` may be emptied by hand.
- Never `git commit -a`: stage named paths.

## Code design

- C++ in `src/` is a few headers and apps. There are no library namespaces (V7). A header holds one
  PascalCase namespace, checked against the installed toolchain (X11 defines `Status`), with
  `camelCase` functions and no `using namespace` of external libraries at namespace scope.
- A source declares what it links in a `// requires: …` line near the top.
- The Python runner is one flat package, `framework/runner/`. A module imports only from lower ranks
  (docs/06_Internals.md §2.1), and `tests/runner/test_imports.py` enforces it.
- Everything the runner knows about a tool lives in its folder (`framework/tools/<tool>/`, or a work
  dir's or the machine root's `tools/`). The runner core never names a tool.
- Before writing code for a tool, read its rows in the knowledge ledger (docs/07_Record.md §3).

## Testing

- Tests write only `forge/scratch/`, through `HEP_WORK`, `HEP_RECORDS`, `HEP_CACHE`,
  `HEP_RESULTS`, `HEP_REPORTS`, `HEP_WORKDIRS` and `HEP_RUNS` (tests/conftest.py). Never name a real work dir in a test. Run them with the stack
  loaded (`source gjallarhorn.sh`): the session builds the fixture work dir's modules first.
- The fixtures (`tests/fixtures/work/`) change only together with the test that needs the change.
- The gates compare against `tests/reference/`: the legacy pipeline's cards, base card and YODAs,
  and `point_counts.toml`. Never regenerate them.
- A fake in a test has the real type (ledger L26).
- If a test run is interrupted or fails, do not restore paths automatically. Report the state to the
  user and wait for instruction.
- One pytest session at a time: the basetemp `forge/scratch/pytest` is wiped per session. Run them
  light (`taskset -c 0-5 nice`), and the slow suite on its own.
- Never rely on the locale default encoding: reading a YODA file resets `LC_ALL` to `C` (L17), so name
  `encoding="utf-8"` on every text read and write, text-mode subprocesses included.
