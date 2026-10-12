# Audit 3 — the user's experience

A user-experience audit of Heimdall, done on 2026-10-12 at `6767d28`, right after its first build on
a second kind of machine (an Apple M4 laptop, macOS 27). It asks four questions:

1. **Process.** Where the way to a working stack and a first plot is wrong, too thin, or fragile, and
   which errors keep coming back. ([01_Process.md](01_Process.md))
2. **Organisation.** Which files and objects exist, who owns them, how long they live, and whether
   the layout keeps those apart. ([02_Organisation.md](02_Organisation.md))
3. **Configuration.** Whether a run TOML keeps related options together, or makes the user write one
   concern under several distant headers. ([03_Configuration.md](03_Configuration.md))
4. **Extending.** How a user plugs in their own tool, or configures a standard one: "standard tools
   are just predefined user tools, and one general system accepts and coordinates all" (the user,
   2026-10-12). ([04_Extending.md](04_Extending.md))

Also covered: the everyday commands ([05_CLI.md](05_CLI.md)). The remediation, in phases, is in
[06_Plan.md](06_Plan.md).

**The user's decisions for this audit (2026-10-12):**
- **Bold:** a schema v3 is allowed, with `hep migrate` carrying configs over, as rework v2 did.
- **Machine-built trees move out of the git checkout** into a machine root of their own.
- **Downloads, sources and builds go in `forge/`;** `stack/` holds finished installs only.
- **Nothing here is built without the user's order,** phase by phase.

## Evidence

- **The Mac build.** It met 17 problems before `@primary` stood, logged one by one as they came
  (condensed in [01_Process.md](01_Process.md#appendix-the-mac-build-problem-by-problem)).
- **A stack audit on both machines.** `check_stack.sh` (kept in Heimdall's ignored `.setup/`) checks
  versions, compiled-in features, Python modules, PDF sets and unresolved libraries, and does short
  smoke runs:
  - lab PC: 101 ok, 7 FAIL;
  - Mac: 116 ok, 0 FAIL.
- **Three read-only surveys of the code.** Every claim below cites `file:line` at `6767d28`:
  - the file layout and who writes what;
  - the run-TOML surface (schema, loader, fixtures);
  - the stack build and the CLI. Some commands were run read-only (`--help`, `--list`,
    `--toolkits`, `hep explain`, `hep check`).
- **A real study's run TOMLs from the user's work** (an ep jets study and an electron–ion scan). They
  are quoted with neutral names.

## Scoring

As in audits 1 and 2: **Priority = (Impact + Risk) × (6 − Effort)**, each scored 1–5. Ids are `U<n>`.
Each finding gives:
- its evidence;
- what the user sees;
- the phase of [06_Plan.md](06_Plan.md) that fixes it.

## Findings, by priority

| # | Pri | Area | Finding | Phase |
|---|---|---|---|---|
| U2 | 45 | process | Download URLs are dead or moved: Pythia's `/download/` returns 404; Rivet and YODA moved to CEDAR. A fresh machine cannot fetch Pythia at all | 1 |
| U1 | 40 | process | Downloads are never verified: an HTML page or a truncated archive is kept and reused; `IncompleteRead` escapes as a traceback | 1 |
| U8 | 40 | process | The Mac's fixes exist only in notes (ThePEG, Herwig, Whizard, YODA, `tbb`): the next Mac repeats every one | 1 |
| U36 | 40 | config | A declared quantity that is neither swept nor static does nothing, silently | 6 |
| U57 | 40 | CLI | `hep` crashes outside the venv (`tomli_w`): scripts, cron and Slurm jobs | 3 |
| U12 | 35 | process | No ABI guard on the command line (`cxx_std=20` on the default stack); `stack/.stamps/cxx_std` is rewritten every run | 1 |
| U30 | 35 | layout | `hep clean` lists `cluster/` submission records as orphans; reserved folder names share the point/configuration namespace | 5 |
| U44 | 35 | config | Base-card lines are silently overridden by quantities and settings; the starter card claims they are refused | 6 |
| U4 | 32 | process | The user's shell leaks into the build (`ROOTSYS`, other stacks' paths): the environment is only prepended to | 1 |
| U5 | 32 | process | Optional dependencies are auto-detected: YODA's H5 depends on whether Homebrew happens to have HDF5; Homebrew HEP formulae can shadow the stack | 1 |
| U6 | 32 | process | Whizard is built without LHAPDF on both machines, with no error | 1 |
| U9 | 32 | process | Stamps know name and release only: a changed flag, `python_packages` or `pdf_sets` is never applied; there is no `--rebuild` | 1 |
| U58 | 32 | CLI | Shell environment: zsh half-loads; an exported guard makes child shells skip setup; `hep refresh` drops an isolated stack; `quit` leaves `machine.sh`'s lines | 3 |
| U50 | 30 | config | Docs contradict the loader: `swept` documented but refused; `run.default` paths; `test_docs` loads no complete example; the import example ≠ the fixture | 7 |
| U10 | 28 | process | Probes and stamps disagree: on the lab PC, `--list` would rebuild everything; ThePEG and Herwig share one folder | 1 |
| U22 | 28 | layout | Deck sources (`deck.md`, `deck.toml`) live in the ignored `reports/` beside their outputs | 5 |
| U27 | 28 | layout | Isolated stacks are half wired: tool folders hardcode `{hep}/framework/Apps`; `build/` is not per stack | 4 |
| U34 | 28 | layout | Six package lists (`packages.toml`, `stack.toml`, `_HEP_PACKAGES`, `hep_status`, two docs) drift: `xrootd` listed, the C++20 packages missing | 3 |
| U54 | 28 | extend | A module's config keys are not checked: a typo falls back to the default silently | 4 |
| U63 | 28 | CLI | The first-run path breaks or stops: the README fails on a Mac, `hep setup` prints no next step, the guide's examples live in the hidden fixture | 7 |
| U7 | 27 | process | Nothing checks what a build can do, after it or later (`hep doctor`) | 2 |
| U16 | 27 | process | An OS upgrade breaks a working stack unnoticed (lab PC: Herwig, Sherpa, ROOT MathMore) | 2 |
| U49 | 25 | config | The editor JSON schema is wrong: it requires `[run].tools`, leaves tool keys open, and has no types for `[static]` | 6 |
| U3 | 24 | process | `--dry-run` is not the build: a different downloader, and it skips stamped, installed and stashed things | 1 |
| U11 | 24 | process | The override surface is thin: `[env]` can't be set from the CLI; `pkg.env=` crashes after downloads; a list replaces the overlay's | 1 |
| U13 | 24 | process | No progress during hour-long builds; the failure tail shows warnings, not the error; a retry wipes the last log | 1 |
| U21 | 24 | layout | Run records (provenance, identity, completion markers) share `output/` with logs and caches: deleting "technical files" reruns everything | 5 |
| U23 | 24 | layout | `datasets/` is ignored: a clone of a work dir cannot run its configs | 5 |
| U24 | 24 | layout | Machine settings in tracked files (`setup_extra`, `[cluster]` in `hep.toml`) dirty Heimdall's provenance | 3 |
| U46 | 24 | config | Errors never cross tables (`threads` in `[tools.pythia]`); unused tool tables and shared files are never checked | 6 |
| U51 | 24 | extend | Tool folders load only from Heimdall: a user cannot add a tool kind without editing the framework | 4 |
| U15 | 21 | process | Docs promised platform parity; there is no support matrix and no second-platform build | 2 |
| U14 | 20 | process | `build_stack.py` run directly on a Mac says "no apt-get" instead of pointing to `build.sh` | 1 |
| U32 | 20 | layout | Doc drift: `framework/01 §2`, the `hep.toml` keys, `06 §14`, the template README's provenance | 7 |
| U41 | 20 | config | A folder's name comes from 6 keys; serial numbers are bumped by hand | 6 |
| U42 | 20 | config | Imported tool tables are replaced whole, so one tool option takes `{var:}` and 3 files | 6 |
| U43 | 20 | config | Repetition: seven copied configurations instead of a swept event count; `tools` repeated per configuration; identity data maps | 6 |
| U47 | 20 | config | `hep explain` covers only the run schema (no tables, tool options, style, vocabulary, `[static]`, decks, `hep.toml`), and `explain static` answers for the other `static` | 6 |
| U48 | 20 | config | `--show-config` prints `cluster = null` and shows no origins for tools and quantities | 6 |
| U61 | 20 | CLI | `hep build` parses its options in bash: `-j` alone fails under `set -u`; `--tests` in a work dir; `--help` prints the global usage | 7 |
| U35 | 18 | config | A quantity is written in up to five places, with values, tags, labels and styles as parallel arrays | 6 |
| U38 | 18 | config | Events and parallelism in 8 places; `threads` in every identity; `threads = 0` resolves per machine | 6 |
| U39 | 18 | config | Seeds in 5 places, and a seed quantity's meaning depends on `seed_type` set elsewhere | 6 |
| U40 | 18 | config | Beams have 4 representations; values and tags are written in opposite orders | 6 |
| U56 | 18 | extend | Quantities bind to tools implicitly by name (the vocabulary); the vocabulary and `latex.toml` have no user overlay | 4 |
| U19 | 16 | layout | Machine-built trees live in the git checkout: `git clean -x` destroys the stack; editors must be told to skip them | 3 |
| U25 | 16 | layout | The house style is a shipped file: changing it means editing Heimdall | 4 |
| U26 | 16 | layout | User toolkits and patches live in the tracked `recipes/` (untracked but not ignored) | 3 |
| U28 | 16 | layout | Work-dir copies of README, CLAUDE.md, Makefile and `expects` are never refreshed | 5 |
| U59 | 16 | CLI | Two help systems; subcommands have no description; no did-you-mean for commands; `hep_help` lists five commands | 7 |
| U60 | 16 | CLI | Seven spellings of "show, don't do"; `--set` missing from check, status and clean; `--only` and "status" mean several things | 7 |
| U62 | 16 | CLI | Four error formats; record ids (`V93`, `C7`) in user messages; a hint that contradicts its error | 7 |
| U20 | 15 | layout | `stash/` and `forge/` split one concern (the user's rule: all of it in `forge/`); `forge/` is a grab bag | 3 |
| U29 | 15 | layout | Absolute paths in records and the venv: moving Heimdall or a work dir breaks links | 5 |
| U31 | 15 | layout | Naming collisions: stack/stacks/stash, "build" ×5, output/results/reports, Apps ×3, setup ×6 | 3 |
| U52 | 15 | extend | `custom` and `module` are special kinds; a custom tool takes 3–5 places | 4 |
| U53 | 15 | extend | A new standard tool takes 7 places in Heimdall | 4 |
| U37 | 14 | config | A tool is written in three places (chain, `[tools]`, `[prelim]`): one FIFO named three times, `prelim = {}` to opt out, `shards` rewrites the chain silently | 6 |
| U45 | 12 | config | Overloaded names: "config" ×9, label, name, title, tag, nested lists, `pre`/`prelim`, `key`/`target`, `"default"` | 6 |
| U17 | 10 | process | Small Mac inconsistencies: `build.sh` picks Python 3.13, the Brewfile installs 3.12; stale comments | 1 |
| U18 | 10 | process | Internal planning words in build output ("a failure is a gate (docs/framework/02 …)") | 1 |
| U33 | 10 | layout | `bots/` (agent state) is tracked while a reusable tool (`.setup/check_stack.sh`) is ignored | 2 |
| U65 | 9 | docs | The user pages total 4,800 lines and cite record ids in prose; there is no one-page reference | 7 |
| U55 | 8 | extend | Plot backends and figure code live in `framework/tools/`, among the chain tools | 4 |

U64 was merged into U7.

**Read first:** [01_Process.md](01_Process.md) for what bit the Mac; [03_Configuration.md](03_Configuration.md)
for the schema v3 proposal; [06_Plan.md](06_Plan.md) for what to do, in order.
