---
id: principles
summary: the principles behind Heimdall's shape, each with what it buys and what it costs
---

# Principles

A principle that cannot name what it paid for is decoration.

**Every tool is a process, and the runner only decides.** No tool runs inside another, the runner links no physics library, and no tool reads the errand file. *Buys:* a tool you trust works as it does by hand, with its own log; any program in any language joins a chain by being an executable; a failure belongs to one process. *Costs:* in-process speed (0.90× v1's rate end to end, measured) and one text serialisation per hop. An in-process loop is still possible as your own program, never the framework's.

**Physics lives in the native card.** TOML carries run control, wiring and sweeps. A quantity renders an override into a point card, and each tool combines it by its own rule: Pythia's last line wins, Sherpa's cards are deep-merged, Whizard's point card goes before the base. *Buys:* no cross-generator dialect to re-verify against every release, and the card on disk is the card that ran. *Costs:* "the same study with another generator" means matching each knob by hand (L24).

**Resolved means resolved.** Every tool gets a finished card and argv: `threads = 0` becomes a number at plan time, seeds are numbers in the card, paths are absolute. *Buys:* `--plan` prints exactly what will run, and tools cannot disagree about a value.

**Say it once, where it belongs.** A kind of tool: its folder. How a quantity reaches a tool: the master TOML. Every key: the schema. The look of a page: `base.toml`. *Buys:* a new tool is a new folder, a quirk is fixed in one file. v1 decided a quantity's effect with a nine-way type dispatch in code; here it is a table.

**Require the explicit statement; refuse the convenient inference.** Connections are named, reference data are matched through a map, a quantity must be consumed, a Rivet option must be declared, a style key must exist. *Buys:* v1's silent failures cannot recur: ZEUS data drawn over another observable, options that changed nothing, a swept value that renamed a directory and nothing else. In each the system did something plausible instead of refusing. *Costs:* a few more lines, and errors to read.

**Refuse early, and say what to do.** Every check runs before any process starts, and every refusal names the file and key with a hint. *Buys:* a sixteen-point sweep never fails at point nine on a typo.

**A partial result has a different name.** Products are `*.partial.*` until their checks pass, and `.complete` is written last. A consumer's count is checked against the producer's sidecar. *Buys:* a truncated result is never mistaken for a complete one, and a rerun resumes exactly where the last stopped.

**Identity decides; location is only location.** *Buys:* a rerun of an unchanged study does nothing, a changed one reruns exactly what changed, and a chain and an integrated program with one generator set-up compare bin for bin.

**Knowledge outlives code.** What v1 learned by running things is kept as ledger notes, and the code that honours one cites it. *Buys:* the reason a line is shaped as it is survives the next rewrite.

**Measure it, and say the number when it is bad.** Gates produce numbers: σ to 1.3e-8, byte-identical YODAs, mpl's pages pixel for pixel against mkhtml's.

**Enforce the rules you can.** A rule a test enforces is a rule; a rule in a document is a hope.

**Small by surface area.** One command, one marker file, a few C++ headers, one flat package. Anything a user does not ask for is not there (v1 had 19 commands).
