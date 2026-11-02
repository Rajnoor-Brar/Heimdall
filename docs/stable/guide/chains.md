---
id: chains
summary: chains of tools: file chains, other generators, comparing generators and setups, stages made once
code: framework/runner/tools.py, framework/runner/config.py
---

# Generators and chains

How one tool's output reaches another follows from the chain:

| The reader of an `output` is | It is | It lives in |
|---|---|---|
| in the producer's group | a **FIFO**, fresh per attempt | the point's working folder |
| in a later group | a **file**: a product | the point's results |
| in a later group, and the producer says `keep = false` | a **scratch file** | the point's working folder |
| nobody | a product | the point's results |

A FIFO connects tools in one group only, has one reader, and never feeds a tool that is not `streamable`. Fan-out is a list-valued `output`: `output = ["to_rivet.hepmc", "to_module.hepmc"]`. `heimdall run … --show-config` lists each configuration's interfaces. `[errand] commands`, argv arrays, run in each point's folder before its first group; a nonzero exit fails the point.

## A file chain

```toml
[cfgs.delphes]
chain = ["pythia_file", "delphes", "jets_reco"]     # three groups in order: files between them

[tools.pythia_file]                                 # a second pythia table
uses   = "pythia"
card   = "ep.cmnd"
output = "showered.hepmc"
keep   = false                                      # a scratch file of the point

[tools.delphes]                                     # not streamable: in pythia's group it is refused
card   = "delphes_card_ATLAS.tcl"
input  = "pythia_file"
output = "delphes.root"

[tools.jets_reco]
uses       = "exec"
executable = "path:python3"
arguments  = ["{work}/modules/Demo/delphes_jets.py", "{input}", "{partial:output}"]
input      = "delphes"
output     = "jets_reco.json"
```

Delphes' tree is count-checked against the generator's sidecar.

## Other generators

The chain is the same; only the generator's table changes. Their slow preparation is cached per card, so a rerun, replica or other event count reuses it. Details per generator: [tools](../tools/overview.md).

```toml
[tools.sherpa]
card   = "ep.sherpa.yaml"
output = "events.hepmc"
```

A MadGraph chain is `chain = ["madgraph", ["shower", "rivet"], "yd2rt"]`: an LHE file between the first two groups, a FIFO from the shower to Rivet. Keep each generator's configurations in an errand file of their own when their quantities differ: a Pythia key would have no consumer in a Sherpa chain. Examples are in Heimdall's `tests/fixtures/work/configs/Demo/`.

## Comparing generators and setups

A quantity whose values are tool tables chooses the tool each point runs; everything else is shared.

```toml
[cfgs.compare]
vary  = ["generator"]
chain = [["@generator", "spectra"], "yd2rt"]    # "@q": what the point's value names

[quantities.generator]
points = [
  { tag = "py8", value = "pythia", label = "Pythia 8.317" },
  { tag = "hw7", value = "herwig", label = "Herwig 7.3" },
  { tag = "sh3", value = "sherpa", label = "Sherpa 3.0.5" },
]
```

- **Setups of one tool** are tables of their own: `[tools.monash]`, `[tools.a14]`, both `uses = "pythia"`, chosen by `@tune`.
- **Chains of different shapes:** a value may be a piece of chain, spliced where `@q` stands. `value = ["madgraph", "pythia"]` beside `value = "sherpa"`; `[["pythia", "rivet"]]` is a group of its own; `[]` leaves the step out.
- **One PDF for every generator:** write the set's name (`"CT14lo"`). Each generator gets its spelling. A tune was fitted with its PDF: a fair comparison matches PDFs, and changing one changes what the tune means.
- **A setting only some generators read:** a fixed one is fine. A varied one must be read by every point's tools, or some points would differ only by seeds, so the plan is refused. List the combinations instead:

  ```toml
  vary = [{ points = [
    { generator = "py8", pt0ref = "p30" },
    { generator = "py8", pt0ref = "p34" },
    { generator = "hw7" },                   # Herwig at its own card's MPI
  ] }]
  ```
- **Tools chosen together:** a quantity with fields, a field per selector, `chain = [["@gen", "@ana"]]`.
- **Results from elsewhere:** a `compare` figure, or `heimdall overlay`.

## Something every point needs, made once

```toml
[cfgs.pdf]
vary = ["pdf"]
pre  = ["fetch"]                                  # once, before every point

[tools.fetch]
uses       = "exec"
executable = "./modules/Demo/fetch_lhe.sh"
arguments  = ["{partial:output}"]
output     = "shared.lhe"                         # every point may name it: input = "shared.lhe"
```

A changed pre stage reruns the points; a failed one stops the Run.
