# The stack's recipes: building Heimdall's stack

`build_stack.py` builds, from source, the software stack Heimdall runs on, **into Heimdall itself**:
the lab PC's stack (Ubuntu 24.04, GCC 13), with the same versions, the same features and the fixes its
build needed. It runs on a Linux machine with apt, in a Docker container, or on macOS with Homebrew
([platforms/mac/](platforms/mac/README.md)). It needs only `python3` (3.11+, or older with `tomli`):
its standard library, no other packages.

| File | Is |
|---|---|
| [packages.toml](packages.toml) | each package: release, tarball, how it is built, what it needs |
| [settings.toml](settings.toml) | the run's settings, each with its default: cores, features, the apt, pip and PDF lists |
| [build_stack.py](build_stack.py) | the engine: reads both, then fetches, builds, stamps and logs |
| [pth.py](pth.py) | writes the venv's `heimdall.pth`, so Python finds `framework/` |
| [patches/](patches/) | patches the stack's sources need (FastJet's SISCone, L29) |
| [platforms/container/](platforms/container/Dockerfile) | the same build in an Ubuntu 24.04 image (Dockerfile, Apptainer definition) |
| [build_by_hand.txt](build_by_hand.txt) | the same build as commands to paste into a terminal, step by step (Ubuntu 24.04) |
| [platforms/mac/](platforms/mac/README.md) | macOS: a Brewfile, the `mac.toml` overlay, `build.sh` and `launch.sh`, and the steps by hand |

The data says what is built; the engine knows only five steps (fetch, unpack, configure or cmake,
install, stamp) and four kinds of package. A version bump, a new flag or a new package is a TOML
edit, never a code change.

**Where the build puts things** (docs/framework/01_Target.md §2), all of it outside git:

| Folder | Holds |
|---|---|
| `stash/` | the downloaded archives (`<package>-<release>.<ext>`) and their unpacked sources |
| `forge/<package>/`, `forge/logs/` | the build trees (CMake's); one log per package |
| `stack/<dir>/`, `stack/.stamps/` | the installs; what is built |
| `env/venv/` | the Python environment, with `heimdall.pth` |
| `env/machine.sh` | this machine's extra lines for `setup.sh` (`setup_extra`; macOS's DYLD and GNU tools) |

The framework's own view of the stack (each library's flags and version) is `env/stack.toml`; the
shell environment is `env/hep_env.sh`, which `setup.sh` sources
([06 §15.3](../docs/06_Internals.md#153-the-flag-cache)).

---

## 1. Quick start

**On a machine** (sudo for the system packages, or `system=false` if they are installed), from
Heimdall's folder:

```bash
python3 recipes/build_stack.py --list                 # each package: release, state, what this run builds
python3 recipes/build_stack.py                        # the core stack (hours: ROOT alone is 1–2 h)
python3 recipes/build_stack.py packages=all           # and Sherpa, MadGraph, Whizard, ONNX Runtime, Geant4
source setup.sh && hep build --framework              # the environment, then the framework's apps
```

**Settings.** Any key of `settings.toml` is `key=value` on the command line (`cores=8
graphics=OFF`); any key of a package is `<package>.<key>=value` (`root.release=6.40.06`,
`madgraph.url=…`, `fastjet.patch=` for none, `root.extra="-Droofit=OFF"` for more arguments after a
package's own). For many changes, `--config my.toml`: a TOML file with settings and `[package]`
tables, which change packages or add new ones. The command line wins. `prefix=` builds somewhere
else than this Heimdall; only the tests use it.

**Cores.** `cores` is how many compilers run at once: each package's build gets it as
`make -j<cores>` (autotools) or `cmake --build <build> -j<cores>` (CMake); one compiler keeps one CPU
busy. `cores = 0` takes every CPU the build may run on: logical CPUs, so hyper-threads count (the
lab PC's i7-13700K has 16 cores and 24 threads: 24). ROOT has its own, `root_cores`, because each of
its LLVM/Cling compilers needs ~3 GB: `0` gives one per 3 GB of RAM, at most `cores` (5 on 15 GB).
`make install`, pip and the downloads do not use it.

**Choosing packages.** `packages = "core"` (the default), `"all"`, or names (`packages="rivet
pythia8"`). What a named package needs is added when it is not installed; they are always built in
`packages.toml`'s order.

**A bash script instead.** `--dry-run` prints the whole build as a plain bash script, so it can be
read first, or saved and run where you want plain commands (`--dry-run > build.sh; bash build.sh`).
It is the same commands, without stamps or logs: run it on a fresh Heimdall.

**In Docker** (from Heimdall's folder; [docs/framework/targets/container.md](../docs/framework/targets/container.md)):

```bash
docker build -f recipes/platforms/container/Dockerfile -t heimdall .
docker build -f recipes/platforms/container/Dockerfile --build-arg PACKAGES=core --build-arg ROOT_CORES=2 -t heimdall:core .
docker run --rm -it --user "$(id -u):$(id -g)" -v "$HOME/Github/Top-Quark:$HOME/Github/Top-Quark" -w "$HOME/Github/Top-Quark" heimdall
```

The image is headless (`graphics=OFF`) and holds Heimdall, with its stack, at `/opt/heimdall`. Work
dirs are mounted into it.

**Resuming.** A package that finishes is stamped (`stack/.stamps/<name>-<release>`) and skipped
next time, so the same command resumes after a failure, a reboot or a Ctrl-C. A changed release is a
new stamp, so it builds; delete a stamp to redo its package. A package's source is unpacked afresh
each time, so a half-done build never leaks into the next try.

**Downloads.** Every tarball the run needs is fetched first, four at a time, before anything is
built: a dead link stops the run in its first minute, not after ROOT. A tarball already in
`stash/<name>-<release>.<ext>` is used as it is, so a machine without network can build from
copied tarballs.

**Logs.** Each package writes `forge/logs/<name>.log`. A failure stops the build at once, prints
the last 30 lines and names the log.

**setup.sh** is tracked at Heimdall's root and finds its own folder; the build writes nothing to it.
What a machine needs beyond it (`setup_extra`) goes to `env/machine.sh`, which `setup.sh` sources.

---

## 2. The packages

`packages.toml`'s header documents every key. In its order (the build order), `core` first:

| Package | Release | Kind | For |
|---|---|---|---|
| `python` | your `python3` | a venv in `env/venv`, `python_packages`, `heimdall.pth` | every Python binding; the framework's `tomli_w`, `rich`, `uproot`, Pillow, matplotlib, pytest |
| `lhapdf` | 6.5.6 | autotools | PDFs for Pythia8, Herwig, Sherpa, Whizard, MadGraph |
| `hepmc3` | 3.3.1 | CMake | the event format between the tools |
| `fastjet` | 3.5.0 | autotools, the SISCone patch | jets for Rivet, Pythia8, Sherpa, Whizard and module programs |
| `fjcontrib` | 1.104 | autotools, into FastJet's prefix | the contribs; `libfastjetcontribfragile.so`, which Rivet links |
| `root` | 6.40.04 | CMake, `builtin_xrootd`, `root_cores` | App_yd2rt, Paint, Delphes, module programs |
| `hdf5` | 2.2.0 | cmake, with `h5cc-plain` for configure scripts (extra) | YODA's `.yoda.h5` when built together; HighFive, h5py, JETSCAPE |
| `yoda` | 2.1.4 | autotools; `.yoda.h5` with the stack's HDF5 in the build, else `--disable-h5` (never a system HDF5) | Rivet's histograms; the plot backends |
| `rivet` | 4.1.4 | autotools | the analyses |
| `pythia8` | 8.318 | its configure, with ROOT's and Rivet's plugins | App_Pythia, InprocJets |
| `thepeg` | 2.3.0 | autotools, into `stack/herwig7` | Herwig's event framework |
| `herwig` | 7.3.0 | autotools, into `stack/herwig7` | the `herwig` tool |
| `delphes` | 3.5.1 | CMake | the `delphes` tool |
| `sherpa` | 3.0.5 | CMake (extra) | the `sherpa` tool |
| `madgraph` | 3.8.1 | unpacked into `stack/madgraph`, configured (extra) | the `madgraph` tool |
| `whizard` | 3.1.8 | autotools, OCaml (extra) | the `whizard` tool |
| `onnxruntime` | 1.29.0 | the released binary, x64 or aarch64 (extra) | `// requires: onnx` |
| `geant4` | 11.4.2 | CMake, MT, GDML, datasets (extra) | `// requires: geant4` |
| `pdfsets` | `pdf_sets` | `lhapdf install` | the sets the configs and the tests use (the lab PC's 21) |

The installs go to `stack/<dir>`, under the directory names `env/hep_env.sh` expects:
`LHAPDF hepmc3 fastjet root yoda rivet pythia8 herwig7 delphes sherpa madgraph whizard onnxruntime
geant4`. More Python packages (scipy, pandas, scikit-learn, pyhf, …) go into `python_packages`.

**A new package** is a table in `packages.toml`, or in a `--config` file:

```toml
[mytool]
release = "1.2"
url     = "https://example.org/mytool-{release}.tar.gz"
kind    = "cmake"
needs   = ["root", "hepmc3"]
args    = ["-DWITH_ROOT={inst}/root"]
```

---

## 3. What makes the builds work together

Each of these was hit on the lab PC; the TOML files do what is in the right column.

| Package | Problem | What is done |
|---|---|---|
| all | ROOT, Rivet, Pythia8 and the module programs pass C++ types across libraries: mixed standards are ABI trouble | one standard for everything: `CXXFLAGS="-O2 -std=c++17"` for every build, and `CMAKE_CXX_STANDARD=17` |
| all | the build of one package needs the ones before it on its paths | the venv first on `PATH`, and every install on `PATH`, `LD_LIBRARY_PATH` and `PYTHONPATH`, as `setup.sh` gives them later (`settings.toml [env]` for the rest) |
| HepMC3 | `pyHepMC3` built but not installed; `GenEvent` missing from it | `-DHEPMC3_Python_SITEARCH<XY>=<venv site-packages>` (`HEPMC3_PYTHON_INSTALL_DIR` is ignored), and `-fno-lto`: LTO strips the pybind11 symbols |
| FastJet | several Rivets in one process (InprocJets, `rivet_threads`) cluster SISCone jets with one shared random state: other jets, or a FastJet internal error (L16, L29) | `fastjet.patch`: `recipes/patches/fastjet-3.5.0-siscone-thread-local-ranlux.patch`, the state per thread; one thread draws exactly what it drew before |
| fjcontrib | `make install` gives only static contrib libraries | `make fragile-shared-install` as well: `libfastjetcontribfragile.so`, as the lab PC has it |
| ROOT | 6.40.00's `rootcling_stage1` fails to link (`clang::CodeGenerator::GetModule()`) | pinned to 6.40.04, which fixes that regression |
| ROOT | parallel compilation of its LLVM/Cling OOM-kills `cc1plus`, and the truncated objects then fail later links with errors that look unrelated | `root_cores`: one compiler per 3 GB of RAM (5 on 15 GB); every other package at `cores` |
| ROOT | `-DPYTHON_EXECUTABLE`, `-Dglew`, `-Dpython3` are ignored by 6.40 | `-DPython3_EXECUTABLE=<venv>` (FindPython3), `-Dpyroot=ON` |
| ROOT | an external xrootd 6.x is untested against ROOT 6.40, and ROOT does not read `XROOTD_ROOT_DIR` | `-Dxrootd=ON -Dbuiltin_xrootd=ON`, `-Ddavix=OFF` |
| ROOT | the features the framework and the lab PC use | `mathmore roofit tmva fftw3 sqlite xml gdml http imt ssl vdt` on; `x11 opengl webgui asimage` follow `graphics` |
| Pythia8 | its Rivet and ROOT plugins exist only if it is built after them | after ROOT and Rivet; `optional` adds `--with-root --with-rivet` when they are there |
| ThePEG | `--with-hepmc` alone looks for HepMC2 | `--with-hepmcversion=3` |
| Herwig | `make install` writes `HerwigDefaults.rpo`, which needs CT14lo/CT14nlo | `lhapdf install CT14lo CT14nlo` first, `LHAPDF_DATA_PATH` set |
| Delphes | DelphesPythia8 is built only when Pythia8 is found | `PYTHIA8=<install>` in its environment, `-DROOT_DIR=<root>/cmake` |
| Sherpa | its `_DIR` options are spelled per package (`HepMC3_DIR`, `RIVET_DIR`, `FASTJET_DIR`, `LHAPDF_DIR`) | as Sherpa spells them; `HepMC3_DIR` is the CMake config directory |
| Whizard | HepMC3 is `--enable-hepmc --with-hepmc` (no `*hepmc3` options); O'Mega needs OCaml | so; `ocaml ocaml-findlib libgc-dev` are system packages |
| MadGraph | not built: a tree that finds LHAPDF and Pythia8 through its configuration file | unpacked into `stack/madgraph`; `lhapdf`, `pythia8_path` and `automatic_html_opening = False` set |
| Python | pip wheels of FastJet or HepMC3 do not match the stack's symbols | every compiled HEP library is built here; pip installs only pure-Python and ML packages |

---

## 4. System packages

With `system = true` (the default), the run first installs `settings.toml`'s `apt_packages` with
apt-get, through sudo when not root (its password is asked before anything is logged), and stamps
`system`. The list is grouped there by what needs each package: the build tools, Python, ROOT,
ThePEG and Herwig, LHAPDF, Sherpa, Whizard (OCaml), Geant4, and the framework itself (toml++,
zstd, zlib for Paint, App_Pythia and the module kit; pdflatex for sheet figures; pandoc, poppler
and the Beamer class for decks and sheets, `hep deck`).

On a distribution without apt, install the same packages under its names and run with
`system=false`.

---

## 5. After the build

```bash
source setup.sh                       # in Heimdall's folder (alias load_hep)
hep status --stack                    # each package's version
hep build --framework && make test    # the framework's apps and tests, against the new stack
```

**What is checked.**
- `tests/runner/test_stack_build.py`: the plans (order, added needs, overrides, `--config`,
  refusals) and the full dry run, which must be valid bash and write nothing.
- For real: FastJet with its patch and fjcontrib, offline from local tarballs, both through the
  engine and through its `--dry-run` script.
- Not yet: the whole stack in one run, the Dockerfile, and the downloader against the live sites.
  The full stack was built on the lab PC by hand, with these flags. Expect the first full run on a
  new machine to need small fixes, which the log names.

**Known caveats.**
- **MadGraph and ONNX Runtime** rename releases often. When a download 404s, set `madgraph.url` or
  `onnxruntime.url` from their download pages.
- **Delphes 3.5.1 and ROOT 6.40** work together on the lab PC, but upstream has not released
  against 6.40. A dictionary (`rootcling`) failure there is Delphes', not this build's.
- **Geant4's datasets** need network during its build. A timeout is retried by rerunning.
- **Rebuilt binaries change identities.** A point that ran with the old App_Pythia, App_yd2rt or a
  Rivet plugin reruns once the framework is rebuilt against a new stack (docs/06_Internals.md §27).
- **Not built here:** CMSSW and Key4hep, which come from CVMFS in an el9 apptainer container. Never
  mix their environment with this stack's in one shell. A standalone xrootd is not built either:
  ROOT builds its own.

---

## 6. Toolkits: preset sets for a kind of work

A toolkit is a named set of packages ([toolkits.toml](toolkits.toml)). `packages=@<toolkit>` builds it,
with what its packages need. Toolkits mix with each other and with names: `packages="@lab
@heavy-flavour"`. `--toolkits` lists them. `packages=all` is still the lab PC's set (`@lab`): the
toolkit packages join only by name or through a toolkit.

| Toolkit | For | Brings (besides the core) |
|---|---|---|
| **`@primary`** | **the primary workflow**: what the fresh-machine plans build | the lab PC's stack (`@lab`) and MadAnalysis 5 |
| `@lab` | the lab PC's stack | the extra generators, Delphes, ONNX Runtime, Geant4 |
| `@generators` | event generators side by side | Herwig, Sherpa, Whizard, MadGraph5_aMC@NLO |
| `@bsm-recast` | BSM reinterpretation | MadGraph, Delphes, MadAnalysis 5, Contur, the HEPData clients |
| `@bsm-models` | model building | FeynRules, SARAH, UFO models into MadGraph; needs Mathematica |
| `@heavy-flavour` | heavy-flavour and tau decays | EvtGen with PHOTOS++ and TAUOLA++ |
| `@exclusive` | central exclusive production | SuperChic |
| `@fixed-order` | fixed-order predictions | MCFM |
| `@tuning` | generator tuning | Professor |
| `@detector` | detector simulation and description | Geant4, Delphes, DD4hep, GeoModel with FullSimLight, Garfield++ |
| `@heavy-ion` | heavy-ion collisions | JETSCAPE |
| `@data` | data formats and publishing | HDF5 with HighFive (and h5py), the HEPData clients |
| `@key4hep`, `@cms`, `@fluka` | external stacks | nothing built: the run says where they come from |
| `@key4hep-src` | Key4hep's data model and framework, from source | **isolated, C++20:** ROOT, HepMC3, Geant4, podio, EDM4hep, Gaudi |
| `@gpu-sim` | Geant4 EM showers on the GPU | **isolated, C++20:** Geant4, VecCore, VecGeom, G4HepEm, AdePT; CUDA (external) |

**Isolated toolkits: a C++ standard of their own.** The stack is one ABI: ROOT, Rivet, Pythia 8,
Geant4 and the framework's apps all C++17. A tool that needs C++20 cannot join it, so a toolkit may
build a whole stack of its own:
- `isolated = true` builds into `stacks/<toolkit>/` (its installs, build trees and venv; its
  framework apps go to `stacks/<toolkit>/Apps`). `stash/` is shared.
- `[<toolkit>.settings]` changes settings for the run, `cxx_std = 20` above all, and
  `[<toolkit>.override.<package>]` changes a package's keys for it (Geant4's own C++ switch).
- **A toolkit that changes `cxx_std` or `opt_flags` must be isolated**: the engine refuses it
  otherwise. **One isolated stack per run.**
- `source stacks/<toolkit>/setup.sh`, which the build writes, loads it instead of `setup.sh`, in a
  shell of its own (or after `quit`). `hep where` and the prompt (`HEP-<toolkit>`) say which stack
  is loaded.

**Your own toolkits** go in [toolkits.d/](toolkits.d/README.md), one or more `*.toml` files in the
same format; [toolkits.d/example.toml.sample](toolkits.d/example.toml.sample) shows every key. They
are read with the presets and used the same way. A name that a preset already has is refused, so a
custom toolkit never silently replaces one.

**Three kinds of package beyond the lab PC's:**
- **`status = "new"`**: the recipe follows the project's own build instructions, with releases
  checked on 2026-10-10, but no build has proven it yet. The run says so when it starts one, and
  its first failure is a gate (docs/framework/02_Agents.md §6). Once a build proves it, the status
  goes.
- **`kind = "external"`**: never built here. Key4hep and CMSSW come from CVMFS, each in a shell or
  container of its own and never mixed with `setup.sh`'s. FLUKA comes behind its licence, and
  Mathematica behind its own. Their `how` says where each comes from.
- **`apt = [...]`**: a package's own system packages, installed with `settings.toml`'s for the run
  that builds it.

### What was asked for, and what came of it

From the list asked for on 2026-10-10: a tool is added when it is installed on its own, rather than
being part of another tool. It must also be compatible (MadGraph 3, Pythia 8.3; a tool needing
another C++ standard gets an isolated toolkit), and still be released and supported.

| Asked for | Decision | Why |
|---|---|---|
| Contur | **added** (`contur`, pip, 3.1.3) | separate; Contur 3 runs on Rivet 4 |
| MadAnalysis 5 | **added** (`madanalysis5`, 1.11.1) | separate; releases on GitHub |
| DelphesMA5tune | inside MadAnalysis 5 | installed from MadAnalysis 5's prompt (`install delphesMA5tune`): a part of it |
| EvtGen | **added** (`evtgen`, R03-00-01) | separate; HepMC3, Pythia 8, PHOTOS++ and TAUOLA++ interfaces |
| PHOTOS++ | **added** (`photospp`, 3.64) | separate; HepMC3 since 3.64 |
| TAUOLA++ | **added** (`tauolapp`, 1.1.8) | separate; HepMC3 since 1.1.8 |
| SuperChic | **added** (`superchic`, 5.6.2) | separate; active |
| MCFM | **added** (`mcfm`, 10.3) | separate; the latest release |
| Professor | **added** (`professor`, 2.5.2) | separate; still released (Apprentice is its intended successor, not yet a replacement) |
| JETSCAPE | **added** (`jetscape`, 4.0.2) | separate; active |
| HighFive / HDF5 | **added** (`highfive`, 3.3.0, on the stack's `hdf5`) | HighFive is maintained at highfive-devs since BlueBrain's archive (2025) |
| HEPData | **added** (`hepdata`: hepdata-lib, hepdata-cli) | the database is a website; its clients are what installs |
| DD4hep | **added** (`dd4hep`, 01-38) | standalone on the stack's ROOT and Geant4; C++17 since v01-35 |
| ATLAS FullSimLight | **added** inside `geomodel` (6.27.0) | its own repository is archived; it is now built as part of GeoModel |
| Garfield++ | **added** (`garfieldpp`, 2025.12) | separate; active |
| FeynRules, SARAH | **added** (`feynrules` 2.3.49, `sarah` 4.15.4) | separate Mathematica packages: they need Mathematica (external) |
| NLOCT | with FeynRules | a FeynRules extension, downloaded into FeynRules' folder from the FeynRules wiki |
| UFO models | **added** (`ufo-models`) | data, not a tool: `settings.toml`'s `ufo_models` URLs are unpacked into MadGraph's `models/` |
| Key4hep | **external** (`key4hep`) | a whole stack (Spack, C++20) from CVMFS, in a shell of its own |
| EDM4hep | **added**, isolated (`@key4hep-src`: `edm4hep` 01-01 on `podio` 01-07); or prebuilt through `@key4hep` | it needs C++20 (and podio): a stack of its own |
| Gaudi | **added**, isolated (`@key4hep-src`: `gaudi` v40r6); or prebuilt through `@key4hep` | C++20 since v39r0: a stack of its own |
| CMSSW | **external** (`cmssw`) | from CVMFS in an el9 container; never mixed with this stack |
| FLUKA | **external** (`fluka`) | registration and licence: it cannot be fetched for the user |
| VINCIA | inside Pythia 8 | Pythia 8.3's shower (`PartonShowers:model = 2`) |
| DIRE | inside Pythia 8 | Pythia 8.3's shower (`PartonShowers:model = 3`); the standalone DIRE is no longer released |
| MadSpin, MadWidth | inside MadGraph | parts of MG5_aMC |
| MadSTR | left out | a MadGraph plugin that does not support MadGraph 3: in conflict with MG5_aMC 3.7.3 |
| TCL detector cards | inside Delphes | Delphes' cards are Tcl files (`cards/`); a work dir keeps its own |
| GDML | inside ROOT and Geant4 | a format: ROOT (`gdml`) and Geant4 (`GEANT4_USE_GDML`) are built with it |
| CheckMATE | left out | its Pythia support is the 8.2 series only (the stack has 8.318), and it has no tagged releases to pin; MadAnalysis 5 and Contur cover recasting |
| AdePT | **added**, isolated (`@gpu-sim`: `adept` 0.4.1 on `vecgeom` v2.1.1, `g4hepem` 20251114, `veccore` 0.8.2) | C++20 and CUDA: a stack of its own; CUDA and the GPU are external |
| HELAC-Onia | left out | the public release is 2.0.1, from 2015; newer versions are not distributed publicly |
| Hector | left out | the last release is 1.5.2, from 2009 |
| FROG | left out | an event display unmaintained for over a decade |
| GeantV | left out | the project ended in 2019 (its successors are AdePT and Celeritas) |
| MCplots | left out | a website (mcplots.cern.ch) built on Rivet, not a tool to install |
| TArt | left out | not identified with certainty (RIKEN ANAROOT's `TArt` classes are experiment-specific); name the one you meant |
