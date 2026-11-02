---
id: build
summary: make, heimdall build, the rules, // requires:, the flag cache, and what rebuilds what
code: Makefile, framework/rules.mk, framework/work.mk, env/flags.sh, env/stack.toml, env/stack.py
---

# The build

`make`, `env/flags.sh`, and `heimdall build` = `make all`. Two makefiles share `framework/rules.mk`:

- **Heimdall's `Makefile`** (`heimdall build --framework`) builds apps and C++ tests. Intermediates are in `forge/make/`; outputs follow the loaded stack (`$HEIMDALL_APPS`, `$HEIMDALL_FORGE`), so apps link against the stack that runs them. **Rebuilding one changes identities:** see [invariants](../../rules/invariants.md).
- **A work dir's `Makefile`** is `include $(HEIMDALL)/framework/work.mk`: its modules and plugins, all in its `build/`.

Run make with the environment loaded: without it, `rules.mk` stops, as `$HEIMDALL` is unset.

## The rules

| Source | Target | Output | Include path |
|---|---|---|---|
| `src/App_<X>.cc` | `src/App_<X>.exe` | `$HEIMDALL_APPS/App_<X>.exe` | `-I $HEIMDALL/src` |
| `src/Apps/<X>/main.cc` | `src/Apps/<X>.exe` | `$HEIMDALL_APPS/<X>.exe` | also `-I src/Apps/<X>/` |
| `tests/cxx/<X>.cc` | `tests/cxx/<X>.exe` | `forge/tests/<X>.exe` | `-I $HEIMDALL/src` |
| `modules/<A>/<X>.cc` | `modules/<A>/<X>.exe` | `build/<A>/<X>.exe` | `-I $HEIMDALL/src -I modules/<A>` |
| `modules/<A>/Rivet/<x>.cc`, `Rivet_<x>.cc` | `….so`, `rivet_<x>` | `build/Rivet/Rivet_<x>.so` + `<x>.info`, `.plot`, `.yoda` | `rivet-build …`, same |
| any `<dir>/<X>.cc`, named | `<dir>/<X>.exe`, `.so` | `build/<dir>/…` (Heimdall's: `forge/make/<dir>/…`) | `-I $HEIMDALL/src` |

- The typed target is a phony alias of the real file, so make's up-to-date check works on the real file.
- `-MMD -MP` writes header dependencies to `deps/`.
- Every output depends on `flags.mk`, so a re-probe rebuilds what linked the old one. A re-probe finding the same flags keeps the cache's time and rebuilds nothing.
- A plugin's `.info`, `.plot` and `.yoda` copies are real targets. A `.info` saying `Requires: ONNX` adds ONNX's flags.
- `make all` in a work dir builds every non-parked program and plugin (`_`-prefixed folders are parked; a subfolder of an assignment holds headers). In Heimdall: every app, and `$HEIMDALL_APPS/Herwig/HerwigDefaults.rpo` when Herwig is on `PATH`.
- Other targets: `configure`, `list`, `clean`; Heimdall's also `tests`, `test`, `test-slow`, `schema`, `docs`. Do not use `test`: [invariants](../../rules/invariants.md).
- Compiler: `CXX` (`g++`), `CXXFLAGS` (`-O2`), and the stack's C++ standard (`stack/.stamps/cxx_std`; 17 when absent).

## `// requires:`

A source names its libraries in a comment near the top; a trailing `(…)` is a note.

```cpp
// requires: pythia8 hepmc3 fastjet   (the kit adds hepmc3 toml)
```

Names are `env/stack.toml`'s (`pythia8`, `hepmc3`, `yoda`, `root`, `fastjet`, `lhapdf`, `rivet`, `geant4`, `toml`, `zstd`, `zlib`, `onnx`, `delphes`).

- `none` links nothing. `pkg:<name>` links any library pkg-config knows, asked when the source is built.
- **No line** links every library found: a quick compile works, just slower to link.
- `#include "Module.hh"` adds `hepmc3 toml`, and `root` when ROOT is ready-made in the base.
- An unknown name, or one whose `*-config` was not found, is a make error saying which.

## The flag cache

The stack is one file, `env/stack.toml`: each library's flags command (or install directory) and version command. A new library is one entry. `env/stack.py` reads it for `flags.sh`, for tool folders (`[identity] version = "stack:<name>"`) and for `heimdall status --stack`. `heimdall_env.sh` keeps its own list, as it runs at login and stays bash-only.

`flags.mk` (`build/flags.mk`, Heimdall's `forge/make/flags.mk`) holds every library's flags, `FOUND` and `KNOWN`. `flags.sh` writes it, running each `*-config` once, and records a key: every `*-config`'s resolved path, install directories (`HEIMDALL_INSTALL`, `ONNXRUNTIME_DIR`, `DELPHES_DIR`), `PKG_CONFIG_PATH`, the stack file's checksum. Make recomputes the key every call and rewrites on a difference; `heimdall build --configure` forces it. `flags.log` records each probe.

**L22** A cache must be keyed on everything it reads, such as `PATH` and install roots: keyed on less is a correctness bug.
