# 01 — Assessment

What the machine root's environment is today, what has gone wrong with it, and what conda-forge can
take over. Package facts are from anaconda.org's package API (2026-10-14). Code citations are at
`864c0f4`.

## 1. Today's layers

| Layer | Comes from | Where Heimdall says so |
|---|---|---|
| compilers, build tools, the libraries the stack links (gsl, libzip, libxml2, boost, X11 …), pandoc, TeX | the OS: `apt-get install` of `apt_packages` (with sudo), or Homebrew's Brewfile on macOS | `recipes/settings.toml:17` (`system = true`), `:40` (`apt_packages`); `recipes/platforms/mac/Brewfile` |
| the Python interpreter | the OS's `python3` | `recipes/settings.toml:16` |
| Python packages | a venv made from it, plus pip | `recipes/toolkits/standard.toml:55`–`62`; `recipes/settings.toml:25` |
| the HEP stack | Heimdall's recipes, from source, into `stack/<pkg>/` | `recipes/toolkits/standard.toml` |
| the stack's Python bindings | built against the venv's interpreter: ROOT, HepMC3, Pythia | `standard.toml:116` (`-DPython3_EXECUTABLE`), `:82` (HepMC3's sitearch), `:165` (`--with-python-bin`) |
| the shell | `env/hep_env.sh` activates the venv and puts each package's `bin/` and `lib/` on `PATH` and `LD_LIBRARY_PATH` | `env/hep_env.sh:222`, `:231`–`232` |

**On macOS, Homebrew is already a base.** `mac.toml` sets `system = false` and points the build at
Homebrew's prefix through `[env]`: `CPPFLAGS`, `LDFLAGS` and `CMAKE_PREFIX_PATH`
(`recipes/platforms/mac/mac.toml:9`, `:22`–`25`). The design in [02](02_Design.md) is that mechanism,
with a prefix Heimdall owns and locks.

**The build cleans its environment (V117).** It keeps a short list of the user's variables and drops
`VIRTUAL_ENV`, `CONDA_PREFIX` and every `PATH` entry of another stack (`recipes/build_stack.py:1009`–`1044`).
A base would be the one prefix the build keeps on purpose.

## 2. What has gone wrong

1. **An OS upgrade breaks the stack.** Ubuntu 24.04 → 26.04 (2026-10-12) replaced apt's `libgsl.so.27`,
   `libzip.so.4` and `libxml2.so.2` with new sonames. Since then:
   - Herwig and ThePEG fail to load (gsl);
   - Sherpa fails to load (libzip);
   - ROOT's `libMathMore` (gsl) and `hist2workspace` (libxml2) are broken.

   `build_stack.py --rebuild-broken` finds and rebuilds them (`recipes/build_stack.py:606`), but only
   after the fact, and it takes hours.
2. **The interpreter comes and goes with the OS.** 26.04 removed Python 3.12, which every binding was
   built against. The venv was repointed by hand at a standalone CPython 3.12.
3. **Each platform has its own system list.**
   - Linux uses `apt_packages`.
   - macOS uses the Brewfile, `mac.toml`'s `[env]` and the 17 problems of the first Mac build
     ([audit 3, 01 appendix](../audit_3/01_Process.md#appendix-the-mac-build-problem-by-problem)).
     Several came from Homebrew's or Apple's toolchain rather than the packages.
4. **A machine without root has no system step.** A cluster node or a shared machine cannot
   `apt-get`. Today the only way there is a container (`recipes/platforms/container/`).

## 3. The base: the apt list and the Brewfile against conda-forge

**Every entry has a conda-forge package**, on Linux x86_64 and, unless noted, on macOS arm64.

| apt (`settings.toml:40`) / Brewfile | conda-forge | Version (2026-10-14) | Note |
|---|---|---|---|
| build-essential | `gcc`, `gxx`, `make`, `sysroot_linux-64` | 16.2 (also 14.x, 15.x), 4.4.1, glibc 2.17–2.39 | macOS: `clang`/`clangxx` 23 |
| gfortran; Brew `gcc` | `gfortran` | 16.2 | |
| cmake, pkg-config, libtool, autoconf, automake, patch | same names | 4.4.4, 0.29.2, 2.5.4, 2.72, 1.19, 2.8 | |
| git, curl, ca-certificates | same names | 2.56.0, 8.22.0, 2026.7.22 | |
| Brew `gnu-sed`, `coreutils`, `bash` | `sed`, `coreutils`, `bash` | 4.10, 9.12, 5.2.37 | replaces `mac.toml`'s gnubin `PATH` lines |
| python3-venv, python3-dev | `python` | any minor version (3.15.0 newest) | pinned per base |
| `python_packages` (`settings.toml:25`) | `numpy`, `cython`, `tomli-w`, `rich`, `pyyaml`, `pillow`, `matplotlib-base`, `uproot`, `awkward`, `pytest` | 2.5.4, 3.3.0, 1.2.0, 15.0.0, 6.0.3, 12.3.0, 3.11.2, 5.7.7, 2.14.0, 9.1.1 | |
| libxml2-dev, libfftw3-dev, libsqlite3-dev | `libxml2`, `fftw`, `libsqlite` | 2.15.4, 3.3.11, 3.54.0 | |
| libx11-dev, libxpm-dev, libxft-dev, libxext-dev | `xorg-libx11`, `xorg-libxpm`, `xorg-libxft`, `xorg-libxext` | 1.8.13, 3.5.19, 2.3.9, 1.3.7 | |
| liblzma-dev, libpcre3-dev | `liblzma-devel`, `pcre` / `pcre2` | 5.8.3, 8.45 / 10.47 | |
| libglew-dev, libgif-dev, libftgl-dev, libgraphviz-dev | `glew`, `giflib`, `ftgl`, `graphviz` | 2.3.0, 6.1.3, 2.4.0, 14.1.2 | |
| libcurl4-openssl-dev, uuid-dev, libkrb5-dev, libssl-dev | `libcurl`, `libuuid`, `krb5`, `openssl` | 8.22.0, 2.42.4, 1.22.2, 4.0.3 | |
| libgsl-dev, libboost-all-dev, libyaml-cpp-dev, libzip-dev, libbz2-dev | `gsl`, `libboost-devel`, `yaml-cpp`, `libzip`, `bzip2` | 2.8, 1.92.0, 0.8.0, 1.11.4, 1.0.8 | the three that broke on 26.04 are here |
| Brew `tbb` | `tbb-devel` | 2023.1.0 | ROOT's `imt` |
| ocaml, ocaml-findlib, libgc-dev | `ocaml`, `ocaml-findlib`, `bdw-gc` | 5.4.0, 1.8.1, 8.2.12 | **`ocaml-findlib`: no macOS arm64 build** (Whizard on the Mac) |
| libxerces-c-dev | `xerces-c` | 3.3.0 | |
| libgl1-mesa-dev, libglu1-mesa-dev, libxmu-dev, libxi-dev | `libgl-devel`, `libglu`, `xorg-libxmu`, `xorg-libxi` | 1.7.0, 9.0.3, 1.3.1, 1.8.3 | GL: Linux only (the Mac uses Cocoa) |
| libtomlplusplus-dev, libzstd-dev, zlib1g-dev | `tomlplusplus`, `zstd`, `zlib` | 3.4.0, 1.5.7, 1.3.2 | Heimdall's own C++ |
| pandoc, poppler-utils | `pandoc`, `poppler` | 3.12.1, 26.09.0 | decks and sheets |
| texlive-latex-base/-extra/-recommended | `texlive-core` | 20260301 | **unknown** whether it holds Beamer and what the sheets load: until checked, TeX stays with the OS |

**The base cannot hold:**
- glibc and the kernel. conda-forge builds against an old glibc (the sysroot), so a newer OS runs them.
- The GPU driver. The CUDA toolkit can be in the base.
- The X server and the GL vendor drivers. The base's `libglvnd` dispatches to the OS's.
- Mathematica, CVMFS stacks, Docker, Slurm.

## 4. The HEP tools on conda-forge: a shortcut, not the default

The tools stay built from source (the user's decision). Where a ready-made package would save hours,
conda-forge has these:

| Package | conda-forge | Heimdall's recipe / the lab PC | Built with |
|---|---|---|---|
| ROOT | 6.40.04 | 6.40.04 | |
| Rivet | 4.1.4 | 4.1.4 | depends on `cxx-compiler`, so `rivet-build` works |
| YODA | 2.1.4 | 2.1.4 | |
| HepMC3 | 3.3.1 | 3.3.1 | |
| LHAPDF | 6.5.6 | 6.5.6 | no PDF sets (downloaded as today) |
| FastJet, fjcontrib | `fastjet-cxx` 3.5.2, `fastjet-contrib` 1.105 | 3.5.0 + the SISCone patch | **unpatched** (`standard.toml:94`): threaded SISCone is refused |
| Pythia 8 | **8.312** | 8318 | FastJet, HepMC2/3, LHAPDF, Python |
| Herwig, ThePEG | 7.3.0, 2.3.0 | 7.3.0, 2.3.0 | GSL, LoopTools |
| Sherpa | **3.0.0** | 3.0.5 | ships `gxx`, `cmake` for its process libraries |
| Delphes, Geant4, EvtGen, ONNX Runtime | 3.5.1, 11.4.3, 2.2.3, 1.31.0 | | |
| MadGraph, Whizard | **absent** | 3.8.1, 3.1.8 | |

Two catches:
- A ready-made package fixes its version and build options, and carries no patch.
- Its conda dependencies come ready-made too. Ready-made Rivet brings ready-made FastJet, so the
  stack's patched FastJet cannot sit under it ([02 §6](02_Design.md#6-ready-made-packages)).

## 5. Channels and tools

- **hep-forge** is an organisation channel on anaconda.org, not hepforge.org (which hosts the source
  tarballs Heimdall downloads).
  - It has 82 packages, Linux only, EIC-flavoured: DJANGOH, RAPGAP, eic-smear, ePIC, afterburner,
    MCFM, Professor and more.
  - Its core packages are older than conda-forge's: Rivet 4.1.0, ROOT 6.38.04, YODA 2.1.0,
    Sherpa 2.2.16.
  - No maintainer is named and no public recipes were found. **Not used** (the user, 2026-10-14).
- **Miniconda** installs Anaconda's `defaults` channel. Anaconda's terms require a paid licence above
  200 employees; university research use is disputed, and several universities moved to Miniforge.
  The HEP packages are not in `defaults` anyway. **Not used.**
- **pixi** (prefix.dev) is **chosen** (the user, 2026-10-14):
  - one static binary, no base environment, no `.bashrc` edits;
  - a manifest (`pixi.toml`) and a multi-platform lockfile (`pixi.lock`);
  - PyPI packages beside conda ones;
  - `pixi shell-hook` prints the activation, and `pixi-pack` packs an env for offline machines.

  Miniforge (conda and mamba) and micromamba use the same packages, without the project lockfile.
- **Not conda:**
  - **Spack** is Key4hep's way: everything from source, heavy.
  - **LCG views on CVMFS** only work on machines that mount CVMFS.
  - **Containers** freeze the whole OS in an image (`recipes/platforms/container/`); a base can live
    inside one.

## 6. Gains and costs of the base model

**Gains:**
1. **OS upgrades stop reaching the stack.** gsl, libzip, libxml2, boost and the rest change only when
   the lock changes. §2's breakage would not have happened.
2. **The interpreter is the base's.** The Python minor version is pinned in the base, not chosen by
   the OS.
3. **One package list for Linux and macOS.** It replaces `apt_packages`, the Brewfile and `mac.toml`'s
   Homebrew `[env]`, apart from a few per-platform lines.
4. **No root.** A user account on a cluster or a shared machine gets the same base: no sudo, no apt.
5. **A lock.** Every machine gets the same compiler and libraries, and the stack's provenance can
   name them.
6. **Heimdall keeps what it builds from source:** versions, patches (SISCone), native flags.
7. **A ready-made package per package**, when the hours matter more than control.

**Costs:**
1. **Integration work** in Heimdall ([03](03_Plan.md) phase 2), and two build modes while the apt path
   stays.
2. **A base update rebuilds what links the changed libraries.** That takes hours, but at a time the
   user chooses, not the OS.
3. **Builds must run inside the activated base.** The sysroot keeps `/usr/include` and `/usr/lib` out,
   so a configure script that hard-codes a system path fails instead of silently mixing. How many of
   the recipes do that is unknown until phase 1.
4. **TeX stays with the OS** unless `texlive-core` proves enough: two sources for the decks' tools.
5. **Disk:** the base and the package cache, a few GB (measured in phase 1).
6. **A conda-forge library may be built with other options than Ubuntu's.** Any difference surfaces as
   a build or verify failure in phase 1.
7. **One more tool to learn (pixi).** It is smaller than Docker: a manifest and three commands.

## 7. Unknowns only a pilot measures

| Unknown | Measured in |
|---|---|
| ROOT, ThePEG/Herwig, Sherpa, Whizard and Geant4 built with conda's compilers and sysroot: what each needs | phase 1.2–1.3 |
| every installed binary links nothing from `/usr/lib` but glibc's own libraries | phase 1.3 (`verify.py`'s scan, `recipes/verify.py:99`) |
| the base's size and install time; the package cache's size | phase 1.1 |
| `texlive-core`: Beamer and the sheets' LaTeX packages, or TeX from the OS | phase 1.1 |
| ROOT's and Geant4's OpenGL viewers through the base's `libglvnd` | phase 1.3 |
| the Mac: conda's clang with the Xcode command-line tools' SDK; how many of the 17 problems remain | phase 3.3 |
| physics and speed against the current stack: histograms within errors, time per event | phase 3.2 |
