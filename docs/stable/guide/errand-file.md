---
id: errand-file
summary: an errand file's anatomy, a complete example, which value wins, imports and starting a new assignment
code: framework/runner/config.py, framework/runner/v3.py, framework/schema/v3.toml
---

# The errand file

A table per concern: `[file]` (how the file is read: imports, vars), `[errand]` (the errand, and what every configuration starts from), `[cfgs.<name>]`, `[tools.<name>]`, `[quantities.<name>]`, `[plot]`, `[stats]`, `[report]`, `[cluster]`, and `[heimdall]` (the commands' own flags). Every key: [errand settings](../../reference/settings/errand.md), [tools](../../reference/settings/tools.md), [plot](../../reference/settings/plot.md).

```toml
# configs/Demo/mini.toml
[errand]
name       = "mini"
assignment = "Demo"
run        = "pdf"                 # the default configuration: what `heimdall run Demo/mini` runs
events     = 100_000
threads    = 8
chain      = [["pythia", "rivet"], "yd2rt"]   # group 1 runs together, then group 2

[cfgs.single]                      # a configuration: one recipe
description = "One point, at the fixed beams and PDF"

[cfgs.pdf]
description = "Two proton PDFs at the fixed beams"
vary        = ["pdf"]              # 2 points

[quantities.energies]              # the vocabulary knows it: Pythia's Beams:eA, Beams:eB
fixed  = "27x920"                  # the point a configuration that does not vary it takes
points = [{ tag = "27x920", value = [920, 27.5] }, { tag = "18x275", value = [275, 18] }]

[quantities.pdf]                   # PDF:pSet = <value>, as written
fixed  = "MSTW08lo"
points = [
  { tag = "MSTW08lo",  value = "LHAPDF6:MSTW2008lo68cl",         label = "MSTW 2008 LO" },
  { tag = "NNPDF23lo", value = "LHAPDF6:NNPDF23_lo_as_0130_qed", label = "NNPDF 2.3 LO" },
]                                  # or Pythia's own sets: value = 13

[tools.pythia]                     # the table's name is the tool
card   = "ep.cmnd"                 # beside this file: the physics
output = "events.hepmc"            # rivet reads it in the same group: a FIFO

[tools.rivet]
input    = "pythia"                # what pythia writes
analyses = ["photo_eic"]
output   = "jets.yoda"             # read by a later group: a product, in results/

[tools.yd2rt]
input  = "rivet"
output = "jets.root"

[plot]
formats = ["pdf", "png"]
ratio   = true
```

- **The physics is in the base card.** A quantity renders an override into the point card, read after the base, so it wins.
- **A quantity says everything about itself:** its points, its `fixed` point, and where its value goes. A quantity that reaches no tool is refused: a value that changes a directory name and nothing else is the failure this framework is built to refuse. So is one no configuration varies or fixes.
- **Connections follow from the chain:** [chains](chains.md).
- **Folders:** a configuration's results go to its Run, `results/Demo/mini/01_pdf/`. A changed configuration gets a new number rather than overwriting: [paths](paths.md).
- **Labels are LaTeX** (`$p_{T}$ > 4 GeV`), with words outside `$…$` as written. Write them in single quotes: in `"…"`, TOML reads a backslash as an escape. A label in ROOT's TLatex is refused with its LaTeX as the hint.
- **Your editor can check a file as you type:** put `#:schema <Heimdall>/framework/schema/run.v3.schema.json` on its first line (Taplo, Even Better TOML).

## Which value wins

Lowest to highest:

```
<tool>/quantities.toml (shipped < machine < work dir)  <  [file].master  <  [quantities.<q>].to  <  --set
a quantity's fixed  <  [cfgs.<name>].fixed  <  --set …fixed…  <  the value a vary gives the point
[errand]  <  extends  <  [cfgs.<name>]  <  --set
[file].import files  <  this file
[plot]  <  [plot.figures.<figure>]
```

`"default"`, on a key that accepts it, means the layer below's value, as if left out. `"native"`, on page keys that say so, means what the drawing tool does by itself. `heimdall run … --show-config` says where each value came from.

An errand file has exactly the top-level tables its reference lists; any other is an error. Everything is checked at plan time, before any process starts: [validation](validation.md).

## A study built on another

Import rather than copy, and write only what differs:

```toml
[file]
import = [{ from = "validation", only = ["tools", "quantities", "plot"] }]
drop   = ["tools.yd2rt"]            # its ROOT conversion: this study draws from the YODA

[errand]
name       = "seed_study"           # a file that imports always names its own errand
assignment = "Demo"
events     = 1_000_000
chain      = [["pythia", "rivet"]]

[tools.rivet]                       # one key over validation's rivet table: the rest stays
shards = 10
```

- **`only`** takes those tables or dotted keys and nothing else. Without it, the whole file comes.
- **`drop`** takes things back out, before this file's tables. One that names nothing an import gave is refused, so a typo never keeps what it meant to remove.
- **This file wins.** Its quantity or configuration replaces the imported one whole; its tool table's keys, `[plot]`, `[cluster]` and `[errand]`'s merge key by key.
- **Imports nest,** depth-first, and `Other/study` imports another assignment's file, whose cards stay its own. An unchanged tool's points keep their identities, so nothing reruns for being imported.

**Vars** (`[file.vars]`): `name = value`, cited in any string as `{var:name}`, replaced after imports and `--set`, so an identity sees only the result.

## A new assignment

A new study sharing nothing with the others is a new work dir: `heimdall setup <dir> --assignment <A> --git`. A new assignment in a work dir:

1. `configs/<A>/`: the native base cards, and an errand file with `[errand] assignment = "<A>"`.
2. `modules/<A>/`: Rivet plugins in `Rivet/<name>.cc` (with `.info`, `.plot`, `.yoda`), programs as `<Name>.cc` with a `// requires:` line. Headers beside them are shared by both.
3. `heimdall build`, `heimdall check <A>/<E>`, `heimdall run <A>/<E> --plan`.
