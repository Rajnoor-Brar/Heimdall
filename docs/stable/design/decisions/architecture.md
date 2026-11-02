---
id: decisions-architecture
summary: why Heimdall is shaped as it is: processes, one flat runner, no libraries, where things live
---

# Decisions: architecture

The full account of each is at tag `docs/pre-rebuild`, in `docs/07_Record.md`.

- **V1** The runner is Python, small, standard library only, `rich` optional for the view. Gave up: click, v1's package structure.
- **V2** No in-process event loop: every tool is a process, a module its own program. Gave up: in-process speed, sharded Rivet's 1.67× on 4 threads.
- **V3** Kept from v1: dry-run planning, identity seeds, skip-unchanged, provenance, a live watch, YODA plotting.
- **V4** Dropped from v1: fits, derived histograms, bench and most commands. A fit is a custom tool now.
- **V5** Clean slate: v1 was deleted, not ported, and is consulted through git. Gave up: a working system during the rewrite.
- **V6** Make-native build: pattern rules, `requires:` lines, a flag cache. Gave up: CMake's components, ctest.
- **V7** No C++ libraries carried: a few headers and apps. A later need is met by copying from git deliberately. Gave up: tested library code.
- **V8** Modules are plain programs with `main()`, reading HepMC through `Module.hh`; no base class, no registration macro.
- **V53** One rank table, in `runner/__init__.py`, read by the test that enforces it.
- **V60** The core names no tool: what was Rivet's is its folder's hook; custom and module differences are data in `tool.toml`.
- **V61** Tables are data, and duplicates are one: LaTeX commands, legend mappings and the like live in TOML.
- **V73** One C++ kit, `Kit.hh`: one exit-code table the apps and modules share.
- **V90** A key's long notes live in the schema beside `doc`, not in the manual's tables.
- **V91** Generated parts of the docs, held current by a test: what the code states, the docs do not restate by hand.
- **V105** Heimdall is its own repository, split from High-Energy at `split/base`. Superseded in part by V122.
- **V106** Two roots, found, never configured: where the code is, and the work dir. A `$HEIMDALL` naming another checkout is refused.
- **V108** One set of build rules, `framework/rules.mk`, used by Heimdall's Makefile and each work dir's.
- **V112** Tests run in a frozen work dir of their own, `tests/fixtures/work/`.
- **V122** The machine root: what a machine built lives outside the checkout. Heimdall holds only what is authored.
- **V127** A study's own layers: style, vocabulary and LaTeX may be a work dir's; plot code moved to `framework/plot/`.
- **V134** One command line: every command is the runner's; the shell script only finds Python.
- **V138** User pages say what they mean without record ids.
- **V52** Tests read frozen configs through a root variable, never the user's.
- **V161** High-Energy became a work dir; its VS Code tooling moved to `editor/`.
- **V213** `hep` → `heimdall` everywhere, a clean break with no alias or fallback.
- **V228** The words Assignment, Errand, Run, addressed `<A>/<E>/<R>`, everywhere.
