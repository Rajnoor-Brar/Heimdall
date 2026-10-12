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
python3 recipes/build_stack.py packages=@primary   # the stack, from source, into stack/ (hours; recipes/README.md)
python3 recipes/build_stack.py --toolkits   # other sets for a kind of work: @bsm-recast, @detector, … and yours
source setup.sh                             # the environment; alias load_hep='source ~/Github/Heimdall/setup.sh'
hep build --framework                       # the framework's apps, into the machine root's apps/ ($HEP_APPS)
hep setup ~/Github/My-Study --project Jets --git    # a work dir with a starter
```

`@primary` is the lab PC's set (ROOT, Pythia8, Rivet, YODA, HepMC3, FastJet, LHAPDF and its PDF
sets, Herwig, Sherpa, MadGraph, Whizard, Delphes, Geant4, ONNX Runtime) plus MadAnalysis5. On macOS
use `recipes/platforms/mac/`. For an image, use `recipes/platforms/container/`. An agent setting up a
fresh machine follows [docs/framework/](docs/framework/README.md), step by step.

## What is where

| Folder | Holds |
|---|---|
| `setup.sh` | the environment: `HEP`, the stack on `PATH`, the venv, `hep` |
| `recipes/` | how the stack is built: `build_stack.py`, `toolkits/` (`standard.toml`, every recipe; one file per toolkit), `settings.toml`, `patches/`, `platforms/` |
| `env/` | the environment's files: `hep_env.sh`, `flags.sh`, `stack.toml`, `stack.py` |
| `framework/` | what runs: `bin/hep`, the runner, the tool folders, the schema, the work-dir template, the build's rules |
| `src/` | what is compiled: the C++ kits and the apps' sources |
| `docs/` | the manual ([docs/README.md](docs/README.md)); `framework/`, the plans that set Heimdall up on a fresh machine |
| `tests/` | the tests, and the frozen work dir they run in |

The checkout holds only what git has. What this machine built lives in the **machine root**,
`~/Himinbjorg` (`$HEP_MACHINE`), outside git, and several checkouts may share it:

| Machine root | Holds |
|---|---|
| `stack/` | the installed stack: a folder per package, `.stamps/` |
| `venv/` | the Python environment, with `heimdall.pth` |
| `apps/` | Heimdall's compiled apps (`$HEP_APPS`) |
| `forge/` | `downloads/`, `src/`, `build/`, `logs/`; the framework's `make/` and `tests/`; the tests' `scratch/`. May be emptied |
| `stacks/<toolkit>/` | an isolated toolkit's own stack (another C++ standard), loaded by its `setup.sh` |
| `machine.toml`, `machine.sh` | this machine's settings, and its extra lines for `setup.sh` |

A checkout made before the machine root moves its stack there once, by links and moves only:
`python3 recipes/machine.py adopt` (`--dry-run` lists what it would do).

## History

Heimdall was seeded on 2026-10-10 from High-Energy at `split/base` (5e0a913). The history before its
import commit, and the record's older citations (`git show 3a5ec16:…`, `rework/v1-final`), are
High-Energy's.
