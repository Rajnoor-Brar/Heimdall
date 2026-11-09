---
id: decisions-quantities
summary: why sweeps, quantities and points work as they do
---

# Decisions: quantities and sweeps

The full account of each is at tag `docs/pre-rebuild`, in `docs/07_Record.md`.

- **V19** A tool may be chosen by a quantity: `"@generator"` in a chain.
- **V35** `combine`: points that differ only in the combined quantities merge per group, so seed replicas become one curve.
- **V38** `sweep_runs`: every configuration, one run after another.
- **V40** A Pythia `pdf` value is written as given, with no `LHAPDF6:` added. Amended by V152.
- **V42** `exclude`: values a sweep leaves out by 1-based place; the rest keep their names and identities.
- **V45** Folders are `<A>/<E>/NN_<label>/<point>`: the serial goes before the configuration's folder. A location, never an identity.
- **V46** A configuration may name its own run folder.
- **V58** A vocabulary of quantities, mapped by each tool's folder: shape and unit checked when the file is read.
- **V62** Beam order is the errand's `[A, B]`, placed by each tool.
- **V67** A quantity's value has its own curve look.
- **V75** `parallelism = "auto"`, and a pipelined sweep of runs (superseded by V236's queue). A DAG scheduler was simulated and saved under 5 %, so it was not built.
- **V76** `notify`, and a shape for a user's own quantity.
- **V151** A varied quantity no tool of a point reads would give points differing only by seeds: those are refused or collapsed.
- **V152** One `pdf` for every generator: a provider check returns the value as its tool writes it.
- **V153** A selector's value may be a piece of chain, spliced where the entry stands.
- **V154** Points that set several quantities at once: compound quantities, and listed rows.
- **V180** One switch, each generator its own field: an axis, since a point has one generator.
- **V186** A set naming a compound quantity names all its fields.
