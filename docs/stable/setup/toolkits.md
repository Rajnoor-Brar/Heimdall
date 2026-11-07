---
id: toolkits
summary: which set of packages to build: every toolkit, writing your own, isolated stacks, ready-made from conda-forge
code: recipes/toolkits
---

# Toolkits

A toolkit is a configuration for building the stack: which recipes, with which settings. One file each in `recipes/toolkits/`, named as invoked (`lab.toml` is `@lab`). `packages=@<toolkit>` builds it with what it needs; they mix (`packages="@lab @heavy-flavour"`). `--toolkits` lists them; `--list @<toolkit>` prints the set and why.

| Toolkit | For | Brings beyond the core |
|---|---|---|
| **`@primary`** | the primary workflow | the lab stack, MadAnalysis 5, HepMC2 |
| `@lab` | the lab PC's stack (`all`) | the extra generators, Delphes, HDF5, ONNX Runtime, Geant4 |
| `@standard` | the core | |
| `@generators` | generators side by side | Pythia 8, Herwig, Sherpa, Whizard, MadGraph |
| `@bsm-recast` | BSM reinterpretation | MadGraph, Delphes, MadAnalysis 5, Contur, HEPData clients |
| `@bsm-models` | model building | FeynRules, SARAH, UFO models; needs Mathematica |
| `@heavy-flavour` | heavy-flavour and tau decays | EvtGen, PHOTOS++, TAUOLA++ |
| `@exclusive` | central exclusive production | SuperChic |
| `@fixed-order` | fixed-order predictions | MCFM |
| `@loops` | NLO in Sherpa | OpenLoops, Recola, BlackHat, OpenMPI |
| `@tuning` | generator tuning | Professor |
| `@detector` | detector simulation | Geant4, Delphes, DD4hep, GeoModel with ATLAS FullSimLight, Garfield++ |
| `@heavy-ion` | heavy-ion collisions | JETSCAPE, HDF5 |
| `@data` | formats and publishing | HDF5, HighFive, h5py, HEPData clients |
| `@key4hep`, `@cms`, `@fluka` | external stacks | nothing built: says where they come from |
| `@core-conda`, `@lab-conda`, `@primary-conda`, `@generators-conda` | the same sets, ready-made where conda-forge carries them | minutes, not hours |
| `@conda` | a layer: every recipe conda-forge carries, ready-made; adds no package | add it to a set: `extends = ["lab", "conda"]` |
| `@key4hep-src` | Key4hep from source | isolated, C++20 |
| `@gpu-sim` | Geant4 EM showers on the GPU | isolated, C++20 |

## Your own

In the machine root's `toolkits/`, never Heimdall's tree. One with a shipped name is used instead of it, and may extend it. `standard.toml` itself is not replaced: change recipes in `machine.toml` or a toolkit.

```toml
# <machine root>/toolkits/heavy-ion.toml
description = "heavy-ion work: JETSCAPE with HDF5, on the lab set"
extends     = "lab"                   # another toolkit, or a list

[standard]                            # which of standard.toml's recipes it takes
jetscape = true                       # a package …
core     = true                       # … or a group
sherpa   = false                      # out of what extends brought

[settings]
cores = 16

[packages.jetscape]                   # a list appends, unless replace = ["key"]
extra = ["-DUSE_ROOT=ON"]
```

## Isolated: a C++ standard of its own

The stack is one ABI, one C++ standard (`cxx_std`, 17 by default), since ROOT, Rivet and Pythia pass C++ types across libraries. A tool needing C++20 gets a whole stack: `isolated = true` builds into `stacks/<toolkit>/` (`forge/downloads/` shared), with `[settings] cxx_std = 20`. A toolkit changing `cxx_std` or `opt_flags` must be isolated, and there is one isolated stack per run. `source stacks/<toolkit>/gjallarhorn.sh` loads it in a shell of its own.

## Ready-made

A recipe with `from = "conda-forge"` is installed into the base, not built. `@conda` sets it for every recipe conda-forge carries; `toolkits/conda.toml` says what differs: FastJet without the SISCone patch, so `rivet_threads > 1` is refused; fjcontrib without its separate libraries; ROOT built for C++20 or 23 only, so a ready-made ROOT sets the stack's `cxx_std` to 20 (one set to another standard by a layer is refused); Pythia 8.312; Sherpa 3.0.0 without Rivet's interface. Not on conda-forge, so still built: MadGraph, Whizard, MadAnalysis 5, PHOTOS++, TAUOLA++, SuperChic, MCFM, JETSCAPE, Garfield++, the PDF sets. What a ready-made package needs must be ready-made too, or there would be two copies: the run refuses that. A machine root remembers what it took: a recipe with no `from`, whose package is in the base and not built, is the base's.

Recipes with `status = "new"` are unproven, and their first failure is yours to judge.
