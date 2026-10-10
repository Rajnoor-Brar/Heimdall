# Heimdall

A framework for Monte Carlo studies in high-energy physics, and the home of the software stack it
runs on. Tools are processes, chained by a run TOML: Pythia, Herwig, Sherpa, Whizard and MadGraph,
Rivet, Delphes, your own programs, and the pages drawn with ROOT.

This folder is `$HEP`. It holds the stack's recipes and, once they have run, the stack itself, the
Python environment, the framework, and its compiled apps. Your studies live elsewhere, in **work
dirs** (`configs/`, `modules/`, `results/`, …), as many as you like.

## Getting it onto a machine

```bash
git clone <Heimdall's URL> ~/Github/Heimdall
cd ~/Github/Heimdall
python3 recipes/build_stack.py              # the stack, from source, into stack/ (hours; recipes/README.md)
python3 recipes/build_stack.py --toolkits   # preset sets for a kind of work: packages=@bsm-recast, @detector, …
source setup.sh                             # the environment; alias load_hep='source ~/Github/Heimdall/setup.sh'
hep build --framework                       # the framework's apps, into framework/Apps/
hep setup ~/Github/My-Study --project Jets --git    # a work dir with a starter
```

On macOS use `recipes/platforms/mac/`. For an image, use `recipes/platforms/container/`.

## What is where

| Folder | Holds |
|---|---|
| `setup.sh` | the environment: `HEP`, the stack on `PATH`, the venv, `hep` |
| `recipes/` | how the stack is built: `build_stack.py`, `packages.toml`, `settings.toml`, `patches/`, `platforms/` |
| `env/` | the environment's files: `hep_env.sh`, `flags.sh`, `stack.toml`, `stack.py`; `venv/` (the Python environment) |
| `framework/` | what runs: `bin/hep`, the runner, the tool folders, the schema, the work-dir template; `Apps/` (the compiled apps) |
| `src/` | what is compiled: the C++ kits and the apps' sources |
| `docs/` | the manual ([docs/README.md](docs/README.md)); `framework/`, the plans that set Heimdall up on a fresh machine |
| `tests/` | the tests, and the frozen work dir they run in |
| `stack/` `forge/` `stash/` | not in git: the installed stack; builds in progress; downloads |
| `stacks/<toolkit>/` | not in git: an isolated toolkit's own stack (another C++ standard), loaded by its `setup.sh` |

**Never run `git clean -x` here:** it would delete the stack. `forge/` and `stash/` may be emptied
by hand. Editors should exclude `stack/ forge/ stash/` from watching and search.

## History

Heimdall was seeded on 2026-10-10 from High-Energy at `split/base` (5e0a913). The history before its
import commit, and the record's older citations (`git show 3a5ec16:…`, `rework/v1-final`), are
High-Energy's.
