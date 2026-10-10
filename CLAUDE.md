# Heimdall: rules for agents

## Plan approval

- During planning, do not solicit go-ahead or ask to proceed; transition to implementation only when
  the user explicitly triggers it (e.g. "Implement the plan").
- Save the plan progressively to `bots/current_plan.md` during planning, to avoid loss on context
  reset.
- Future roadmaps and intent notes go in `bots/intent.md`.

## Layout

Heimdall is the framework **and** the machine's home: `$HEP` is this folder
(docs/framework/01_Target.md §2). The manual's index is [docs/README.md](docs/README.md).

| Path | Holds |
| --- | --- |
| `setup.sh` | the environment (`load_hep` = `source <Heimdall>/setup.sh`) |
| `recipes/` | the stack's recipes: `build_stack.py`, `packages.toml`, `settings.toml`, `patches/`, `platforms/{mac,container}/` |
| `env/` | `hep_env.sh`, `flags.sh`, `stack.toml`, `stack.py`; `venv/` (ignored), `machine.sh` (ignored) |
| `framework/` | `bin/` (`hep`, `run`), `runner/` (the Python package), `tools/<folder>/` (the tool folders, backends, figures), `schema/`, `templates/work/`, `work.mk`, `hepkit.py`; `Apps/` (ignored: the compiled apps) |
| `src/` | the C++ kits (`Status.hh`, `Kit.hh`, `Module.hh`, `PythiaRun.hh`) and the apps' sources (`App_*.cc`, `Apps/Paint/`) |
| `docs/` | the manual `01`–`07`, `reporter/`, `audit_2/`, `framework/` (the setup plans) |
| `bots/` | `current_plan.md`, `intent.md`, `archive.md` |
| `tests/` | `runner/`, `integration/`, `cxx/`, `reference/`, `fixtures/work/` (the frozen work dir the tests use) |
| `stack/`, `forge/`, `stash/` | ignored: the installs; builds in progress (and the tests' scratch); downloads |

Work dirs (configs, modules, results) live elsewhere, one per workspace, made by `hep setup <dir>`.

- v1 is at High-Energy's tag `rework/v1-final`, and Heimdall's history before its import commit is
  High-Energy's (`split/base`): consult it there, never restore it wholesale.

## Never

- **Never `git clean -x` here.** It would delete `stack/`, `env/venv/` and `framework/Apps/`: hours
  of building. `forge/` and `stash/` may be emptied by hand.
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
  `HEP_REPORTS` (tests/conftest.py). Never name a real work dir in a test.
- The gates compare against `tests/reference/`: the legacy pipeline's cards, base card and YODAs,
  and `point_counts.toml`. Never regenerate them.
- A fake in a test has the real type (ledger L26).
- If a test run is interrupted or fails, do not restore paths automatically. Report the state to the
  user and wait for instruction.
- One pytest session at a time: the basetemp `forge/scratch/pytest` is wiped per session.
- Never rely on the locale default encoding: reading a YODA file resets `LC_ALL` to `C` (L17), so name
  `encoding="utf-8"` on every text read and write.
