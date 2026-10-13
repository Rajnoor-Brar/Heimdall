# 02 — Design

How a conda base fits the machine root. The HEP tools stay built from source. The base takes over what
apt, Homebrew and the venv provide today ([01 §1](01_Assessment.md#1-todays-layers)). Code citations
are at `864c0f4`.

"Base" here is Heimdall's word for this layer. It is not conda's own `base` environment: pixi has none.

## 1. Layout in the machine root

```
~/Himinbjorg/
  base/                        the base: a pixi workspace
    pixi.toml                  written by build_stack.py from recipes/base.toml (+ toolkits, machine.toml)
    pixi.lock                  Heimdall's recipes/base/pixi.lock, or solved here when the list differs (§2)
    .pixi/envs/default/        the prefix: bin/ lib/ include/ share/ …   ($HEP_BASE)
    activate.sh                `pixi shell-hook`'s output, written at install: a login never runs pixi
  forge/pixi/bin/pixi          the pixi binary (PIXI_HOME)
  forge/downloads/conda/       pixi's package cache (PIXI_CACHE_DIR), beside the source archives
  stack/  apps/  …             as today
  venv -> base/.pixi/envs/default   a link, while {venv} and HEP_VENV are still read
```

- **pixi is fetched by `build_stack.py` like any archive:** retries, checks, a `sha256` per platform
  (V116). It goes into `forge/pixi/`, not `stack/`, because it builds the stack and is not part of it
  (the user's forge rule).
- **The prefix cannot move.** Like the stack and today's venv, it carries absolute paths
  (`recipes/machine.py:12`–`13`). `machine.py adopt` links it as it links those.
- **An isolated toolkit shares the machine's base.** An isolated toolkit (`stacks/<kit>/`,
  `setup.sh:35`–`43`) changes the C++ standard of the stack, not the base's C libraries. One whose
  toolkit adds base packages (§2) gets `stacks/<kit>/base/` of its own.

## 2. The package list and its lock

`recipes/base.toml` (tracked) replaces `apt_packages` (`recipes/settings.toml:40`), `python_packages`
(`:25`), the Brewfile and `mac.toml`'s Homebrew `[env]`. Like `apt_packages`, it lists each package by
what needs it. It splits **libraries**, which the stack links, from **tools**, which the build and the
decks run. §4 explains why.

```toml
# recipes/base.toml — the base: conda-forge packages, by what needs them
[base]
channels  = ["conda-forge"]
platforms = ["linux-64", "linux-aarch64", "osx-arm64"]
python    = "3.12.*"                   # the stack's bindings are built against it
compilers = "15.*"                     # gcc/gxx/gfortran (Linux), clang/clangxx (macOS): pinned majors

[base.libraries]                       # linked by the stack: a change here makes it stale (§4)
root      = ["libxml2", "fftw", "libsqlite", "xorg-libx11", "xorg-libxpm", "xorg-libxft", "xorg-libxext",
             "liblzma-devel", "pcre2", "glew", "giflib", "ftgl", "graphviz", "libcurl", "libuuid", "krb5",
             "openssl", "tbb-devel", "zstd", "zlib"]
herwig    = ["gsl", "libboost-devel"]
lhapdf    = ["yaml-cpp"]
sherpa    = ["libzip", "bzip2", "libsqlite"]
whizard   = ["ocaml", "ocaml-findlib", "bdw-gc"]
geant4    = ["xerces-c", "libgl-devel", "libglu", "xorg-libxmu", "xorg-libxi"]
framework = ["tomlplusplus", "zstd", "zlib"]

[base.tools]                           # run, not linked: a change rebuilds nothing
build = ["make", "cmake", "pkg-config", "autoconf", "automake", "libtool", "patch", "git", "curl",
         "ca-certificates", "sed", "coreutils", "bash"]
decks = ["pandoc", "poppler"]          # TeX stays with the OS until texlive-core is proven (01 §7)

[base.python]                          # the framework's Python packages
packages = ["numpy", "cython", "tomli-w", "rich", "pyyaml", "pillow", "matplotlib-base", "uproot",
            "awkward", "pytest"]
pypi     = []                          # what conda-forge lacks: pixi's pypi-dependencies

[base.osx-arm64]                       # one platform's differences
drop = ["libgl-devel", "libglu", "xorg-libxmu", "xorg-libxi", "ocaml-findlib"]
```

- **A toolkit or `machine.toml` may add to the base** with a `[base]` table of the same shape (for
  example `@gpu-sim`: `libraries.gpu = ["cuda-toolkit"]`). A user's own analysis packages go there
  too.
- **The lock is tracked:** `recipes/base/pixi.lock`, solved for every platform of the list.
  - A machine whose list equals Heimdall's installs it with `pixi install --frozen`, so every such
    machine gets the same base.
  - A machine with additions solves its own `base/pixi.lock`, and `hep stack status` says "local
    lock".
- **An update is deliberate.** `hep stack base --update` solves again and prints the changes package
  by package, separating libraries from tools. Heimdall's lock changes only by a commit.

## 3. Building inside the base

`build_stack.py` gains a base mode. It is a layer, like the Mac's (`mac.toml`), written in
`recipes/base.toml`:

```toml
[settings]
system = false                         # no apt-get: the base is the system (as mac.toml:9)
python = "{base}/bin/python"

[env]
CPPFLAGS          = "-isystem {base}/include"
LDFLAGS           = "-Wl,-rpath,{base}/lib -Wl,-rpath-link,{base}/lib -L{base}/lib"
CMAKE_PREFIX_PATH = "{base}"
PKG_CONFIG_PATH   = "{base}/lib/pkgconfig:{base}/share/pkgconfig"
```

- **The build's environment** is the clean environment (V117), then the base's activation, then this
  `[env]`.
  - The activation is read once: `bash -c 'source base/activate.sh; env -0'`.
  - It gives the compilers (`CC`, `CXX`, `FC`: `x86_64-conda-linux-gnu-*`) and `CMAKE_ARGS` (their
    `ar`, `ranlib`, …), which every cmake recipe receives.
  - `--dry-run`'s script sources `activate.sh` at its top.
- **The compilers use the base's sysroot.** `/usr/include` and `/usr/lib` are not searched, so a
  dependency missing from the base fails at configure. It is never taken silently from the OS.
- **Heimdall's flags win.** `{cxxflags}` (`opt_flags`, native) replaces the activation's `CXXFLAGS`
  (conda's `-march=nocona -mtune=haswell …`). The `-isystem` of `CPPFLAGS` stays.
- **The clean environment keeps the base.** `clean_environment` (`recipes/build_stack.py:1023`)
  drops `CONDA_PREFIX` and a conda env's `PATH` entries today. In base mode it keeps the base's prefix
  and still drops any other conda env or venv.
- **ROOT uses the base's libraries** where it has a `builtin_*` choice (`standard.toml:120`: freetype,
  pcre, xrootd's own dependencies). The base layer's `[packages.root] extra` turns those builtins off,
  as `mac.toml` adds Cocoa.
- **Python:** the `python` recipe (`standard.toml:55`–`62`) makes no venv in base mode. It only writes
  `heimdall.pth` into the base's site-packages (`recipes/pth.py`). The bindings are built against
  `{base}/bin/python`.
- **The stack still installs into `stack/<pkg>/`.** Its binaries reach the base's libraries through
  the rpath in `LDFLAGS`, and each other through `LD_LIBRARY_PATH` as today.

## 4. The stack's identity

- **A stamp holds a digest of the package's recipe** (`recipes/build_stack.py:40`, `:507`). In base
  mode the digest also covers **the base's libraries and compilers**: their names, versions and build
  strings, read from `pixi.lock`. A change in `[base.tools]` (pandoc, cmake) changes no stamp.
- **A package built on other libraries is listed "stale (the base changed)"** by `--list` and
  `hep stack status`. The next build rebuilds it and its dependents, after saying so.
  `--rebuild-broken` (`:606`) stays for a library that vanished.
- **Point identities are unchanged in mechanism.** Each tool's executable is hashed (`exe_sha256`,
  `framework/runner/tools.py:981`). The first stack built on the base changes every executable, so
  every point reruns once, as V122's portable paths did.
- **Provenance names the base.** `provenance.json` (`framework/runner/record.py:386`) records the base
  lock's hash beside the git states, so `hep reproduce` can say which base a result came from.

## 5. The runtime

- **`setup.sh` loads the base, then the stack.**
  - It sets `HEP_BASE=<machine>/base/.pixi/envs/default`.
  - It sources `base/activate.sh` through `_hep_source_recorded` (`env/hep_env.sh:86`), so
    `hep quit` takes out exactly what the activation set.
  - Then come the stack's folders, as today (`env/hep_env.sh:224`–`236`).
- **The user's shell keeps part of the activation.** It keeps `PATH`, `CONDA_PREFIX` and the
  compilers (`CC`, `CXX`, `FC`). It drops `CFLAGS`, `CXXFLAGS`, `CPPFLAGS` and `LDFLAGS`, so
  `rules.mk`'s own `CXXFLAGS ?= -O2` (`framework/rules.mk:25`) stays Heimdall's.
- **A module finds the base's libraries by rpath.** `rules.mk` adds `-Wl,-rpath,$(HEP_BASE)/lib` when
  `HEP_BASE` is set. A module built with conda's g++ then finds the base's `libstdc++` at run time,
  never the OS's.
- **`$HEP_BASE/lib` is never on `LD_LIBRARY_PATH`.** The base's libraries are found through rpaths.
  The OS's own programs (git, ssh, the desktop's) keep the OS's `libssl` and `libstdc++`. The stack's
  own `lib/` folders stay on `LD_LIBRARY_PATH` as today (`env/hep_env.sh:231`–`232`).
- **Python:**
  - `HEP_VENV` is `HEP_BASE`, so `bin/hep` (`framework/bin/hep:12`–`14`) runs the base's Python
    unchanged;
  - `source $HEP_VENV/bin/activate` (`env/hep_env.sh:222`) is replaced by the activation;
  - `import ROOT, rivet, yoda, pythia8, lhapdf, pyHepMC3` works in that one interpreter.
- **The rest is unchanged:**
  - the tool search path and the `{stack}` placeholder (`framework/runner/paths.py:350`), since
    `stack/` is unchanged;
  - `env/flags.sh`, which probes the `*-config` programs on `PATH`. Its key changes with the stack, so
    `flags.mk` is probed again (`framework/rules.mk:35`–`38`).

## 6. Ready-made packages

- **A toolkit or `machine.toml` may take a package ready-made:** `[packages.root] from = "conda-forge"`,
  optionally with `release = "6.40.04"`.
  - `build_stack.py` adds the package to the base's list instead of building it.
  - Its `probe` and `verify` checks run against the base.
  - Its dependents build against it through `PATH` (`root-config`) and `CMAKE_PREFIX_PATH`.
- **One copy of each package.** A ready-made package's conda dependencies are ready-made too, so none
  of them may also be built from source. `build_stack.py` reads the dependency tree in `pixi.lock` and
  refuses with a reason: "rivet from conda-forge brings fastjet-cxx: take fastjet from conda-forge too
  (unpatched), or build rivet".
- **`hep stack list` shows where each package comes from:** `source` or `conda-forge <version>`.
  Patches and build options are Heimdall's only for `source`.
- **Default: nothing ready-made.** The use case is a laptop that wants ROOT in minutes, not in an
  hour.

## 7. Platforms

| Platform | What changes |
|---|---|
| Linux x86_64, aarch64 | §1–§6 as written |
| macOS arm64 | The Brewfile, `mac.toml`'s Homebrew `[env]` (`:22`–`25`) and its gnubin `PATH` lines become base entries. `mac.toml` keeps its package fixes (ThePEG's libc++ macros, …) where they are still needed. The compilers are conda's clang 23, with the Xcode command-line tools' SDK, which is still required because Apple's SDK is not redistributable. Whizard has no `ocaml-findlib` for osx-arm64, so it needs findlib from source or stays out. |
| a cluster or shared machine | pixi is a user-space binary and the base lives in the user's machine root: no sudo. A node without internet gets the locked env from a `pixi-pack` archive. |
| a container | The image needs glibc only. The base is installed from the lock inside it (`recipes/platforms/container/`). |

## 8. What stays outside the base

| Outside | Why |
|---|---|
| glibc, the kernel | the base is built against an older glibc (the sysroot), so a newer OS runs it |
| the GPU driver, the X server, GL vendor drivers | hardware; the base's `libglvnd` dispatches to the OS's driver |
| TeX | until `texlive-core` is proven for Beamer and the sheets (01 §7) |
| Mathematica (FeynRules, SARAH) | licensed; already `external` |
| CVMFS stacks (Key4hep, CMSSW) | already `external`, in shells of their own (`recipes/README.md` §6) |
| Docker, Apptainer, Slurm | system services |

## 9. This machine

- **The pilot is a separate machine root,** `HEP_MACHINE=~/Himinbjorg-base`. Untouched:
  - today's `~/Himinbjorg` (linked to `~/HEP/install` and `~/HEP/.venv`);
  - `~/HEP` itself;
  - High-Energy.
- **The source archives are shared.** The pilot's `forge/downloads` links to the current machine
  root's, so nothing is downloaded twice. Only pixi and the base's packages are new downloads.
- **If adopted** ([03](03_Plan.md) step 3.3), the machine root's stack is rebuilt on the base. Point
  identities change once. `~/HEP` retires when High-Energy does: the user's call.
