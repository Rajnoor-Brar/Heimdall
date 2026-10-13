# Heimdall

A framework for Monte Carlo studies in high-energy physics, and the home of the software stack it
runs on. Tools are processes, chained by a run TOML: Pythia, Herwig, Sherpa, Whizard and MadGraph,
Rivet, Delphes, your own programs, and the pages drawn with ROOT.

This folder is `$HEP`. It holds the stack's recipes and, once they have run, the stack itself, the
Python environment, the framework, and its compiled apps. Your studies live elsewhere, in **work
dirs** (`configs/`, `modules/`, `results/`, …), as many as you like.

## From nothing to a drawn page

**Linux** (Ubuntu, Debian):

```bash
git clone <Heimdall's URL> ~/Github/Heimdall && cd ~/Github/Heimdall
python3 recipes/build_stack.py packages=@primary   # the stack, from source, into ~/Himinbjorg (hours; recipes/README.md)
source setup.sh                                    # the environment, in bash (any other shell: ./launch.sh)
hep build --framework                              # Heimdall's apps, into the machine root's apps/
hep doctor                                         # what the stack can do, checked: every row ok?
hep setup ~/Study --example jets                   # a work dir, with the guide's demo project
cd ~/Study && hep build                            # its Rivet plugin and module programs
hep check Demo/jets                                # every configuration planned, nothing run
hep run Demo/jets single                           # one point: Pythia → Rivet → ROOT, then the pages
xdg-open results/Demo/jets/03_single/plots/root/index.html
```

**macOS**: the same, but the stack is built through Homebrew's tools first, and the environment is
`launch.sh`'s bash (macOS's own shell is zsh):

```bash
git clone <Heimdall's URL> ~/Github/Heimdall && cd ~/Github/Heimdall
bash recipes/platforms/mac/build.sh packages=@primary   # (recipes/platforms/mac/README.md)
./launch.sh                                             # a bash with the environment; then as on Linux,
hep build --framework && hep doctor                     # from hep build --framework to the page,
hep setup ~/Study --example jets                        # with `open` for xdg-open
```

**A container**: `recipes/platforms/container/` builds an image with the stack in it.

Then: [docs/02_User_Guide.md](docs/02_User_Guide.md) walks through the example and your own study
(`hep setup ~/Github/My-Study --project Jets --git`: a work dir with a starter, in a git repository);
`hep help` lists the commands. Later rebuilds are `hep stack build` (`hep stack list @primary` says
what is installed); other sets for a kind of work are `python3 recipes/build_stack.py --toolkits`.

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
