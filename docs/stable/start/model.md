---
id: model
summary: what Heimdall is, how a run works, the core vocabulary, and the three places files live
code: framework/runner/cli.py, framework/runner/execute.py, framework/templates/work
---

# The model

Heimdall runs Monte Carlo studies in high-energy physics: **tools are processes, chained by a TOML**. It generates events with a standard generator, analyses them with Rivet or your own program, sweeps the settings that matter, and compares the curves with each other and with data.

The runner decides and supervises; the tools do the physics. No tool runs inside another, the runner links no physics library, and no tool reads the errand file. Physics stays in each tool's native card.

## A run

```
heimdall run Demo/jets energy_pdf
  ├─ load     configs/Demo/jets.toml, in the work dir
  ├─ expand   vary = ["energies", "pdf"]  →  16 points
  ├─ plan     per point: cards, argv, connections, identity, seeds; every check. Nothing has run yet
  ├─ pre      tools run once before every point
  ├─ for each point
  │    skip?     already complete with this identity  →  next
  │    prepare   cached slow steps (Sherpa's integration), once per card
  │    group 1   App_Pythia ══FIFO══► rivet     together, supervised
  │    settle    rivet's event count == the generator's; jets.partial.yoda → jets.yoda
  │    group 2   App_yd2rt  jets.yoda → jets.root
  │    record    provenance.json, then .complete, last
  ├─ combine  replicas merged into one curve
  ├─ post     tools run once after every point
  └─ plot     pages and their numbers
```

A rerun of an unchanged study does nothing, and a changed one reruns exactly what changed. A failed point leaves its products with partial names and the run goes on, so rerunning resumes.

## Words

| Word | Means |
|---|---|
| **assignment** | a folder of `configs/`, `<A>`: errand files and cards, with its `modules/<A>/`, `results/<A>/`, `records/<A>/` |
| **errand** | one TOML under `configs/<A>/`, `<E>.toml`, with `[errand]` |
| **configuration** | a named recipe in an errand (`[cfgs.<name>]`): what it varies and fixes, its chain, events, threads |
| **Run** | what one configuration made: `results/<A>/<E>/<R>/`, where `<R>` is `NN_<label>`. `<A>/<E>/<R>` is its address |
| **job** | one `heimdall run`: it makes or resumes Runs |
| **quantity** | a named value that can be varied or fixed (`[quantities.<q>]`) |
| **point** | one combination of varied values: one chain of processes, one folder |
| **tool** | one process in the chain (`[tools.<name>]`), of a kind a tool folder describes |
| **group** | tools that run together, connected by FIFOs: an inner list in `chain` |
| **stage** | tools run once rather than per point: `pre`, `post`, a combined group |
| **object** | data: one histogram or scatter in a point's YODA (`/ZEUS_2012_I1116258/d01-x01-y01`) |
| **figure** | a recipe for pages (`[plot.figures.<f>]`) |
| **page** | output: one drawn file. A page per cell and object; the other varied quantities are its curves |

More: [glossary](../design/glossary.md).

## Three places

- **Heimdall** (`$HEIMDALL`): the framework, authored. `heimdall where` says which one this shell uses.
- **Himinbjorg** (`$HEIMDALL_MACHINE`, by default `~/Himinbjorg`): what this machine built, the stack and compiled apps.
- **A work dir:** a study, usually its own git repository. `heimdall setup <dir>` makes one; a `heimdall.toml` marks it, and the runner finds it from the working directory as git finds a repository.

| In a work dir | Holds | In git |
|---|---|---|
| `configs/<A>/` | errand files, cards, report recipes | yes |
| `modules/<A>/` | your programs (`X.cc`), Rivet analyses (`Rivet/<x>.cc`) | yes |
| `datasets/` | reference data; large files listed in `datasets.toml` | yes |
| `results/<A>/<E>/<R>/` | products, pages, their numbers | no |
| `records/<A>/<E>/<R>/` | what a job recorded; delete a point's `.complete` and it reruns | no |
| `.cache/`, `build/`, `reports/` | rebuildable caches; compiled modules; reports | no |

Details: [outputs](../guide/outputs.md).
