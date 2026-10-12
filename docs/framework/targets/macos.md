# Target: macOS (Homebrew)

A Mac, Apple Silicon or Intel. The recipes are `recipes/platforms/mac/`: a `Brewfile`, `mac.toml` (the platform's fixes, laid by `build_stack.py` on macOS),
`build.sh` and `launch.sh`, moved from `High-Energy's docs/stack/mac/` (recipes/platforms/mac/README.md has every step by
hand). Only what differs from the phase files is here (D11).

## Prerequisites (P0 S1)

- **Xcode's command-line tools:** `xcode-select -p` prints a path.
- **Homebrew** (`brew --version`). A native terminal: on Apple Silicon `uname -m` is `arm64`, never
  Rosetta.
- **Homebrew's bash 5** for `hep_env.sh` (macOS's own bash is 3.2), and Python ≥ 3.11 from
  Homebrew.
- 60 GB free.

## System packages (P1 S1)

- `brew bundle --file=$HEP/recipes/platforms/mac/Brewfile` replaces apt. It includes `pandoc` and
  `poppler` for decks.
- No sudo, so no gate, but it is a download: ask with the others.
- Homebrew's own HEP formulae (`root`, `hepmc3`, `lhapdf`, `pythia`, `yoda`, `rivet`, `fastjet`)
  must not be installed (recipes/platforms/mac/README.md §5). A gate if they are.

## Overlay and launching

- **The build:** `bash $HEP/recipes/platforms/mac/build.sh packages=@primary cores=… root_cores=…`
  stands in for P1 S2's command. It runs `recipes/build_stack.py`, which lays `mac.toml` itself, with GNU
  make, sed and coreutils first on `PATH`.
- **Launching:** `recipes/platforms/mac/launch.sh` opens a bash 5 with `$HEP/setup.sh` loaded, or runs one
  command in it. The machine root's `machine.sh`, written from `mac.toml`'s `setup_extra` and sourced by
  `setup.sh`, adds `DYLD_LIBRARY_PATH` and the GNU tools.

## What the seam made portable (I15, D11, V113)

| Spot | On macOS |
|---|---|
| `runner/events.py` (the watch socket) | a socket file `hep-watch-<pid>` in `$TMPDIR/hep-watch/` (per user on macOS), removed at exit; a dead process's is cleared by the next `hep watch`. This is the one place where runtime state touches the disk (the user's rule of 2026-10-03 cannot hold without abstract sockets) |
| Paint's `basePath()` (C76) | `$HEP/src/Apps/Paint/base.toml`; `setup.sh` exports `HEP` |
| `bin/hep`'s core count | `os.cpu_count()` |
| `framework/rules.mk`'s `sed -i` | `sed -i.tmp`, then the `.tmp` removed |

## Rows that differ (P1 S3)

| Row | On macOS |
|---|---|
| R13 | `libonnxruntime.dylib`, not `.so` |
| R17 | the same file count, under `$HEP_INSTALL/fastjet/include/siscone` |
| R23 | Homebrew's versions; recorded |

Everything else is as on Ubuntu. That includes the versions of every HEP package, which are the lab
PC's.

## Allowed adjustments (02 §7)

- A Homebrew formula renamed upstream (`brew info <old>` says so): the new name, recorded.

Everything else is a gate, and above all any new line in `mac.toml`.

## Known limits

- **Not yet run on a Mac.** The recipes follow the Linux build, which the lab PC proved. Their dry
  run is tested; the real build is not. Expect gates.
- **macOS drops `DYLD_LIBRARY_PATH`** whenever one of its own programs starts (System Integrity
  Protection). The stack does not rely on it: absolute install names and rpaths (recipes/platforms/mac/README.md
  §4).
- **The test suite on macOS:** some integration tests use Linux tools (`/proc`). A test that cannot
  run there must skip with that reason, never fail silently. P2 S1's `-rs` lists them when the target
  is `macos`.
