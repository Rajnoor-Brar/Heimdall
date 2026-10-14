# 03 — Plan

Three phases of three steps. Each step names its tasks, its verification rows (each producing a
number or a yes/no that can be checked), and a Log filled in when it is done.

**What happened (2026-10-14).** The user ordered the implementation before phase 1: the base as the
default, from source inside it, plus ready-made toolkits. Phase 2 was done directly (V140, V141), and
phase 1 became the verification of that code in two scratch machine roots; their findings are the Logs
of 1.2 and 2.1–2.3 below. Phase 3 is pending.

**Nothing is built without the user's order, phase by phase.** Every download is asked first: the
file, its source and its size. `~/HEP`, its venv, today's `~/Himinbjorg` and High-Energy are not
touched. Phase 1 writes no Heimdall code. A finished step of phase 2 gets a V-row in
[07_Record](../07_Record.md).

---

## Phase 1 — The base by hand, in a scratch machine root

The question for this phase: can today's recipes build the core stack inside a conda base, and what
does each package need? No Heimdall code changes. What the phase learns becomes phase 2's input.

**1.1 pixi and the base**
- Make the scratch machine root `~/Himinbjorg-base`, with `forge/downloads` linked to today's.
- Download pixi into `forge/pixi/bin/` (ask first: the binary's release, URL and size).
- Write `base/pixi.toml` by hand from [02 §2](02_Design.md#2-the-package-list-and-its-lock)'s list,
  for linux-64 only, then `pixi install` (ask first: the solve's download size).
- Write `activate.sh` with `pixi shell-hook`. Check what it sets (`CC`, `CXX`, `FC`, `CMAKE_ARGS`,
  the flags).
- Check `texlive-core`: does it hold Beamer, and the packages `framework/plot`'s sheets and the decks
  load?

| Row | Expected / recorded |
|---|---|
| `pixi install` | succeeds; **minutes taken** and **the prefix's size in GB** recorded |
| `forge/downloads/conda` | **its size in GB** recorded |
| `$CXX --version`, `$CXX -print-sysroot` in the activated shell | conda's g++ 15.x; the sysroot inside the base |
| `$CXX -x c++ -E -v - < /dev/null` | the include search list holds no `/usr/include` |
| `python -c "import numpy, matplotlib, uproot, awkward, rich, tomli_w, yaml, PIL"` | ok |
| `texlive-core` | yes or no for Beamer and each package the sheets load; no → TeX stays with the OS |

Log (2026-10-14, by `build_stack.py --base` in `~/Himinbjorg-conda`, not by hand): pixi 0.81.0 fetched
and checked; 206 packages, Python 3.12.15, conda-forge's GCC 15.3.0, whose sysroot (glibc 2.28) keeps
`/usr/include` out; 2.3 GB, plus a 298 MB cache; 33 s. Nothing landed in `~/.pixi` or `~/.cache`.
`texlive-core` not tried: TeX stays the OS's.

**1.2 The core from source inside it**
- Print today's build with `build_stack.py --dry-run` and edit it by hand into a script that sources
  `activate.sh` first and uses [02 §3](02_Design.md#3-building-inside-the-base)'s `[env]`.
- Build into the scratch root, in recipe order: LHAPDF, HepMC3, FastJet (with the SISCone patch),
  fjcontrib, ROOT, YODA, Rivet, Pythia 8, plus the PDF sets (copied from today's, not downloaded).
- Log every problem with its cause and fix, the way [audit 3's Mac notes](../audit_3/01_Process.md)
  were kept: these become phase 2's recipe changes.

| Row | Expected / recorded |
|---|---|
| each of the 8 packages | builds; **minutes taken** against the lab PC's build log for the same package |
| problems met | **a count**, each with its cause and fix |
| `ldd` of every binary and library under the scratch `stack/` | **the count of libraries resolved under `/usr/lib`** other than glibc's own (`libc`, `libm`, `libdl`, `libpthread`, `librt`, `ld-linux`): expected 0 |
| `import ROOT, rivet, yoda, pythia8, lhapdf, pyHepMC3` in the base's Python | ok |
| `rivet-build` of the fixture's `photo_eic.cc` | builds and loads (`rivet --list-analyses photo_eic`) |

Log (2026-10-14, `build_stack.py` in `~/Himinbjorg-conda`): LHAPDF, HepMC3, FastJet (with the patch),
fjcontrib and YODA built from source in the base, their checks passing; `ldd` of `libYODA.so`: nothing
outside the machine root but glibc's, found by the base's rpath. Rivet's build was stopped before its end
(below), before the lab PC's reinstall. Problems met, 3: the
configure scripts of YODA, Rivet and ThePEG looked for zlib in `/usr` and added `-I/usr/include`, and
ThePEG's and Herwig's looked for GSL "on the system" (`--with-zlib`, `--with-gsl` = the base, in
`base.toml`); `base_hash` was never computed (`c["base"]` is the prefix, not "conda"); Rivet's analysis
libraries, one compiler run of several GB each, at every core exhausted 14 GB of RAM and took the
machine down (`rivet.cores = "{root_cores}"`). ROOT, Pythia 8 and the rest not built here yet.

**1.3 The rest, and Heimdall's checks**
- Build ThePEG and Herwig, Sherpa, Delphes, Whizard (with LHAPDF), MadGraph (unpacked), and Geant4
  without its data if time is short.
- Run Heimdall's package checks: the `verify` tables of `recipes/toolkits/standard.toml`, through
  `recipes/verify.py`, against the scratch stack.
- Open ROOT's OpenGL viewer and Geant4's once, to check `libglvnd` with the OS's GL driver.

| Row | Expected / recorded |
|---|---|
| each package | builds; minutes taken; problems counted as in 1.2 |
| the `verify` checks | **passed / total**, for every package built (the lab PC today: 101 ok, 7 FAIL, mostly the 26.04 breakage) |
| Herwig's and Sherpa's smoke runs (the verify rows) | run; on today's stack they exit 127 |
| `ldd` scan as in 1.2, over every package | 0 libraries from `/usr/lib` but glibc's (and the GL vendor's when loaded) |
| the GL viewers | open, or a recorded reason |

Log: —

**Decision point after phase 1:** the user reads the logs and decides whether to go on to phase 2.

---

## Phase 2 — Integration in Heimdall

The question for this phase: is the base a supported way to build and run the stack, with
`build_stack.py`, `setup.sh` and `hep` handling it?

**2.1 The list, the lock, and builds in the base**
- `recipes/base.toml`: the list and the layer of [02 §2–§3](02_Design.md#2-the-package-list-and-its-lock).
- `build_stack.py`:
  - a `base` mode (`base = true` in `settings.toml`, `machine.toml` or a toolkit);
  - pixi fetched and checked (V116);
  - `pixi.toml` written, and `pixi install --frozen` against `recipes/base/pixi.lock`, or a local
    solve;
  - the activation read into the build's environment, and `clean_environment` keeping the base;
  - phase 1's recipe changes;
  - stamps carrying the libraries' hash ([02 §4](02_Design.md#4-the-stacks-identity));
  - `--dry-run` sourcing `activate.sh`;
  - `hep stack base --update`.
- `recipes/base/pixi.lock` solved for linux-64, linux-aarch64 and osx-arm64, and tracked.

| Row | Expected |
|---|---|
| `build_stack.py base=true packages=core` in a fresh scratch root | the core stack, with no hand edits; **minutes**; every `verify` check passes |
| a tools-only lock change (pandoc's version) | no package stale |
| a libraries change (gsl's build) | ThePEG, Herwig and ROOT listed "stale (the base changed)" |
| `CONDA_PREFIX` of another env in the user's shell | dropped from the build; the base kept |
| `tests/runner/test_stack_build.py` with new base-mode tests | pass |

Log (2026-10-14, V140): `base = "conda"` (not `true`), the default; a root with a `venv/` and no
`base/` stays `"system"`. `base.toml`: pixi's release and sha256 per platform, `[base.libraries]` and
`[base.tools]` by what needs them, a layer for the builds (`{cflags}`, `{ldflags}`: `-isystem` and the
rpath). The lock is each machine's own (`base/pixi.lock`), not yet tracked. Stamps hold `base_hash`
(the libraries, compilers, C++ runtime, Python). The sysroot is unpinned: the newest the solve allows
(2.28, pixi's floor), or 2.17 when a ready-made ROOT, built against it, is in the base. conda-forge's
toml++ ships no pkg-config file: the base gets `base/pkgconfig/tomlplusplus.pc`. `--base`,
`--update-base`. `test_stack_build.py`'s base tests pass.

**2.2 The shell and `hep`**
- `setup.sh` / `env/hep_env.sh`:
  - `HEP_BASE`;
  - `activate.sh` sourced through `_hep_source_recorded`;
  - the flags dropped from the user's shell;
  - no `$HEP_BASE/lib` on `LD_LIBRARY_PATH`;
  - `HEP_VENV` = `HEP_BASE`.
- `framework/rules.mk` gets the base's rpath.
- `machine.py` handles `base/` in `where` and `adopt`.
- `hep stack status` and `hep doctor` show the base: its lock's hash, Python, compilers, the package
  count, and stale stamps.
- `provenance.json` records the base lock's hash.

| Row | Expected |
|---|---|
| `source setup.sh`, then `hep quit` | the environment as before, variable for variable (the shell tests' check) |
| a module built by `hep build` | `readelf -d` shows the base's rpath; it runs with no `LD_LIBRARY_PATH` entry for the base |
| `git --version`, `ssh -V` in the loaded shell | the OS's binaries, linking the OS's `libssl` |
| `hep doctor` | clean on the scratch root |
| fast suite with the base stack loaded | **passed / total** |

Log (2026-10-14, V140): `setup.sh` sets `HEP_BASE` (and `HEP_VENV` to it) when `base/activate.sh`
exists; `hep_env.sh` sources it recorded, so `quit` restores the shell variable for variable (a shell
test); the base's `lib/` never joins `LD_LIBRARY_PATH`. `rules.mk` adds `-isystem`, `-L` and the
rpath (its commas escaped: a bare one split `$(if)`), and puts the stack's `-std` last (conda-forge's
`pythia8-config` says `-std=c++11`). The flags cache is keyed on `PKG_CONFIG_PATH` and `DELPHES_DIR`
too, and keeps its time when a re-probe finds the same flags. `framework/bin/hep` runs the base's
Python without the environment. `hep doctor` shows the base and the ready-made rows. Provenance does
not record the lock's hash yet; the fast suite on a base stack is phase 3's.

**2.3 Ready-made packages, and the documents**
- `from = "conda-forge"`, with the one-copy rule ([02 §6](02_Design.md#6-ready-made-packages)) and
  `hep stack list`'s source column.
- The manual:
  - 05 (the build and the environment);
  - `recipes/README.md` (the base mode; `apt_packages` kept for the apt path);
  - the fresh-machine runbook `docs/framework/` (P0 preflight: pixi, not apt);
  - 06's layout;
  - V-rows.

| Row | Expected |
|---|---|
| `[packages.root] from = "conda-forge"` in a test toolkit | ROOT from the base; YODA and Rivet build against it; verify passes |
| ready-made `rivet` with source `fastjet` | refused, naming `fastjet-cxx` |
| `make docs`, `test_docs.py` | pass |

Log (2026-10-14, V141): `from = "conda-forge"` and the one-copy rule; `@conda` (a layer) and
`@core-conda`, `@lab-conda`, `@primary-conda`, `@generators-conda`. `@core-conda` in the scratch root
`~/Himinbjorg-conda-ready`: the base with the ready-made core, 387 packages, in 45 s; every check run
and reported, none fatal (fjcontrib: conda-forge's build lacks the separate contrib libraries); then
`hep build --framework` (every app, by rpath, nothing from `/usr/lib` but glibc's), `hep doctor --quick`
(34 ok, 1 MISSING), and the guide's example in a scratch work dir: its modules built, `hep check` 13
configurations, `hep run Demo/jets single` in 2 minutes with its 19 pages. Found on the way:
conda-forge builds ROOT for C++20 and 23 only, so a ready-made ROOT makes the stack C++20 and the base
asks for that build (`conda_std`); a root built with a ready-made set is read as such without it (a
recipe whose package is in the base and not in `stack/`); a module using `Module.hh` links ROOT when
ROOT's headers are in the base.

---

## Phase 3 — Trial and decision

The question for this phase: does the base stack give the same physics, at a comparable speed, on
both machines? And should it become the default?

**3.1 The slow suite on the base stack**
- Run the slow suite alone (one pytest session at a time), with the scratch root's stack loaded.

| Row | Expected |
|---|---|
| the slow suite | **passed / total**. Today's stack: 36 passed, 3 failed (Herwig, Sherpa, the three-generator test: exit 127). Expected here: all pass |

Log: —

**3.2 Physics and speed against today's stack**
- Use `hep setup --example jets` in a scratch work dir, and a copy of a real study's work dir.
- Run the same configurations on both stacks, with the seeds fixed: a single point at 100 000 events,
  and one sweep.
- Pythia's release differs (8318 against 8317), so compare statistically, not bit for bit.

| Row | Expected / recorded |
|---|---|
| every histogram of the runs | χ²/ndf against today's stack: **the distribution recorded**; expected consistent within errors |
| time per event, per generator | **the ratio base / today** (native flags on both) |
| `hep run … --dry-run` identities | all differ (new executables), as [02 §4](02_Design.md#4-the-stacks-identity) says |

Log: —

**3.3 The Mac, and the decision**
- On the Mac (osx-arm64), with the user: the base from the tracked lock, then `@primary` built in it.
- Count which of the 17 problems of the first Mac build still occur.
- Put the decision to the user:
  - should the base be the default for fresh machines (`docs/framework/` runbook), keep the apt path
    as an option, or retire it?
  - should the lab PC's machine root be rebuilt on the base?

| Row | Expected / recorded |
|---|---|
| the base on the Mac | installs from the tracked lock; **minutes**, **GB** |
| `@primary` on the Mac | builds; **the count of the 17 problems that remain**, each with whether a base fixed it |
| the `verify` checks on the Mac | **passed / total** (the Mac today: 116 ok, 0 FAIL) |

Log: —
