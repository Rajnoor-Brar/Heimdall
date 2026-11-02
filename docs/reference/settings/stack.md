---
id: settings-stack
summary: every setting of the stack's build: what is built, with what, how many cores, nested as the file nests them
code: recipes/settings.toml
generated: true
---

Generated from the code; change it there. `heimdall explain <key>` says the same. From `recipes/settings.toml`. Set one on the command line (`cores=8`), in a `--config` file, or in the machine root's `machine.toml`.

# `[settings]`

[`machine`](#machine) · [`base`](#base) · [`base_python`](#base_python) · [`base_gcc`](#base_gcc) · [`base_packages`](#base_packages) · [`base_pypi`](#base_pypi) · [`packages`](#packages) · [`cores`](#cores) · [`root_cores`](#root_cores) · [`cxx_std`](#cxx_std) · [`opt_flags`](#opt_flags) · [`python`](#python) · [`system`](#system) · [`graphics`](#graphics) · [`geant4_data`](#geant4_data) · [`cuda_arch`](#cuda_arch) · [`setup_extra`](#setup_extra) · [`verify`](#verify) · [`shell_rc`](#shell_rc) · [`python_packages`](#python_packages) · [`ufo_models`](#ufo_models) · [`openloops_processes`](#openloops_processes) · [`pdf_sets`](#pdf_sets) · [`apt_packages`](#apt_packages)

## `machine`

| Type | Default | Acceptable |
|---|---|---|
| string | `""` | — |

The machine root: "": $HEIMDALL_MACHINE, else ~/Himinbjorg (forge/ base/ stack/ apps/ machine.sh)

## `base`

| Type | Default | Acceptable |
|---|---|---|
| string | `"conda"` | — |

What the stack is built with: "conda", a conda-forge base made by pixi (recipes/base.toml: compilers, libraries, Python; no root needed); "system", apt_packages (or Homebrew) and a venv.

## `base_python`

| Type | Default | Acceptable |
|---|---|---|
| string | `"3.12"` | — |

The base's Python, which the stack's bindings are built against.

## `base_gcc`

| Type | Default | Acceptable |
|---|---|---|
| string | `"15"` | — |

The base's GCC on Linux (a major version)

## `base_packages`

| Type | Default | Acceptable |
|---|---|---|
| list | `[]` | — |

More conda-forge packages for the base (scipy, pandas, "gsl 2.8.*", …): bifrost <pkg>.

## `base_pypi`

| Type | Default | Acceptable |
|---|---|---|
| list | `[]` | — |

PyPI packages for the base, by their pip names ("iminuit >=2.30"): bifrost -python <pkg>.

## `packages`

| Type | Default | Acceptable |
|---|---|---|
| string | `"core"` | — |

"core", "all", or names: "rivet pythia8" (what they need is added)

## `cores`

| Type | Default | Acceptable |
|---|---|---|
| integer | `0` | — |

How many compilers run at once (make -j<cores>, cmake --build -j<cores>); 0: the CPUs this process may use that are idle when the build starts (hyper- threads count: 24 on the lab PC), less the load of the runs going beside it.

## `root_cores`

| Type | Default | Acceptable |
|---|---|---|
| integer | `0` | — |

The same for ROOT and Rivet; 0: one per 1.3 GB of the memory available when the build starts, at most cores (12 on the idle 16 GB lab PC; fewer beside runs)

## `cxx_std`

| Type | Default | Acceptable |
|---|---|---|
| integer | `17` | — |

One C++ standard for the whole stack: ROOT, Rivet and Pythia8 share ABIs.

## `opt_flags`

| Type | Default | Acceptable |
|---|---|---|
| string | `"-O2"` | — |

## `python`

| Type | Default | Acceptable |
|---|---|---|
| string | `"python3"` | — |

Base = "system": the interpreter the venv is made from (with "conda": the base's)

## `system`

| Type | Default | Acceptable |
|---|---|---|
| true or false | `true` | — |

Base = "system": apt-get install apt_packages first (sudo when not root); false: they are there.

## `graphics`

| Type | Default | Acceptable |
|---|---|---|
| string | `"ON"` | — |

ROOT's x11/opengl/webgui/asimage and Geant4's OpenGL; "OFF" when headless.

## `geant4_data`

| Type | Default | Acceptable |
|---|---|---|
| string | `"ON"` | — |

Geant4's datasets (~4 GB), downloaded during its build.

## `cuda_arch`

| Type | Default | Acceptable |
|---|---|---|
| string | `"native"` | — |

CMAKE_CUDA_ARCHITECTURES for the GPU packages (@gpu-sim): "native", or e.g. "86;89".

## `setup_extra`

| Type | Default | Acceptable |
|---|---|---|
| list | `[]` | — |

This machine's lines, written to <machine root>/machine.sh, which gjallarhorn.sh sources.

## `verify`

| Type | Default | Acceptable |
|---|---|---|
| true or false | `true` | — |

Run a package's checks ([[<pkg>.verify]]) right after it installs; a failed check fails it.

## `shell_rc`

| Type | Default | Acceptable |
|---|---|---|
| true or false | `true` | — |

After a build: `gjallarhorn` and `bifrost` into ~/.bashrc and ~/.zshrc (a marked block; one for another checkout or machine root is left alone). false: never.

## `python_packages`

| Type | Default | Acceptable |
|---|---|---|
| list | 10 entries, in the file | — |

The Python packages (in the base, from conda-forge; or in the venv, from pip): the framework's. Add the analysis ones you want (scipy, pandas, pyhf, …).

## `ufo_models`

| Type | Default | Acceptable |
|---|---|---|
| list | `[]` | — |

What the `ufo-models` package (toolkit @bsm-models) fetches into MadGraph's models/: URLs of UFO archives (.tgz, .tar.gz or .zip), e.g. from the FeynRules model database. Empty: nothing.

## `openloops_processes`

| Type | Default | Acceptable |
|---|---|---|
| list | `["ppllj"]` | — |

What the `openloops` package installs: OpenLoops' process libraries, by name (openloops.hepforge.org's process list). One at least: Sherpa's interface needs the list a first one fetches. Each holds every crossing: ppllj serves DIS (e q → e q, + a jet), pplljj two jets; ppajj photoproduction.

## `pdf_sets`

| Type | Default | Acceptable |
|---|---|---|
| list | 21 entries, in the file | — |

What the `pdfsets` package installs: the sets the configs and the tests use (the lab PC's).

## `apt_packages`

| Type | Default | Acceptable |
|---|---|---|
| list | 51 entries, in the file | — |

Base = "system": the system packages (Ubuntu 24.04 names), by what needs them. (base = "conda": recipes/base.toml.)

# `env`

[`CXXFLAGS`](#cxxflags) · [`VIRTUAL_ENV`](#virtual_env) · [`LHAPDF_DATA_PATH`](#lhapdf_data_path)

## `CXXFLAGS`

| Type | Default | Acceptable |
|---|---|---|
| string | `"{cxxflags}"` | — |

## `VIRTUAL_ENV`

| Type | Default | Acceptable |
|---|---|---|
| string | `"{venv}"` | — |

## `LHAPDF_DATA_PATH`

| Type | Default | Acceptable |
|---|---|---|
| string | `"{dir_lhapdf}/share/LHAPDF"` | — |
