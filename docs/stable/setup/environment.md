---
id: environment
summary: gjallarhorn, the shell's environment, heimdall build, bifrost, recognised work dirs, every environment variable
code: gjallarhorn.sh, launch.sh, env/heimdall_env.sh, framework/runner/bifrost.py, framework/runner/workdirs.py, framework/runner/shellrc.py
---

# The environment

`source gjallarhorn.sh` in bash sets `HEIMDALL`, puts the stack and `heimdall` on `PATH`, activates the base and adds `machine.sh`'s lines. The build writes a block into `~/.bashrc` and `~/.zshrc` defining **`gjallarhorn [title]`** and `bifrost`; `gjallarhorn <title>` also goes to that work dir. In zsh it opens a bash, via `launch.sh`, which also runs one command (`launch.sh heimdall run …`) or an image's environment (`gjallarhorn --image <name>`: [images](images.md)). Another shell sourcing it is turned away. `heimdall where` says which Heimdall, stack and work dir a shell sees.

`heimdall cd ASSIGNMENT [configs|modules|results|records|logs]`, `heimdall quit` (takes out all it added) and `heimdall refresh` (`quit`, then the same stack again) change the shell, so they are the function's. Everything else works without the environment: `framework/bin/heimdall` runs the machine's Python by path, for cron, scripts and Slurm.

The base is activated first: its `bin/` on `PATH`, `CC`, `CXX`, `FC` set. Its `lib/` never joins `LD_LIBRARY_PATH`: what is built on it finds it by rpath, and the OS's own programs keep the OS's libraries.

## Building

`heimdall build [TARGET…] [--framework] [--tests] [--clean] [--configure] [-j N]` is `make all`: in the work dir, its modules and plugins into `build/`; with `--framework`, Heimdall's apps into `$HEIMDALL_APPS`. `heimdall make …` is `make` there. [build](../internals/build.md).

## `bifrost`: what is in the environment

| Command | Does |
|---|---|
| `bifrost` | shows the base, each package added, the tools, the rc block |
| `bifrost <pkg>…` | conda-forge packages into the base (`scipy`, `gsl=2.8`, `"gsl >=2.8"`), recorded in `machine.toml` |
| `bifrost -python <pkg>…` | PyPI's, by pip names, installed by pixi with the conda ones |
| `bifrost --drop [-python] <pkg>…` | takes them out |
| `bifrost -c <tool>…` | a recipe ready-made from conda-forge, with what it needs |
| `bifrost -b <tool>…` | builds it from its recipe; `-b@<toolkit>` with that toolkit's changes |
| `bifrost --shell install\|remove` | writes or removes the rc block |

- **A switch** between built and ready-made changes the programs, so recorded points run again and apps rebuild. It says how many, and asks; `--yes` otherwise. The built copy goes to `forge/retired/`.
- **Refused:** a package whose recipe the stack built (two copies would clash); a ready-made tool that needs one being built. A failure puts `machine.toml` back.
- With `base = "system"`, `-python` goes in the venv by pip; others are refused.
- It downloads.

## The work dirs this machine knows

`heimdall recognise [PATH]` records a work dir by title in `workdirs.toml`, so `gjallarhorn <title>` finds it. Another folder is searched 4 deep. `heimdall setup` records what it makes. `--as TITLE`, `--list`, `--forget TITLE`, `--path TITLE`.

## Variables

| Variable | Set by | Means |
|---|---|---|
| `HEIMDALL` | `gjallarhorn.sh` | Heimdall's folder |
| `HEIMDALL_MACHINE` | you | the machine root, if not `~/Himinbjorg` |
| `HEIMDALL_INSTALL`, `HEIMDALL_VENV`, `HEIMDALL_APPS`, `HEIMDALL_FORGE` | `gjallarhorn.sh` | the loaded stack, its Python, apps, forge |
| `HEIMDALL_BASE` | `gjallarhorn.sh` | the conda base's environment |
| `HEIMDALL_STACK` | `stacks/<toolkit>/gjallarhorn.sh` | an isolated toolkit's stack is loaded |
| `HEIMDALL_WORK` | you, tests | the work dir, instead of the walk up |
| `HEIMDALL_WORKDIRS`, `HEIMDALL_RUNS` | you, tests | replace `workdirs.toml`, `runs/` |
| `HEIMDALL_DETACH` | you | `never`: a run on a terminal stays in the command's own process |
| `HEIMDALL_CLUSTER_JOB` | job scripts | a cluster job: its run is recorded by its submission, not by itself, and stays in-process |
| `HEIMDALL_RUN_ID`, `HEIMDALL_RESUMES` | `heimdall runs --resume` | the id a detached run takes; the paused entry it resumes |
| `HEIMDALL_MAKELIBS_JOBS` | you | how many compilers Sherpa's `makelibs` runs at once (default 1) |
| `HEIMDALL_BUILD_SH` | `platforms/mac/build.sh` | on macOS, the build came through the wrapper |
| `HEIMDALL_RECORDS`, `_CACHE`, `_RESULTS`, `_REPORTS`, `_CONFIGS` | you, tests | replace the work dir's trees |
| `HEIMDALL_STATUS_FD`, `HEIMDALL_CONTEXT` | the runner, per tool | the status pipe; the point's context file |
| `HEIMDALL_PLAIN`, `NO_COLOR` | you | no live progress in the stack build; no colour in `doctor` and the build |
| `RIVET_ANALYSIS_PATH` | the rivet and merge folders | `build/Rivet`; not set in the shell on purpose |
| `LHAPDF_DATA_PATH`, `GEANT4_DATA_DIR`, `ONNXRUNTIME_DIR`, `DELPHES_DIR` | `heimdall_env.sh` | the toolchain's data |

High-Energy's `HEKIT_*` and the old `HEP_*` names are refused, naming the replacement.
