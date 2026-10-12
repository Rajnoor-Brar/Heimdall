# 01 — The process

From a fresh machine to a first plot, the process has five parts:
1. clone;
2. build the stack;
3. load the environment;
4. build Heimdall's apps;
5. make a work dir, then run.

On the lab PC the stack was grown by hand over months. On the Mac it was built from the recipes for
the first time, and it met 17 problems, logged as they came. This page groups them into the patterns
behind them, adds what the stack audits found on both machines, and says what the process lacks.
The problems one by one are in the [appendix](#appendix-the-mac-build-problem-by-problem).

`BS` is `recipes/build_stack.py`; `PK` is `recipes/packages.toml`; `MT` is
`recipes/platforms/mac/mac.toml`.

---

## 1. Nine patterns

### A. Upstream drift — U2 (45)

Projects move their downloads, and a recipe pins one URL.
- **Pythia:** pythia.org moved its tarballs from `/download/pythia83/` to `/releases/pythia83/`. The
  old path now returns 404 for every release, 8317 included (`PK:103`), so **a fresh machine cannot
  fetch Pythia at all**.
- **Rivet and YODA:** they moved to `cedar-tools.web.cern.ch/downloads/`. HepForge's list stops at
  Rivet 4.1.3, and its `?f=` link answers an HTML page for anything newer (`PK:90,96`).
- **Versions bumped by hand:** on the Mac they were raised by editing `packages.toml` (YODA 2.1.4,
  Rivet 4.1.4, Pythia 8318, MadGraph 3.8.1). That leaves an uncommitted Heimdall, with nothing
  recording why.

**Fix:**
- each package gets a list of URLs (mirrors) and a `sha256` for its release;
- `build_stack.py --check-urls` sends a HEAD request to every recipe's URL;
- versions move by recipe change, not by local edit (phase 1.1).

### B. Downloads are never verified — U1 (40), U3 (24)

- **"Fetched" means only "exists and is not empty"** (`BS:382`). The real fetch is urllib, with no
  retry and no resume (`BS:392-404`).
- **What gets kept:**
  - **an HTML page served with status 200** (HepForge's links) is kept as the tarball and fails later
    at `tar`. Every rerun reuses it until it's deleted by hand (Mac §9).
  - **a cut-off download** is kept as complete (Mac §10: Pythia, `truncated gzip input`).
  - **a server that announces a length and then stops** raises `http.client.IncompleteRead`. That is
    not an `OSError`, so it escapes the handler (`BS:399`) as a traceback.
- **pip has no timeout or retry settings** (Mac §2: PyPI read timeouts).
- **`--dry-run` prints a different downloader** (`curl -fL --retry 3`, `BS:386`). It also skips
  stamped packages, installed dependencies and archives already present, so the "whole build as bash"
  is not the build.

**Fix:**
- one downloader for both modes, with resume and retries;
- every archive checked: gzip, xz or bzip2 magic, `tar -t` succeeds, the size matches;
- a bad file deleted with a message that names what arrived ("the server sent a web page, not the
  archive: <url>");
- pip run with `--timeout` and `--retries` (phase 1.1).

### C. The host leaks into the build — U4 (32), U5 (32), U6 (32)

- **The environment is only added to.** The build starts from the user's environment and prepends to
  it (`BS:516-518`).
  - A leftover `ROOTSYS` and `LD_LIBRARY_PATH` in `~/.zshrc`, from an older stack, made ROOT's
    configure strip its "other ROOT" from the library path. That tripped a ROOT CMake bug (Mac §3).
  - Homebrew's prefix is on every compile (`MT [env]`), so Homebrew's own HEP formulae can shadow
    the stack's. The Brewfile warns about this, but nothing checks it.
- **Optional dependencies are auto-detected.** autotools packages switch features on when they happen
  to find a library.
  - YODA found an HDF5 that Homebrew had installed for Octave, enabled its H5 extension, and broke
    its own link (Mac §5).
  - The same YODA on the lab PC has no H5, because no HDF5 was there.
- **The opposite case: Whizard on both machines was built without LHAPDF,** although its recipe says
  `--enable-lhapdf`. Its `lhapdf_*` functions are stubs, and no LHAPDF library is linked (check_stack
  on both machines). Nothing failed.

**Fix:**
- **a hermetic build environment:** `ROOTSYS`, `DYLD_*`, `LD_LIBRARY_PATH`, `PYTHONPATH` and
  `CMAKE_PREFIX_PATH` are reset, then the stack's own paths added;
- **every optional dependency explicit** in its recipe (`--disable-h5`, or `--with-hdf5=<stack>`;
  Whizard's LHAPDF given by path);
- **a preflight** that lists what conflicts: Homebrew HEP formulae, another `ROOTSYS`, the shell
  (phase 1.2).

### D. Toolchain drift — U8 (40)

New compilers and a new OS broke old autotools packages in six separate ways (Mac §11–§16):

| Package | Cause | What fixed it |
|---|---|---|
| ThePEG, Herwig | libc++ drops the C++17 removals (`std::mem_fun` …), which libstdc++ keeps | `-D_LIBCPP_ENABLE_CXX17_REMOVED_{BINDERS,UNARY_BINARY_FUNCTION,RANDOM_SHUFFLE,AUTO_PTR}` |
| ThePEG | its `--with-gsl=system` expects GSL on the default include path | `--with-gsl={HOMEBREW_PREFIX}/opt/gsl` |
| ThePEG | linked with `-flat_namespace -undefined suppress`: libThePEG records no libc++ dependency, so its static initialisers ran before libc++'s, and macOS 27's typed `operator new` aborted | `LDFLAGS=… -lc++` |
| Herwig | Looptools needs `-fdefault-integer-8`; `m4/herwig.m4:147-151` adds it only for `x86_64-*` and `*-darwin1*`, and an M4 is `aarch64-apple-darwin2x` | `FFLAGS`/`FCFLAGS` with `-fdefault-integer-8` |
| ThePEG, Herwig | class descriptions keyed by `type_info` address; across plugin libraries on arm64 macOS the address differs, so a class lost its base's interfaces | `-DTHEPEG_DYNAMIC_TYPE_INFO_BUG` (ThePEG's own switch) |
| Whizard | its configure filters `-lto_library` only when it can read Xcode's version; with only the Command Line Tools it can't | `CXXLIBS=-lc++` |

None of these is in a recipe yet: they live in the ignored notes, and the next Mac would repeat them
all. The table is the content of `mac.toml`'s next version, each line with its reason, and the
upstream version it applies to (phase 1.3).

### E. Silent capability loss — U7 (27), U54 (28)

- **Nothing asks what a finished build can do.**
  - Whizard without LHAPDF (C) was found only by the stack audit.
  - So was the lab PC's ROOT after Ubuntu 26.04. `libMathMore.so` needs `libgsl.so.27`, and
    `hist2workspace` needs `libxml2.so.2`, both gone with the upgrade. `import ROOT` and plain fits
    still work, so nothing showed.
- **The same pattern appears at run time.** A module's config is read with defaults and never checked
  for unknown keys (`src/Module.hh` has no such check). So a typo in `[tools.<module>.config]` runs
  silently with the default. Heimdall already guards Rivet against exactly this (undeclared analysis
  options; L19).

**Fix:**
- **a `verify` per package in `packages.toml`:** the features it must have (`root-config --features`
  has `mathmore`; `pythia8-config --with-lhapdf6` is true; Whizard links LHAPDF), checked after it
  installs;
- **`hep doctor`** runs every `verify`, plus a link scan and short smoke runs, whenever asked. Its
  seed is `check_stack.sh`, which already does this (phase 2.1). Module key checks are phase 4.2.

### F. Poor observability — U13 (24)

- **No progress:** a package prints `==> name` when it starts (`BS:555`) and "done in N min" when it
  ends (`BS:565`; 0 for anything short). ROOT was silent for 26 minutes, and Herwig longer.
- **The failure shows the last 30 log lines** (`BS:375-377`). In a parallel make that is mostly other
  files' warnings: ThePEG's real error was a few hundred lines up, under 191 warnings. The user had to
  `grep` for it.
- **Each attempt wipes the package's log** (`BS:561`), so a retry loses the previous failure.

**Fix:**
- a status line per package (step, elapsed time, `[i/N]`, CMake's `[ 42%]` when there is one) and a
  3-line window onto the log;
- on failure, the log's first `error:`/`Error`/`fatal` lines with context, then the tail;
- logs kept per attempt (phase 1.3).

### G. Override and stamp traps — U9 (32), U10 (28), U11 (24), U12 (35)

- **Stamps are name + release** (`BS:243`).
  - A change of args, extra, URL, patch, `opt_flags`, `python_packages`, `pdf_sets` or `ufo_models`
    never triggers a rebuild. `recipes/README.md:130` advises adding packages to `python_packages`,
    which then does nothing.
  - The system step's stamp counts packages (`system-<n>`, `BS:447`).
  - Forcing a rebuild means deleting a stamp file. On the Mac a zsh glob error aborted the `rm`, and
    "done already" followed.
- **Probes and stamps disagree.**
  - A probe file stops only a *dependency* from being added (`BS:343`), while a *chosen* package
    without a stamp is always rebuilt (`BS:543`). On the lab PC (no stamps) `--list` says
    "installed / build" for every core package.
  - ThePEG and Herwig install into one folder, so deleting one deletes both.
- **The command line is the only override surface, and a thin one.**
  - `[env]` can't be set from it.
  - `thepeg.env=X=1` is accepted, then crashes in `build()` after every download (`BS:420`).
  - A list value is split on spaces and replaces the overlay's list: `root.extra=…` on a Mac silently
    drops `MT:29`'s Cocoa flags.
  - The ThePEG/Herwig fixes took four `pkg.extra=` and `opt_flags=` arguments, with nested quoting.
- **No ABI guard from the command line.** `cxx_std=20` on the default stack is accepted (only
  toolkits are guarded, `BS:297`), and `stack/.stamps/cxx_std` is rewritten every run (`BS:537`).

**Fix:**
- **a machine overlay** (`machine.toml`, see [02 §3](02_Organisation.md#3-the-proposed-layout)) with
  merge semantics for lists and tables;
- **stamps that carry a digest** of the package's resolved recipe;
- **`--rebuild PKG`**, and one "installed" rule (a stamp, else a `verify` that passes);
- **the ABI guard for every source of `cxx_std` and `opt_flags`** (phases 1.3, 3.1).

### H. The docs promised parity — U15 (21), U14 (20), U17 (10), U18 (10)

- **The macOS annex** (`docs/framework/targets/macos.md`) said "everything else is as on Ubuntu";
  the Mac took 17 fixes.
- **The README's quick start** runs `python3 recipes/build_stack.py`, which on a Mac fails with "no
  apt-get" (`BS:452`) instead of pointing to `recipes/platforms/mac/build.sh` (the flag `MAC` is
  already set, `BS:64`).
- **Small inconsistencies:**
  - `build.sh` picks Python 3.13 while the Brewfile installs 3.12;
  - the Brewfile says `hep` uses `nproc`;
  - the mac README still says "not yet run on a Mac";
  - planning words reach users ("a failure is a gate (docs/framework/02_Agents.md §6)", `BS:555`).

**Fix:**
- a **support matrix**: platform × package × last verified (date, machine, `hep doctor` result);
- **a second-platform build in CI**: the container recipe, at least on Linux;
- the README's quick start per platform (phases 2.2, 7.2).

### I. OS upgrades break a working stack — U16 (27)

The lab PC's move to Ubuntu 26.04 replaced system libraries under the stack's feet:
- Herwig needs `libgsl.so.27`;
- Sherpa needs `libzip.so.4`;
- ROOT's MathMore and `hist2workspace` need `libgsl.so.27` and `libxml2.so.2`;
- the venv's Python 3.12 was removed (worked around with a standalone CPython).

Nothing recorded which system libraries the stack links, or noticed the change.

**Fix:**
- `hep doctor`'s link scan names every unresolved library and the package that needs it;
- `build_stack.py --rebuild-broken` rebuilds exactly those packages and what depends on them;
- the install records the system libraries it was built against (phase 2.3).

---

## 2. What the process lacks

1. **A check step.** No step between "built" and "first run" says the machine is good (`hep doctor`).
2. **A first run.** The README ends at `hep setup`. Nothing says `hep check`, then `hep run`, then
   where the pages are ([05 §4](05_CLI.md#4-from-nothing-to-a-first-plot--u63-28-u14)).
3. **A machine identity.** Heimdall doesn't record which machine and platform a stack was built for,
   or with which fixes. The Mac's workarounds lived in a shell history.
4. **Updates.** There is no `build_stack.py --upgrade PKG=VERSION` that moves a version, checks the
   URL and sha256, and rebuilds what depends on it. Local edits stand in for it.
5. **A second platform in the loop.** Every recipe was proven on one machine.

---

## Appendix: the Mac build, problem by problem

An Apple M4 (10 cores), macOS 27.0 (Darwin 27), AppleClang 21, Homebrew GCC 16.2 (gfortran),
CMake 4.4, Python 3.13 (Homebrew). `@primary` with the user's newer versions.

| § | Symptom | Cause | Workaround that worked | Pattern |
|---|---|---|---|---|
| 1 | `no apt-get` | `build_stack.py` run directly, not through `build.sh` | `bash recipes/platforms/mac/build.sh` | H |
| 2 | pip `ReadTimeoutError` (PyPI) | slow network; pip's 15 s timeout, no retry settings | rerun (`PIP_DEFAULT_TIMEOUT=120`) | B |
| 3 | ROOT configure: `string sub-command REGEX … needs at least 6 arguments` (CMakeLists.txt:85) | `ROOTSYS`/`LD_LIBRARY_PATH` of a deleted older stack in `~/.zshrc`; ROOT's "strip the other ROOT" code fails on a path list with a trailing `:` | remove those lines; new terminal | C |
| 4 | an hour of silence per package | no progress output | `tail -f forge/logs/<pkg>.log` | F |
| 5 | YODA: `/bin/sh: -ldl: command not found` at `libYODA.la` | a Homebrew HDF5 (Octave's) auto-detected; its `h5cc` flags broke the link line | `yoda.extra=--disable-h5`; later a stack HDF5 and a plain `h5cc` wrapper | C |
| 6 | (request) HDF5 in the stack | no recipe; only `libhdf5-dev` for two toolkit packages | HDF5 2.2.0 by hand (CMake) into `stack/hdf5`; `hdf5` added to `_HEP_PACKAGES` | — |
| 7 | `_hep_prepend:2: bad substitution` | `setup.sh` sourced in zsh; `hep_env.sh` is bash; it half-loads, and an exported guard then fools child shells | `recipes/platforms/mac/launch.sh` from a new terminal | — (05 §5) |
| 8 | YODA + HDF5 2.x | YODA reads HDF5 through `h5cc`; HDF5 2.x is CMake-only | a plain `h5cc` wrapper in `forge/` | C |
| 9 | `tar: Unrecognized archive format` (Rivet 4.1.4) | HepForge served an HTML page; releases moved to CEDAR | `rivet.url=https://cedar-tools.web.cern.ch/downloads/Rivet-{release}.tar.gz` | A, B |
| 10 | `truncated gzip input` (Pythia 8318) | a cut-off download; also pythia.org moved to `/releases/` | `curl -C - --retry 5` by hand, `gzip -t` | A, B |
| 11 | ThePEG: `no member named 'mem_fun'` | libc++ at C++17 | the four `_LIBCPP_ENABLE_CXX17_REMOVED_*` macros | D |
| 12 | ThePEG: `'gsl/gsl_rng.h' file not found` | `--with-gsl=system` | `--with-gsl=/opt/homebrew/opt/gsl` | D |
| 13 | `setupThePEG` aborts: typed `operator new` before libc++'s initialiser | no libc++ dependency recorded (flat namespace) | `LDFLAGS=-L/opt/homebrew/lib -lc++` (`-fno-typed-cxx-new-delete` did not help) | D |
| 14 | Herwig Looptools: `Parameter 'nz2' … does not reduce to a constant` | `-fdefault-integer-8` only for x86_64 / old Darwin | `FFLAGS`/`FCFLAGS` with it | D |
| 15 | Herwig: `The interface 'AlphaQCDISR:ScaleFactor' was not found` | `type_info` addresses differ across plugin libraries | `-DTHEPEG_DYNAMIC_TYPE_INFO_BUG`, ThePEG and Herwig both rebuilt | D |
| 16 | Whizard: `-lto_library library filename must be 'libLTO.dylib'` | its Xcode-version filter skipped with only the Command Line Tools | `whizard.extra="'CXXLIBS=-lc++'"` | D |
| 17 | MadGraph options: `lhapdf` not set | the recipe's `sed` found no `lhapdf =` line in 3.8.1's file | a Python edit that sets each key whether present, commented or missing | A |
| 18 | stack audit | — | Mac 116 ok / 0 FAIL; lab PC 101 ok / 7 FAIL | E, I |

The Mac's final state, from its stack audit:
- **Working:**
  - ROOT 6.40.04 with every feature and Cocoa;
  - YODA 2.1.4 **with** HDF5;
  - Rivet 4.1.4 (2047 analyses);
  - Pythia 8.318, all six `--with-*` true;
  - Herwig 7.3.0, `LHC.in` read and 10 events run;
  - Sherpa 3.0.5, MadGraph 3.8.1, Whizard 3.1.8, Geant4 11.4.2 (multithreading, GDML, 12 data sets);
  - LHAPDF and its 21 sets;
  - no unresolved library.
- **Open:**
  - Whizard without LHAPDF (on both machines);
  - ONNX Runtime not at the expected path;
  - Heimdall's own apps not yet built (`hep build --framework`).
