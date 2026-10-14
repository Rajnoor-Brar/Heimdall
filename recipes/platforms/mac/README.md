# The HEP stack on macOS

The same build as on Linux ([../../README.md](../../README.md)). By default it builds on a **conda base**
([docs/conda/](../../../docs/conda/README.md)): `build.sh` fetches pixi, which makes the machine root's
`base/` from conda-forge (clang, the libraries the stack links, Python, GNU sed and coreutils, a bash of
today), and the stack is built inside it; Homebrew is not needed. With `base=system` (and on an Intel Mac)
it is the way before: Homebrew's packages and Apple's clang. The build is `build_stack.py`, which lays
`mac.toml` (the platform's fixes) and this folder's file for the base under every toolkit by itself on
macOS; no recipe is copied. **The conda base on a Mac is not yet proven by a build.**

| File | Is |
|---|---|
| [mac.toml](mac.toml) | what the build does differently on macOS, whatever the base: `[settings]`, `[env]`, `[packages.<name>]`, laid on macOS by itself |
| [conda.toml](conda.toml) | with the conda base (the default): ThePEG's and Herwig's link line with the base's rpath |
| [system.toml](system.toml), [Brewfile](Brewfile) | with `base=system`: Homebrew's packages (the macOS counterpart of `apt_packages`), its search paths, GNU tools first |
| [build.sh](build.sh) | checks the machine; conda base: fetches pixi and runs `build_stack.py` with pixi's Python; `base=system`: runs `brew bundle`, puts the GNU tools first, then `build_stack.py` |
| [launch.sh](launch.sh) | moved to `launch.sh` at Heimdall's root (every platform); this one passes on to it, for older aliases |

---

## 1. By hand, once

0. **A native terminal.** On an Apple Silicon Mac, `uname -m` must print `arm64`: a Terminal set to
   "Open using Rosetta" builds x86_64 against an arm64 Homebrew, and `build.sh` refuses it.
1. **Xcode's command-line tools** (the compiler, `make`, the SDK; about 1 GB; full Xcode is not
   needed):
   ```bash
   xcode-select --install
   ```
   A dialog asks to install them. When it is done, `xcode-select -p` prints a path.
2. **Homebrew, only for `base=system`** (or an Intel Mac, where the conda base has no pixi here), from
   [brew.sh](https://brew.sh): paste its install line into Terminal (it asks for your password), then
   run the two `echo … >> ~/.zprofile` and `eval …` lines it prints at the end, so new terminals have
   `brew`. Check in a new terminal:
   ```bash
   brew --version
   ```
3. **Heimdall**, if it is not on the Mac yet:
   ```bash
   git clone <Heimdall's URL> ~/Github/Heimdall
   cd ~/Github/Heimdall
   ```
4. **Optional: pdflatex** for the sheet figures and the decks' Beamer class (TeX stays the OS's, on
   either base): [BasicTeX](https://tug.org/mactex/morepackages.html) (about 100 MB), or with Homebrew:
   ```bash
   brew install --cask basictex
   ```
   Or uncomment `cask "basictex"` in the Brewfile.
5. **Disk and time:** about 20 GB free; the core stack takes hours (ROOT alone 1–2 h). Keep the Mac
   plugged in; `caffeinate` below keeps it awake.

---

## 2. Build

From Heimdall's folder:

```bash
bash recipes/platforms/mac/build.sh --dry-run > ~/hep-build.sh     # look first: the whole build as bash; nothing installed
caffeinate -i bash recipes/platforms/mac/build.sh                  # pixi and the base, then the core stack into ~/Himinbjorg
caffeinate -i bash recipes/platforms/mac/build.sh packages=all     # and Sherpa, MadGraph, Whizard, ONNX Runtime, Geant4
bash recipes/platforms/mac/build.sh packages=@core-conda           # or the core ready-made from conda-forge: minutes
caffeinate -i bash recipes/platforms/mac/build.sh base=system      # the way before: Homebrew's packages and a venv
```

`build.sh` checks the machine (macOS, Xcode's tools, not Rosetta). On the conda base it fetches pixi
(`recipes/base.toml`'s release, checked against its sha256) into the machine root's `forge/pixi/`, and runs
`build_stack.py` with a Python pixi provides (macOS's own is too old to read TOML); `build_stack.py` then
makes the base with the same pixi. A dry run needs pixi, so the first run is a real one. With
`base=system` it checks for Homebrew, runs `brew bundle` (skip it with `BREW_BUNDLE=0`), puts GNU make, sed
and coreutils first on `PATH`, picks Homebrew's Python 3.11+, and runs `build_stack.py`. Either way
`build_stack.py` lays `mac.toml`, then `conda.toml` or `system.toml`, under every toolkit. Every
`build_stack.py` argument passes through and wins over `mac.toml`: `cores=8`, `root.release=6.40.06`,
`packages="rivet pythia8"`. Stamps (`stack/.stamps/`), logs (`forge/logs/<package>.log`), resuming and
`--list` are as on Linux ([../../README.md §1](../../README.md#1-quick-start)). `mac.toml`'s `setup_extra`
lines go to the machine root's `machine.sh`, which `setup.sh` sources.

---

## 3. Launch

```bash
~/Github/Heimdall/launch.sh                    # a bash with Heimdall's setup.sh loaded (hep_status shows the stack)
~/Github/Heimdall/launch.sh root -l            # one command in that environment
```

The environment (`env/hep_env.sh`) is bash, and macOS's login shell is zsh, with a bash 3.2:
`launch.sh` runs the base's bash 5 (or Homebrew's, with `base=system`) with your `~/.bashrc` and
`setup.sh`. Inside a bash already,
`source ~/Github/Heimdall/setup.sh` does the same; zsh sourcing it is turned away. For a zsh
shortcut, in `~/.zshrc` (an older alias to `recipes/platforms/mac/launch.sh` still works):

```bash
alias load_hep="$HOME/Github/Heimdall/launch.sh"
```

Then, in the launched shell, the framework against the new stack:

```bash
hep build --framework && make -C "$HEP" test
```

---

## 4. What mac.toml changes

On the conda base, the base gives what Homebrew gave (the libraries, GNU sed and coreutils, a bash of
today, pandoc and poppler) and `conda.toml` holds the one fix it needs; the table's Homebrew rows are
`system.toml`'s, for `base=system`.

| What | Linux | macOS |
|---|---|---|
| system packages | the base; or `apt-get install apt_packages` | the base; or `system = false` and `brew bundle` (Brewfile), by build.sh |
| compiler search paths | the system's | Homebrew's: `CPPFLAGS`, `LDFLAGS`, `CMAKE_PREFIX_PATH`, `BOOST_ROOT` (ThePEG and Herwig find Boost and GSL there) |
| OpenSSL | the system's | Homebrew's keg-only `openssl@3`: `OPENSSL_ROOT_DIR` for ROOT and its builtin xrootd |
| ROOT's graphics | X11, OpenGL, web GUI, AfterImage | `graphics = "OFF"` (no X11), then `root.extra`: Cocoa, OpenGL, web GUI, AfterImage |
| Geant4's viewer | OpenGL/X11 | none (`graphics = "OFF"`) |
| libraries found by | `LD_LIBRARY_PATH` | absolute install names: libtool's own (LHAPDF, YODA, Rivet, ThePEG, Herwig, Whizard) and `CMAKE_INSTALL_NAME_DIR` for HepMC3, Delphes, Geant4; rpaths from `root-config`, `fastjet-config`, `pythia8-config`; `DYLD_LIBRARY_PATH` as well |
| fjcontrib's shared library | `libfastjetcontribfragile.so` | `.dylib` (the `{dylib}` placeholder) |
| ONNX Runtime | `onnxruntime-linux-<arch>` | `onnxruntime-osx-<arm64 or x86_64>` |
| setup.sh | the stub | the stub, then `DYLD_LIBRARY_PATH` and GNU make, sed, coreutils first on `PATH` (`setup_extra`) |
| decks (`hep deck`) | `pandoc`, `poppler-utils`, `texlive-latex-recommended` (apt) | `pandoc`, `poppler` (Brewfile); the Beamer class comes with BasicTeX or MacTeX |

---

## 5. Known limits

- **Proven once** (2026-10-12: an M4, macOS 27, AppleClang 21, Homebrew GCC 16, `@primary`). That
  first build needed fixes that are now `mac.toml` lines, each with its reason: ThePEG and Herwig
  (libc++, GSL, `-lc++`, type_info across plugins) and Whizard (`CXXLIBS`). Herwig's 8-byte Fortran
  integers and Whizard's PDF sets are in `recipes/toolkits/standard.toml`, for every platform. The whole story:
  `docs/audit_3/01_Process.md`.
- **Your shell is zsh; the environment is bash.** Load it with `launch.sh` (above); `source setup.sh`
  in zsh is turned away, with nothing changed. `hep quit` takes `DYLD_LIBRARY_PATH` and the GNU tools
  out again (`machine.sh`'s lines are recorded when they are sourced).
- **`hep run`'s watch socket** (`framework/runner/events.py`) uses Linux's abstract socket namespace;
  on macOS it falls back to a socket file in `$TMPDIR` (docs/framework/06_Seam.md, S2).
- **DYLD_LIBRARY_PATH** is dropped by macOS (System Integrity Protection) whenever one of Apple's own
  programs starts, `/usr/bin/env` and `/bin/sh` among them, and so for most scripts. The stack does
  not rely on it: its libraries carry absolute install names or rpaths (the table above).
- **No Homebrew HEP formulae alongside:** Homebrew's own `root`, `hepmc3`, `lhapdf`, `pythia`,
  `yoda`, `rivet` or `fastjet` would sit on the build's search paths ahead of the stack's. Remove
  them first (`brew uninstall root`, …).
