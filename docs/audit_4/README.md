# Audit 4 — ghosts and gaps

An audit of what Heimdall carries without using, finishing or explaining it, done on 2026-10-15 at
`d9d6374`, after tasks A–F (V140–V154). The user asked for "features and capabilities that are present but
not documented or used, abandoned halfway or not fully developed, deprecated but still lingers as a ghost,
hard to discern its purpose or usefulness".

- [01_Findings.md](01_Findings.md): the findings, G1–G23, by those four questions.
- [02_Plan.md](02_Plan.md): a remediation in four phases. **Nothing is built without the user's order.**

## How it was looked for

Each sweep is repeatable from the checkout:

| Sweep | What it compared |
|---|---|
| Unused definitions | every module-level function, class and constant in `framework/`, `recipes/`, `env/`, against every reference in code, scripts, tests and docs |
| CLI options | every `add_argument` of `cli.py`, against the code that reads `args.<dest>` (all are read) |
| Schema keys | every key of `framework/schema/run.toml` and `deck.toml`, against the runner's code (all are named) |
| Environment | every variable the code reads, against the manual |
| Markers | "retired", "for a release", "for now", "not yet", "legacy", "old name", TODO and the like, in code |
| Tool folders | each folder's documentation (05), fixture use and tests |
| Recipes and toolkits | `status = "new"`, each toolkit against the builds the record shows, the patches, `build_by_hand.txt` |
| Commands | the command list against the docs (no command or flag in the docs is missing from the CLI), overlaps between commands |
| Earlier audits | audit 2's H1–H16 re-checked against today's code; `bots/intent.md`'s rows against what exists |
| Messages | a v3 file with a wrong `vary` and `fixed`, to see what a user reads |
| CI | GitHub's run list for the workflow (none) |
| Tool-folder contract | every key `tools.FOLDER_SECTIONS` accepts, against the shipped folders (each is used); the vocabulary's words, against the folders' `quantities.toml` (each is mapped) |
| Fixture | each fixture config's configurations, against the tests (all are planned, by the tests that walk every config; some are never run) |
| C++ kits | each function of `Kit.hh`, `Module.hh`, `Status.hh`, `PythiaRun.hh`, against the apps, the fixture's modules and the C++ tests (each is called) |
| Make targets | the root `Makefile`, `rules.mk`, `work.mk`, against the docs (each is documented) |
| Paths in docs | every repository path the manual, the runbook and the READMEs name (the stale ones are G13's old layout and G11's planned lock; 07's are history) |

## The findings at a glance

| | Present, not documented or used | Half-built | Deprecated, lingering | Purpose unclear |
|---|---|---|---|---|
| Code | G1 dead definitions; G5 the project master | G6 `[cluster] image`; G8 two 1D backends | G12 v2 names in v3 errors; G13 finished migrations; G14 retired-name guards; G17 `{repo}` twice | G18 `plotmerge`; G21 `bin/run` |
| Commands and shell | G3 `heimdall_stash` and kin | — | G15 old entry points (`heimdall doctor`, `status --stack`, the shell's old names, the Mac shim) | G19 overlapping verbs |
| Stack | — | G7 25 unproven recipes, 18 unbuilt toolkits | G16 `build_by_hand.txt` | G20 five settings files |
| Docs, records, machines | G2 undocumented switches; G4 a CI workflow never run | G9 audit 2's open findings; G10 a stale intent.md; G11 never run on a real system | — | G22 `hep` beside `heimdall`; G23 the old machine's support row |

**The user's decisions (2026-10-15):** retire G13, G14, G15, G3, G5, G18 and G16; keep G4; rename the marker
(G22); fix G12's messages and keep reading v2; mark G7's unproven toolkits (02 Phase 2). Still open: G6 is a
design; G8 waits on the user's comparison of the mpl and mkhtml pages.

**What is sound:** every CLI option is read; every schema key is used and documented (a test holds it); every
tool-folder key and vocabulary word is used; every C++ kit function is called; every make target is documented;
every command and flag the docs name exists; every module has a rank and a row in 06; the apps'
command lines match 05.
