---
id: platforms
summary: what differs on Ubuntu and on macOS; what is proven and what is not
code: recipes/platforms/mac/build.sh, recipes/platforms/mac/mac.toml, recipes/platforms/mac/conda.toml, recipes/platforms/mac/system.toml
---

# Platforms

## Ubuntu

The primary target: every recipe was proven on 24.04. A newer Ubuntu brings a newer GCC, glibc and Python; the suspects, in build order, are ROOT against the new Python, ThePEG and Herwig (C++ headers no longer included transitively), Whizard's OCaml, Sherpa. The way out is usually a newer release (`<package>.release=…`), which moves versions. Byte-identical gates may fail on a new compiler: that is a decision, not a fault.

With `base=system`, a `-dev` package with no candidate may be dropped if its only user builds its own copy (`libpcre3-dev`: confirm in the log that ROOT switched on its builtin), and a renamed package with the same source package may be substituted, recorded.

## macOS

**The conda base on a Mac is not yet proven by a build,** and the recipes have not run on a Mac end to end. Expect failures to judge. `build_stack.py` lays `platforms/mac/mac.toml` and this base's `conda.toml` or `system.toml` by itself; `--platform mac` shows them anywhere.

1. **A native terminal.** On Apple Silicon, `uname -m` must print `arm64`: `build.sh` refuses Rosetta.
2. **Xcode's command-line tools:** `xcode-select --install`, about 1 GB.
3. **Homebrew,** only for `base=system` or an Intel Mac, where the conda base has no pixi. Homebrew's own HEP formulae (`root`, `hepmc3`, `lhapdf`, `pythia`, `yoda`, `rivet`, `fastjet`) must not be installed.
4. **Optional pdflatex:** BasicTeX, about 100 MB.
5. **Disk and time:** about 20 GB, and hours. Keep it plugged in.

```bash
bash recipes/platforms/mac/build.sh --dry-run > ~/heimdall-build.sh     # look first
caffeinate -i bash recipes/platforms/mac/build.sh                        # the base, then the core stack
```

`launch.sh` opens a bash with the environment; macOS's own bash is 3.2. `machine.sh`, from `mac.toml`'s `setup_extra`, adds `DYLD_LIBRARY_PATH` and GNU tools. macOS drops `DYLD_LIBRARY_PATH` whenever one of its own programs starts, so the stack relies on absolute install names and rpaths. The watch socket is a file in `$TMPDIR/heimdall-watch/`. Some integration tests use `/proc`, and must skip with that reason.
