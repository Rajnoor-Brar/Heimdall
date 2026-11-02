---
id: tools-delphes
summary: the delphes tool: it reads a file, never a FIFO; its card and count check
code: framework/tools/delphes/tool.toml
---

# `delphes`

```toml
[tools.delphes]
card   = "delphes_card_ATLAS.tcl"
input  = "pythia_file"            # a file from an earlier group: never a FIFO
output = "delphes.root"
```

Runs `DelphesHepMC3 <combined card> <partial output> <input>`. Card: Tcl, `set {key} {value}`, seed as `set RandomSeed <seed>`. **Count check:** the `Delphes` tree's entries, read with uproot. It is not an event producer, so it never moves the generator's seeds.

- **L11** Delphes cannot read a FIFO (it skips zero-length input), and it creates its ROOT file before reading the card: write to a partial name, then rename.
