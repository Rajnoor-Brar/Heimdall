---
id: stack
summary: how build_stack.py builds the stack: settings and their layers, cores, resuming, downloads, adding a package, what each package is
code: recipes/build_stack.py, recipes/settings.toml, recipes/toolkits/standard.toml, recipes/machine.py
---

# Building the stack

`build_stack.py` builds the software Heimdall runs on, into the machine root. The data says what is built; the engine knows five steps (fetch, unpack, configure or cmake, install, stamp) and five kinds of package: `autotools`, `cmake`, `unpack`, `none` and `external`. A version bump, flag or package is a TOML edit, never a code change. Every setting: [stack settings](../../reference/settings/stack.md).

| File | Is |
|---|---|
| `toolkits/standard.toml` | every recipe; its header documents every key |
| `toolkits/` | one file per toolkit: [toolkits](toolkits.md) |
| `settings.toml` | the run's settings, each with its default |
| `base.toml` | the conda base: [base](base.md) |
| `verify.py` | a package's checks, after it installs and in `heimdall doctor` |
| `machine.py` | `where`; `adopt` moves a stack built inside a checkout, by links and moves only |
| `patches/` | patches the sources need |
| `build_by_hand.txt` | the same build as commands to paste (Ubuntu 24.04) |

`heimdall stack build|list|status|doctor` wraps it (on macOS, `platforms/mac/build.sh`). Sources and builds stay in `forge/`; `stack/` holds installs only.

## Settings and layers

`key=value` for any setting (`cores=8 graphics=OFF`), `<package>.<key>=value` for a package (`root.release=6.40.06`, `fastjet.patch=`), `key+=value` appends to a list, `env.VAR=…` and `<package>.env.VAR=…` set one variable. `--config my.toml` for many.

**The layers, lowest first:** the recipes (`standard.toml`, then the machine root's `recipes.toml`) and `settings.toml`; the base's; the platform's fixes; the toolkits asked for, each after what it extends; `machine.toml`; `--config` files; the command line. `--list @<toolkit>` says which layer changed which value.

**`machine.toml`,** written once from a template and yours to edit, is a layer of `[settings]`, `[env]` and `[packages.<name>]`. A list appends to the shipped one, unless its table says `replace = ["pdf_sets"]`; anything else replaces. `[cluster]` holds `heimdall cluster`'s defaults.

```toml
[settings]
cores = 20
setup_extra = ["module load gcc/13"]

[packages.root]
args = ["-Dcuda=ON"]          # after ROOT's own arguments
```

**Cores.** `cores` is how many compilers run at once; `0` takes the CPUs idle when it starts, logical CPUs less the load average. `root_cores` is ROOT's and Rivet's, because each compiler takes memory: `0` gives one per 1.3 GB available, at most `cores`. At every core, Rivet's once took a 14 GB machine down.

**Choosing packages.** `packages = "core"`, `"all"`, a toolkit (`packages=@lab`), or names (`packages="rivet pythia8"`). What a named package needs is added; order is `standard.toml`'s.

## Resuming and rebuilding

A finished package is stamped (`stack/.stamps/<name>-<release>`, holding its recipe's digest) and skipped, so the same command resumes after a failure, a reboot or Ctrl-C. A changed release builds. A recipe changed otherwise is named, never rebuilt by itself: `--rebuild <package>` builds it, with every installed package needing it. A `.building` marker means the attempt did not finish. A package installed another way, its probe file there, is used as it is. Source is unpacked afresh each time. The C++ standard of a built stack cannot change in place: an isolated toolkit builds another.

**After an OS upgrade.** On the base, nothing but glibc comes from the OS. With `base=system`, `heimdall doctor` names what no longer resolves, and `--rebuild-broken` rebuilds exactly those and their dependents.

## Downloads

Every tarball is fetched first, four at a time, so a dead link stops the run in its first minute. A `url` may list mirrors; a download resumes and retries; a web page, cut-off file or wrong `sha256` is refused and named. `--check-urls` asks every URL first, `--sha256` prints checksums as recipe lines. A tarball already in `forge/downloads/<name>-<release>.<ext>` is used as it is, so a machine with no network can build from copied tarballs.

`--dry-run` prints the whole build as a bash script (`--resume`: only what the prefix lacks); `--platform mac --dry-run` another platform's. `--toolkits` lists the toolkits, `--base` makes the base only, `--update-base` brings its packages to their newest first. Each package logs to `forge/logs/<name>.log`; a failure stops at once, prints its first error lines with a line of context and the log's last 15, and names the log.

## A new package

A `[packages.<name>]` table, best in the machine root's `recipes.toml`, as one of standard's for every toolkit:

```toml
[packages.mytool]
release  = "1.2"
url      = "https://example.org/mytool-{release}.tar.gz"
kind     = "cmake"
needs    = ["root", "hepmc3"]
args     = ["-DWITH_ROOT={dir_root}"]    # stack/root, or the base when ready-made
base     = ["boost-cpp"]                 # what it needs in the base
optional = { "root >=6.30" = ["-DWITH_RNTUPLE=ON"], hdf5 = ["-DWITH_HDF5={dir_hdf5}"] }
```

`optional`'s keys are a package and a version spec. `{dir_<pkg>}`, `{bin_<pkg>}`, `{version_<pkg>}` name another package's folder, programs and version. `status = "new"` marks a recipe no build has proven yet. `kind = "external"` is never built: its `how` says where it comes from. `apt = [...]` and `base = [...]` are a package's own system packages.

## The core packages

`heimdall stack list` shows each with its release, and `--list` what this run would build. `lhapdf` and `pdfsets` (PDFs); `hepmc3`, `hepmc2` (events); `fastjet`, `fjcontrib` (jets, patched for SISCone); `root` (Paint, App_yd2rt, Delphes, modules); `yoda`, `rivet`; `pythia8` (with ROOT's and Rivet's plugins, built after them); `thepeg`, `herwig`; `delphes`. Extra: `sherpa`, `madgraph`, `whizard`, `onnxruntime`, `geant4`, `hdf5`.

**Known caveats.** MadGraph and ONNX Runtime rename releases often: on a 404, set `madgraph.url`. Delphes 3.5.1 works with ROOT 6.40 here, but upstream has not released against it. Geant4's datasets need network during its build. CMSSW and Key4hep come from CVMFS in a container; never mix their environment with this stack's. Pip wheels of FastJet or HepMC3 do not match the stack's symbols: every compiled HEP library is built here.

Why recipes are as they are: [build-fixes](build-fixes.md).
