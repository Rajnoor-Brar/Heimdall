---
id: base
summary: the conda base: what it holds, what stays the OS's, updating it, and base=system
code: recipes/base.toml, recipes/build_stack.py, framework/runner/bifrost.py
---

# The base

"Base" is Heimdall's word: a pixi workspace at `<Himinbjorg>/base/`, not conda's own `base` environment. Before any package, pixi (fetched once into `forge/pixi/`, checked against `base.toml`'s sha256) makes it from conda-forge: Python (`base_python`), GCC (`base_gcc`; clang on macOS), build tools, the libraries the stack links, `python_packages` and `base_packages`, and PyPI's `base_pypi`. So it needs no apt, no sudo and no Homebrew, and an OS upgrade no longer reaches the stack. HEP tools are still built from source inside it, unless taken ready-made.

`recipes/base.toml` lists packages by what needs them, splitting **libraries**, which the stack links and which make it stale when changed, from **tools**, which do not. A recipe's own go in its `base = [...]`; yours through `bifrost`. pixi solves them into `base/pixi.lock`.

Every build runs inside it: its compilers, whose sysroot keeps `/usr/include` and `/usr/lib` out, its headers, an rpath to its libraries. Its `lib/` never joins `LD_LIBRARY_PATH`. The prefix cannot move, as it carries absolute paths; `machine.py adopt` links it.

**What stays the OS's:** glibc and the kernel, GPU and GL drivers, and TeX.

**Updating:** `--base` makes or brings it up to date alone; `--update-base` takes packages to their newest first. A stamp holds what the base's libraries were: an update changing one marks what was built on it "changed" (`--rebuild` it); a tool's update marks nothing.

Nothing keeps a separate list of what is installed: the stamps, the base's `conda-meta` and `machine.toml` are the record. `heimdall stack status` shows it.

## `base=system`

The way before, and what a Himinbjorg made before the base stays on: the run installs `settings.toml`'s `apt_packages` with apt-get, through sudo (or Homebrew on a Mac), and makes a venv. On a distribution without apt, install the same packages under its names and run with `system=false`.

Why a conda base, and what it cost: [decisions](../design/decisions/stack.md).
