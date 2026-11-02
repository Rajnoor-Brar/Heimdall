---
id: programs
summary: your own programs in a chain: a module, an integrated program, an exec tool, a tool folder of your own
code: src/Module.hh, framework/tools/module/tool.toml, framework/tools/exec/tool.toml, framework/heimdallkit.py
---

# Your own programs

## An analysis program

When Rivet is not the right tool, write a program with the module kit ([its calls](../internals/cxx-kits.md)):

```toml
[cfgs.single]
chain = [["pythia", "decayriv", "decay"], "yd2rt"]

[tools.pythia]
card   = "decay.cmnd"
output = ["to_rivet.hepmc", "to_module.hepmc"]   # fan-out: the same events to both, a FIFO each

[tools.decay]
uses       = "module"
executable = "Decay.exe"                         # build/Decay/Decay.exe
input      = "to_module.hepmc"
output     = "decay.root"

[tools.decay.config]                             # its config: argument 1
mass_tolerance = 0.15

[quantities.masstol]                             # one quantity, two consumers
to     = { "decayriv/DecayRiv" = "MASSTOL", decay = "mass_tolerance" }
points = [{ tag = "0.05", value = 0.05 }, { tag = "0.15", value = 0.15 }]
```

Fill with raw weights and scale once after the loop; beside a Rivet histogram, scale as a density (`out.scale(σ/ΣW, "width")`). `heimdall explain Decay.exe` lists a module's settings.

## An integrated program

One process running Pythia and Rivet itself, with the runner's sweeps and seeds:

```toml
[cfgs.inproc]
chain          = ["jets", "yd2rt"]                # no FIFO: the events never leave the process
generate_cards = ["pythia", "rivet"]              # not run: their cards, in the point's context file

[tools.jets]
uses       = "module"
executable = "InprocJets.exe"
output     = "jets.yoda"

[tools.jets.config]
rivet_threads = 12
```

- **It gets** the context file (`$HEIMDALL_CONTEXT`): `job.card("pythia")` is the card, seeds included, App_Pythia would have got, so it gives the same events; `job.tool("rivet")` the analyses.
- **It owns** what the chain would do: σ over threads, the final σ to Rivet, the counting.
- **Speed:** with 12 + 12 threads, about 1.5× faster than the sharded chain. Above one Rivet it needs the SISCone patch, which the build applies.
- **A whole study in one process** imports the chain's errand file and writes only the program, the configurations that run it, and its own errand name. A point with the chain's event count and `threads` gets the chain's seeds.

## An exec tool

```toml
[tools.fit]
uses       = "exec"                               # any executable
executable = "path:python3"                       # a command on PATH
arguments  = ["{work}/modules/Decay/fit_mass.py", "{in:decay.root}", "{partial:output}"]
input      = "decay.root"
output     = "fit.json"
consumes   = ["sqrts"]                            # → [quantities] in its config

[tools.fit.config]
window = [1.09, 1.14]
```

- **Its config** is its first argument. A quantity with `to = { fit = "window" }` varies a key of it.
- **Its products:** write to `{partial:output}`; the runner renames them after the checks.
- **Other tools' cards and configs** are in `$HEIMDALL_CONTEXT`; a tool not in the chain goes in `generate_cards`.
- **Its status:** `filters = "my_rules.toml"` for a progress bar from your prints, or speak the status protocol with `framework/heimdallkit.py`: [events](../internals/events.md).

## A tool of your own

`heimdall tools new fit --from exec` makes `tools/fit/` in the work dir: a folder you can give options, a card or a status of its own, used as `[tools.fit]`. A program you installed (`bifrost <package>`) is named by `--runs <command> --package <package>`. The machine root's `tools/` holds folders every work dir sees. The contract: [tool-contract](../internals/tool-contract.md).
