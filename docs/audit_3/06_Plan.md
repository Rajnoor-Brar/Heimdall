# 06 — The remediation plan

Seven phases, 2–3 steps each. Each step names:
- the findings it closes (U-ids from [README.md](README.md));
- the files it touches;
- its verification rows.

**Nothing is built without the user's order, phase by phase.** A finished step gets a V-row in
[07_Record](../07_Record.md) and is marked done here.

**Suggested order:**
1. Phases 1 → 2 → 3, so the next machine is easy and the lab PC can be checked and repaired.
2. Phases 4 and 6, the user-facing core (6 builds on 4's tool typing).
3. Phases 5 and 7.

Phase 7.3's doc fixes can go first at any time: they help today's users.

---

## Phase 1 — Build reliability

**1.1 Downloads** (U1, U2, U3, U17) — **done, V116**
- `recipes/build_stack.py` (`fetch`):
  - one downloader for the build and `--dry-run`: resume, 5 retries with backoff, a read timeout;
  - every archive checked (magic bytes, `tar -t` or `unzip -l`, size against Content-Length,
    `sha256` when the recipe has one);
  - a bad file deleted with a message naming what arrived (an HTML page, `n` of `m` bytes);
  - `IncompleteRead` caught.
- `recipes/packages.toml`:
  - `url` may be a list (mirrors);
  - `sha256` per package;
  - Pythia → `/releases/pythia83/`;
  - Rivet and YODA → `cedar-tools.web.cern.ch/downloads/` (HepForge as the second mirror);
  - the newer versions the Mac proved (the user's decision): YODA 2.1.4, Rivet 4.1.4, Pythia 8318,
    MadGraph 3.8.1. The lab PC takes them at its repair (2.3).
- `--check-urls`: a HEAD request to every chosen package's URLs, no download.
- pip runs with `--timeout 60 --retries 10`.
- `--dry-run` reads stamps only with `--resume`. By default it prints the whole build.

| Row | Expected |
|---|---|
| an HTML page served for a package | refused at download: "the server sent a web page, not the archive: <url>"; nothing kept |
| a download cut at 50 % | resumed on rerun; `tar -t` passes |
| `--check-urls packages=@primary` | every URL answers 200 (after the URL changes) |
| `--dry-run` on a fresh Heimdall | lists every package of the set, with curl lines that resume and retry |

**1.2 A hermetic build and a preflight** (U4, U5, U6, U14) — **done, V117**
- `build_stack.py`'s environment:
  - starts from a clean set: `PATH` = the system's and the stack's, `HOME`, `TMPDIR` and the locale;
  - `ROOTSYS`, `LD_LIBRARY_PATH`, `DYLD_*`, `PYTHONPATH` and `CMAKE_PREFIX_PATH` are reset, then
    filled from the stack.
- Every optional dependency is explicit:
  - YODA `--disable-h5`, or `optional = { hdf5 = ["--enable-h5", "--with-hdf5=…/h5cc"] }` with an
    `hdf5` recipe (1.14.6, autotools; or 2.x with the `h5cc` shim of the Mac notes);
  - Whizard's LHAPDF given by path (find why `--enable-lhapdf` gave stubs);
  - the same review for every autotools package.
- A preflight before any download, listing what will cause trouble:
  - Homebrew HEP formulae (root, hepmc3, fastjet, lhapdf, pythia, yoda, rivet), and an untrusted
    tap's;
  - another `ROOTSYS` in the environment;
  - the shell (zsh, for the environment later);
  - free disk;
  - `build_stack.py` started on macOS without the Mac overlay → "run recipes/platforms/mac/build.sh".

| Row | Expected |
|---|---|
| `ROOTSYS=/elsewhere` set, then a ROOT build | builds; the log shows `ROOTSYS` unset |
| Homebrew HDF5 present, YODA built | no H5 unless the stack's HDF5 is chosen |
| Whizard built | `ldd`/`otool -L` of `libwhizard` shows LHAPDF; `hep doctor` row ok |
| `python3 recipes/build_stack.py` on a Mac | one line naming `build.sh` |

**1.3 The Mac's fixes as data, stamps, progress** (U8, U9, U10, U11, U12, U13, U18) — **done, V118**
- `recipes/platforms/mac/mac.toml`, from [01 D](01_Process.md#d-toolchain-drift--u8-40):
  - ThePEG and Herwig: the four libc++ macros, `--with-gsl`, `LDFLAGS=… -lc++` and
    `THEPEG_DYNAMIC_TYPE_INFO_BUG`;
  - Herwig: `-fdefault-integer-8`;
  - Whizard: `CXXLIBS=-lc++`;
  - the Brewfile: `tbb`, and agreement with `build.sh` on Python.

  Each line carries its reason and the versions it was proven on.
- Stamps are `<name>-<release>-<digest>`, where the digest covers the resolved recipe (args, extra,
  env, url, patch, `opt_flags`, `cxx_std`, the package lists). A change rebuilds that package and its
  dependents.
- `--rebuild PKG…`.
- One "installed" rule: a stamp, or a `verify` (2.1) that passes.
- ThePEG and Herwig in separate install folders, or one recipe.
- Overrides:
  - `machine.toml` (3.1) with merge semantics: lists append unless `!replace`, tables merge;
  - `[env]` and package `env` settable;
  - list values from the command line split only on commas.
- The ABI guard covers the command line and `machine.toml`. `cxx_std` is stored as configuration
  (`stack/stack.toml`), not as a stamp.
- Progress:
  - a status line per package (`[i/N]`, step, elapsed time, CMake's percentage) and a 3-line window
    on a terminal;
  - plain lines otherwise;
  - on failure, the first error lines with context, then the tail;
  - logs kept per attempt.
- Planning words out of user output.

| Row | Expected |
|---|---|
| a fresh Mac, `build.sh packages=@primary` | builds with no command-line extras (the 17-problem build, minus the network) |
| `opt_flags` changed, rerun | the packages whose digest changed rebuild; others "done already" |
| `--rebuild thepeg` | ThePEG and its dependents (Herwig) rebuild |
| a compile error in a parallel make | the error line is shown, not only the last 30 lines |

---

## Phase 2 — Verification

**2.1 `hep doctor`** (U7, U33)
- `check_stack.sh` (now in Heimdall's ignored `.setup/`) becomes a framework command, `hep doctor`,
  in Python. It is driven by a `verify` table per package in `packages.toml`:
  - `features`: `root-config --features ⊇ […]`; `pythia8-config --with-lhapdf6 = true`;
  - `links`: Whizard links LHAPDF;
  - `run`: a smoke run with an expected line.
- Plus a link scan of every binary, the PDF sets, the venv's packages, and Heimdall's apps.
- One row per check: ok / MISSING / FAIL / n/a.
- `hep stack build` runs a package's `verify` right after it installs.
- `bots/` moves out of git (it is agent state), or `.setup/`'s tools move into it: one rule.

| Row | Expected |
|---|---|
| `hep doctor` on the lab PC today | the 7 FAILs of the audit (Herwig, Sherpa, ROOT MathMore, `hist2workspace`) and Whizard's LHAPDF |
| `hep doctor` on the Mac today | 0 FAIL; Whizard's LHAPDF MISSING; ONNX path MISSING |
| `hep doctor --quick` | no smoke runs, under 10 s |

**2.2 A support matrix and a second platform** (U15)
- `recipes/README.md` holds a table of platform × package × last verified (date, machine,
  `hep doctor` summary), written by `hep doctor --record`.
- A CI job builds the container recipe's core set, then runs `hep doctor` and the fast tests.
- The macOS annex (`docs/framework/targets/macos.md`) is rewritten from the Mac's build: what differs,
  and why.

**2.3 After an OS upgrade** (U16)
- The install records the system libraries each package links (sonames).
- `hep doctor` compares them with what's there now.
- `build_stack.py --rebuild-broken` rebuilds the packages with unresolved libraries, and their
  dependents.

| Row | Expected |
|---|---|
| the lab PC: `--rebuild-broken --dry-run` | lists Herwig (and ThePEG), Sherpa and ROOT (MathMore: gsl; RooFit: libxml2), with the missing sonames |
| after the rebuild | `hep doctor`: 0 FAIL |

---

## Phase 3 — The machine root and the shell

**3.1 The machine root, `~/Himinbjorg`** (U19, U20, U24, U26, U29)
- The machine root, as in [02 §3](02_Organisation.md#3-the-proposed-layout), by default
  `~/Himinbjorg` (the user's choice):
  - `machine.toml`;
  - `forge/{downloads,src,build,logs}` (`stash/` retired, by the user's rule);
  - `stack/`, `venv/`, `apps/`, `stacks/<kit>/`;
  - `toolkits/`, `patches/`, `tools/`.
- `setup.sh` finds the root:
  1. `$HEP_MACHINE`;
  2. else `~/Himinbjorg`.
- `paths.py` gains `machine_root()` and `{apps}`.
- `setup_extra`, `[cluster]` defaults and recipe overrides move into `machine.toml`.
- `hep setup --machine <root>` creates one or adopts an existing install (by moving or linking; the
  lab PC's `~/HEP/install`).

| Row | Expected |
|---|---|
| `git -C ~/Github/Heimdall clean -xdn` | lists nothing of the stack, venv or apps |
| two checkouts with one `HEP_MACHINE` | both run; one stack |
| Heimdall moved to another folder | `hep doctor` passes without a rebuild |

**3.2 Toolkits as files, one package registry** (U26, U34)
- The toolkits of [04 §5](04_Extending.md#5-toolkits-the-stacks-build-configurations), the user's
  design:
  - `recipes/toolkits/standard.toml` holds every recipe, with its groups, conditional flags and
    `verify`;
  - one file per toolkit (`lab.toml` → `@lab`), with `extends`, `[standard]` booleans (packages or
    groups), `[settings]` and `[packages.<name>]` overrides or additions;
  - the user's toolkits go in the machine root's `toolkits/`, nearest first;
  - platform fixes in `recipes/platforms/<platform>.toml`, applied under every toolkit.

  `packages.toml`, `toolkits.toml` and `toolkits.d/` merge into this.
- `--list @<toolkit>` prints the resolved set, and where each package and flag came from.
- The registry generates the environment's package list (`env/packages.sh`), the rows of
  `hep stack status` and `stack.toml`'s library entries. `_HEP_PACKAGES` and `hep_status`'s fixed
  rows are gone.
- HDF5 is a recipe, in `@primary`, `@lab`, `@data` and `@heavy-ion` (the user's decision). YODA gets
  `.yoda.h5` when HDF5 is in the build.
- ONNX Runtime's library name comes from `{dylib}`.

| Row | Expected |
|---|---|
| `--list @primary` before and after the merge | the same packages and flags (plus HDF5) |
| a machine `toolkits/mine.toml` with `extends = "lab"`, one package off, one recipe added | built as listed; Heimdall's tree untouched |

**3.3 The shell** (U57, U58)
- `setup.sh` refuses any shell but bash, before touching anything, with the way in.
- `launch.sh` is `load_hep` on every platform.
- The loaded check tests the functions, not only the exported variable.
- `quit` undoes `machine.sh`'s additions.
- `refresh` reloads the setup that loaded the shell, the isolated stack included (with a test).
- `bin/hep` runs the machine's venv Python by path, so it works from cron, scripts and Slurm.
- Shell verbs through the `hep` function: `hep cd`, `hep quit`, `hep refresh`.

| Row | Expected |
|---|---|
| `zsh -c 'source setup.sh'` | one line naming `launch.sh`; the environment untouched |
| `env -i PATH=/usr/bin:/bin ~/Github/Heimdall/framework/bin/hep where` | works (no venv loaded) |
| `source stacks/<kit>/setup.sh`, then `hep refresh` | still the `<kit>` stack |
| a Mac shell: `load_hep`, `quit` | `DYLD_LIBRARY_PATH` and `PATH` exactly as before |

---

## Phase 4 — One tool system

**4.1 The tool search path** (U51, U27)
- `tools.folders()` and the quantity mappings search, nearest first:
  1. `<work>/tools/`;
  2. `$HEP_MACHINE/tools/`;
  3. `framework/tools/`.
- `extends = "<tool>"` merges a nearer folder over a shipped one.
- `{apps}` replaces `{hep}/framework/Apps` in the shipped folders.
- `hep tools` lists every folder with its origin.

**4.2 `custom` and `module` as folders; module settings checked** (U52, U53, U54)
- Shipped `exec` and `module` folders replace the two special kinds (`tool = "custom"` migrates to
  `tool = "exec"`).
- `hep tools new <name> --from exec|module|<tool>` writes a commented folder in `<work>/tools/`.
- **The context file** ([04 §3](04_Extending.md#3-the-tool-contract-its-own-arguments-and-one-context-file)):
  - written when a point starts and removed when it ends;
  - lists the card and config of every tool it generated cards for: the point's chain plus
    `run.generate_cards` (a configuration may override it). Tool tables that are defined but unused
    get no card;
  - reaches a tool as `HEP_CONTEXT` first, and as `{context}` in a folder's argv where wanted.
  
  It replaces the `<tool>_<export>` keys and the `[standard.<key>]` tables. The expensive products
  (Herwig's run file, MadGraph's process directory, Sherpa's integration) are asked for in the same
  list as `"<tool>:<product>"`.
- `src/Module.hh`:
  - `setting(name, default, doc)` declarations;
  - unknown keys refused before the first event;
  - `--describe` for `hep explain`.
- Adding a shipped tool: the 7 places become 3 (the folder with its docs; the vocabulary entry if
  new; a test). `test_docs` reads the folder's `doc` strings.

**4.3 Plot code, style, vocabulary** (U25, U55, U56)
- `framework/tools/{mpl,yoda,figures,merge,plotmerge}` → `framework/plot/`.
- `base.toml` → `framework/style/`, with `$HEP_MACHINE/style.toml` and `<work>/style.toml` over it.
- A folder's `quantities.toml` may declare vocabulary names. A work dir may extend `latex.toml`.

| Row (phase 4) | Expected |
|---|---|
| a work-dir `tools/fit/` from `exec` | `hep tools`: `fit (work)`; a run uses it; Heimdall's tree untouched |
| `tools/pythia/` with `extends = "pythia"` | that study uses it; `hep tools` says so |
| a module setting misspelt | refused before the first event, with the nearest name |
| an isolated stack's `hep run` | its own apps (via `{apps}`) |

---

## Phase 5 — The work dir's lifecycle

**5.1 Records apart from logs and caches; a point lock** (U21, U30, U29, U66)
- `output/` splits by lifecycle into:
  - `records/` (provenance, identity, `.complete`, `points.json`, `cluster/<time>/`);
  - `logs/` (point logs, FIFOs);
  - `.cache/`.
- Paths in records become relative to their roots.
- `hep clean` works by lifecycle: logs and cache by default; records only with `--records`, after
  confirming.
- Reserved names (`plots`, `pre`, `post`, `cluster`, `compare`) are refused as configuration and
  point names.
- **A point lock** (U66): `flock` on `<point>/.lock` (host, pid and start time inside).
  - A second session's run of a running point skips it with a message naming who holds it, or waits
    with `--wait`.
  - A stale lock (a dead pid on this host, or older than the point's timeout on another) is taken
    over.
  - `hep status` shows "running (pid N, host H)".
- `hep migrate --layout` moves an existing work dir.

**5.2 Deck sources, datasets, the template** (U22, U23, U28)
- `decks/<deck>/{deck.md,deck.toml}` (tracked) build into `reports/<deck>/` (ignored).
- `datasets/` is tracked for small files. `datasets.toml` is a manifest (URL, sha256) for large
  ones, fetched by `hep setup`.
- `hep setup --refresh` updates the framework-written files (README, CLAUDE.md, Makefile,
  `.vscode`), showing the diff, and never touches the user's files.

| Row (phase 5) | Expected |
|---|---|
| `rm -rf logs .cache` in a work dir | `hep status` still shows every point complete |
| the same configuration started in two sessions | the second skips the points the first holds, naming them; no file is written twice |
| a fresh clone of a work dir | `hep check` passes; data-backed pages draw |
| `hep clean` | never lists `records/` or `cluster/` |

---

## Phase 6 — Schema v3

**6.1 Quantities** (U35, U36, U40, U43)
- `points = [{tag, value, label, style}]` rows, `fixed`, and bindings (`to = {tool = key}`).
- Compound quantities (`fields`) for entangled sweeps.
- `vary = [...]` in a configuration.
- A list-valued `events` makes one folder per count.
- One `beams` quantity.
- **An inactive quantity is an error** (U36): "declared but neither varied nor fixed: give `fixed`,
  or vary it". This can come first, even in v2.

**6.2 Tools and the chain** (U37, U38, U39, U42, U44)
- Tools are typed by table name (`uses =` for a second instance).
- `input = "<producer>"`; FIFO or file inferred; `keep = true`.
- `[prelim]` retired (its commands become a `pre` step).
- The chain once in `[run]`; configurations replace it only when they differ.
- One seed key; `replicas`.
- Imported tool tables merge key by key.
- A native key set twice is an error naming both (`override = true` to allow).
- `--plan --card <tool>` shows each line's origin.

**6.3 Names, errors, help, migration** (U41, U45, U46, U47, U48, U49)
- The renames of [03 §6](03_Configuration.md#6-schema-v3): `[file]`, `card`, `folder`, automatic
  serials optional (automatic unless `serial` is set; a changed identity under a set serial is
  refused), one meaning of `"default"`, and `[cfgs.<name>]` at the top level.
- Errors that cross tables (a wrong-table key names its table).
- Unused tool tables and shared files checked by `hep check`.
- `hep explain` for tables, tool options, style keys, the vocabulary, `[static]`, decks and
  `machine.toml`.
- `--show-config` with origins for every value.
- `run.schema.json` regenerated correctly (no required `[run].tools`; tool keys typed).
- `hep migrate --v3`, and the manual's 02, 03 and 04 rewritten on v3.

| Row (phase 6) | Expected |
|---|---|
| every fixture and the user's study configs through `hep migrate --v3 --apply` | `hep check` passes; identities unchanged except where the record says why |
| the starter in v3 | about 35 lines (from 53); no fact written twice |
| `threads = 4` in `[tools.pythia]` | "threads belongs in [run] or a configuration" |
| a quantity declared and unused | refused, with the fix |

---

## Phase 7 — The command line and the first run

**7.1 One CLI** (U59, U60, U61, U62)
- One Python entry point (`build` and `make` included); descriptions; `hep help <command>`;
  did-you-mean for commands.
- `--dry-run` everywhere (`--plan` kept as `run`'s alias); `--set` on every command that plans;
  `--plain` global.
- `hep stack build|list|status|doctor` over the builder's engine.
- One error format, the builder's included.
- Record ids only as "(see V93)" after an explanation.

**7.2 The first run** (U63, U14)
- The README has one path per platform, ending at a drawn page, with `hep doctor` between build and
  first run.
- `hep setup --example jets` copies the demo project into the user's work dir.
- `hep setup` prints the next three commands.
- The guide runs on the example.

**7.3 Docs that match the code** (U50, U32, U65)
- The contradictions of [03 §5](03_Configuration.md#5-contradictions-in-the-docs-schema-and-fixtures--u50-30):
  - `swept` out of the schema;
  - `run.cfgs` paths in examples;
  - the import example made true;
  - eight sections;
  - `{work}/…` arguments;
  - the stale card comments;
  - the starter card's claim.
- `test_docs` loads every complete example again (it checks the old `run[configuration]` shape).
- The doc drift of [02 §5](02_Organisation.md#5-doc-drift--u32-20).
- A one-page `docs/00_Quick.md`. That needs `test_the_manual_is_the_seven_pages_and_its_index`
  updated.

| Row (phase 7) | Expected |
|---|---|
| `hep rn` | "did you mean run?" |
| `hep build -j` | an argparse error naming `-j`'s value |
| a new user on a Mac, from the README | a drawn page, with no step outside the README |
| `pytest tests/runner/test_docs.py` | every complete example in 02–04 loads |
