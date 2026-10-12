# Heimdall: rules for agents

## Plan approval

- During planning, do not solicit go-ahead or ask to proceed; transition to implementation only when
  the user explicitly triggers it (e.g. "Implement the plan").
- Save the plan progressively to `bots/current_plan.md` during planning, to avoid loss on context
  reset.
- Future roadmaps and intent notes go in `bots/intent.md`.

## Layout

Heimdall is the framework **and** the machine's home: `$HEP` is this folder (V105; the manual's
[06 §1](docs/06_Internals.md#1-layout-heimdall-and-work-dirs)). The manual's index is
[docs/README.md](docs/README.md); setting Heimdall up on a fresh machine is [docs/framework/](docs/framework/README.md).

| Path | Holds |
| --- | --- |
| `setup.sh`, `launch.sh` | the environment, bash only (`source <Heimdall>/setup.sh`); `launch.sh` is it from any shell (`load_hep`) |
| `recipes/` | the stack's recipes: `build_stack.py`, `toolkits/` (`standard.toml`: every recipe; one file per toolkit), `settings.toml`, `patches/`, `platforms/{mac,container}/` |
| `env/` | `hep_env.sh`, `flags.sh`, `stack.toml`, `stack.py` |
| `framework/` | `bin/` (`hep`, `run`), `runner/` (the Python package), `tools/<folder>/` (the tool folders, backends, figures), `schema/`, `templates/work/`, `rules.mk`, `work.mk`, `hepkit.py` |
| `src/` | the C++ kits (`Status.hh`, `Kit.hh`, `Module.hh`, `PythiaRun.hh`) and the apps' sources (`App_*.cc`, `Apps/Paint/`) |
| `docs/` | the manual `01`–`07`, `reporter/`, `audit_2/`, `framework/` (the setup plans) |
| `bots/` | `current_plan.md`, `intent.md`, `archive.md` |
| `tests/` | `runner/`, `integration/`, `cxx/`, `reference/`, `fixtures/work/` (the frozen work dir the tests use) |

What this machine built is in the **machine root**, `~/Himinbjorg` (`$HEP_MACHINE`), outside git:
`stack/`, `venv/`, `apps/` (`$HEP_APPS`), `forge/` (`$HEP_FORGE`: downloads, sources, builds, logs,
the tests' scratch), `stacks/<toolkit>/`, `machine.toml`, `machine.sh`. `recipes/machine.py adopt`
moves an older in-checkout stack there.

Work dirs (configs, modules, results) live elsewhere, one per workspace, made by `hep setup <dir>`.

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
- Everything the runner knows about a tool lives in `framework/tools/<tool>/`. The runner core never
  names a tool.
- Before writing code for a tool, read its rows in the knowledge ledger (docs/07_Record.md §3).

## Testing

- Tests write only `forge/scratch/`, through `HEP_WORK`, `HEP_OUTPUT`, `HEP_RESULTS` and
  `HEP_REPORTS` (tests/conftest.py). Never name a real work dir in a test. Run them with the stack
  loaded (`source setup.sh`): the session builds the fixture work dir's modules first.
- The fixtures (`tests/fixtures/work/`) change only together with the test that needs the change.
- The gates compare against `tests/reference/`: the legacy pipeline's cards, base card and YODAs,
  and `point_counts.toml`. Never regenerate them.
- A fake in a test has the real type (ledger L26).
- If a test run is interrupted or fails, do not restore paths automatically. Report the state to the
  user and wait for instruction.
- One pytest session at a time: the basetemp `forge/scratch/pytest` is wiped per session.
- Never rely on the locale default encoding: reading a YODA file resets `LC_ALL` to `C` (L17), so name
  `encoding="utf-8"` on every text read and write.
