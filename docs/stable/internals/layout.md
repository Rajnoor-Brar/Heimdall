---
id: layout
summary: Heimdall's folders, the machine root's and a work dir's; what is in git; how the roots are found; where a run's files go
code: framework/runner/paths.py, framework/templates/work, gjallarhorn.sh
---

# Layout

Three roots. **Heimdall** (`$HEIMDALL`) is a git repository: what is authored, nothing built. The **machine root** (`$HEIMDALL_MACHINE`, by default `~/Himinbjorg`) holds what this machine built, outside git. A **work dir** holds a study.

## Heimdall

| Path | Holds |
|---|---|
| `gjallarhorn.sh`, `launch.sh` | the environment, bash only: sets `HEIMDALL`, the machine root and the loaded stack (`HEIMDALL_INSTALL`, `HEIMDALL_VENV`, `HEIMDALL_BASE`, `HEIMDALL_APPS`, `HEIMDALL_FORGE`, `HEIMDALL_STACK`), then sources `env/heimdall_env.sh`. `launch.sh` is it from any shell |
| `recipes/` | how the stack is built: `build_stack.py`, `machine.py`, `verify.py`, `toolkits/`, `settings.toml`, `base.toml`, `patches/`, `platforms/` |
| `env/` | `heimdall_env.sh`, `flags.sh`, `stack.toml` and `stack.py` (each library's flags and version) |
| `framework/bin/` | `heimdall`, `bifrost`, `run` |
| `framework/runner/` | the runner, one flat package: [runner](runner.md) |
| `framework/tools/<tool>/` | the tool folders: [tool-contract](tool-contract.md) |
| `framework/plot/` | the backends besides Paint (`mpl/`, `yoda/`) and the figures' plugins (`figures/`) |
| `framework/schema/` | `run.toml`, `v3.toml`, `report.toml`, `quantities.toml` (the vocabulary), `latex.toml`; the editor's JSON schemas, generated |
| `framework/templates/work/` | what `heimdall setup` lays down |
| `framework/rules.mk`, `work.mk`, `heimdallkit.py` | the build's rules; a work dir's build; the kit for a Python exec tool |
| `src/` | the C++: `Status.hh`, `Kit.hh`, `Module.hh`, `PythiaRun.hh`, `App_*.cc`, `Apps/Paint/` with `base.toml` |
| `tests/` | `runner/`, `integration/`, `cxx/`, `fixtures/work/`, `reference/`: [testing](testing.md) |
| `editor/` | VS Code tooling: `cmnd-syntax/`, `heimdall-contrast-theme/`, `heimdall-icons/`, `icon-bank/` |
| `docs/`, `.plans/` | [writing](../../rules/writing.md), [work](../../rules/work.md) |

v1 is at High-Energy's tag `rework/v1-final`, and Heimdall's history before its import commit is High-Energy's (`split/base`): consult it there, never restore it wholesale.

## The machine root

| Path | Holds |
|---|---|
| `base/` | the conda base: `pixi.toml` (from `recipes/base.toml`), `pixi.lock`, `.pixi/envs/default/` (`$HEIMDALL_BASE`), `activate.sh`, `pkgconfig/` |
| `stack/` | the installed stack: a folder per package, `.stamps/` |
| `venv/` | with `base = "system"`, or in an older root: the Python environment |
| `apps/` | compiled apps (`$HEIMDALL_APPS`): `App_*.exe`, `Paint.exe`, `Herwig/` |
| `forge/` | `$HEIMDALL_FORGE`, disposable: `downloads/`, `pixi/`, `src/`, `build/<pkg>/`, `logs/`, `make/`, `tests/`, `scratch/`, `retired/`, `docs/` |
| `stacks/<toolkit>/` | an isolated toolkit's own stack, base, forge, apps and `gjallarhorn.sh` |
| `machine.toml`, `machine.sh`, `recipes.toml`, `toolkits/`, `tools/` | this machine's settings, shell lines, recipes, toolkits and tool folders. **Live state**: see [invariants](../../rules/invariants.md) |
| `workdirs.toml` | the work dirs this machine knows, by title |
| `runs/` | the run registry (`$HEIMDALL_RUNS`): `<id>.json`, `<id>.log`; kept 30 days; nothing is written in a read-only root |
| `images/` | Apptainer images |

Several checkouts may share one machine root. `recipes/machine.py adopt` moves an older checkout's stack in.

A record names a file under a known root by that root's placeholder, never its absolute path: `{apps}`, `{stack}`, `{base}`, `{work}`, `{machine}`, `{heimdall}`, and the point's `{out}` and `{res}` (`paths.portable_texts`). Identities do the same: [identity](identity.md).

## A work dir

Made by `heimdall setup <dir>`. Its meaning for a user is in [outputs](../guide/outputs.md).

| Path | In git |
|---|---|
| `heimdall.toml`: the marker. `[work] name`, `[framework] expects`, `[cluster]`, `[run] keep`; any other key is refused | yes |
| `Makefile`: one line, `include $(HEIMDALL)/framework/work.mk` | yes |
| `configs/<A>/`, `modules/<A>/`, `datasets/` | yes |
| `build/`, `records/`, `.cache/`, `results/`, `reports/` | no |

## How the roots are found

- `heimdall_root()` is where the code is. A `$HEIMDALL` naming another folder is refused ("two Heimdalls"), so a shell loaded for one never runs another's code against its stack.
- `work_root()` is `$HEIMDALL_WORK`, or the first folder up from here whose `heimdall.toml` has `[work]`. Markers under Heimdall's `tests/` are skipped. Outside a work dir, a command that needs one fails, naming `heimdall setup`.
- `{repo}` is refused, naming `{work}` and `{heimdall}`.
