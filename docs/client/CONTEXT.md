---
id: context
summary: what an AI working in a work dir needs first; heimdall context prints it
code: framework/runner/docs.py
generated: true
---

# Heimdall, for an agent in a work dir

Generated: printed by `heimdall context`, and matching the Heimdall this shell uses.

## How to work here

- `configs/` and `modules/` are the user's: change them only when asked, and show the diff.
- `results/`, `records/`, `.cache/`, `build/` and `reports/` are made by runs. Never write into them by hand.
- Before running, `heimdall check <A>/<E>`, then `heimdall run <A>/<E> [cfg] --plan`. Say what a run will cost before starting a long one.
- Look a key up rather than guessing: `heimdall explain <key>` gives its type, default, accepted values and effect, for errand keys, `plot.*`, `style.*`, `stack.*` and tool options; `heimdall explain plot` lists a table.
- A rebuilt program or changed card reruns the points that used it, by design. A plot change reruns nothing.
- Commit by path, never `git commit -a`.

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

## A complete errand file

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

A configuration with `plot_points = ["energies"]` gets a page per value of it, the other varied quantities being the curves. Left out, every point is on one page.

## What to write

| To | Write |
|---|---|
| vary two things as a grid; zip two | `vary = ["energies", "pdf"]`; `vary = [["pdf", "alphas"]]` |
| a page per value of one | `plot_points = ["energies"]` |
| a value no tool knows by name | `to = { pythia = "MultipartonInteractions:pT0Ref" }` |
| a Rivet option | `to = { "rivet/photo_eic" = "R" }` |
| seed replicas, merged into one curve | `to = { "pythia/seed" = true }`, `combine = ["replica"]` |
| several event counts | `events = [100_000, 1_000_000]` in a configuration |
| your own program | `uses = "module"` or `uses = "exec"` |
| start from another file | `[file] import = ["validation"]` |
| a fixed folder number | `serial = 3` |

Refused at plan time, each with a hint: an unknown key; a quantity no tool consumes; a FIFO across groups or into Delphes; an undeclared Rivet option; an uninstalled PDF set; a label in TLatex rather than LaTeX.

## Commands

- `heimdall run`: plan and run a configuration
- `heimdall plot`: draw a configuration's pages from its complete points
- `heimdall stats`: retired: heimdall plot RUN --stats-only measures a Run's statistics, heimdall score reads them
- `heimdall score`: a Run's standings, marginals and baseline from its statistics.csv, drawing nothing
- `heimdall overlay`: overlay any YODA/ROOT files through Paint, with no errand file
- `heimdall deck`: retired: heimdall report makes a report of Runs' pages and numbers
- `heimdall report`: a quick report of Runs' pages and numbers, built only when asked into reports/, where results/ has its sources (a folder's: its report.toml)
- `heimdall ls`: every config and its configurations
- `heimdall explain`: a key of an errand file: its type, default and meaning (the schema's)
- `heimdall context`: what an AI working in a work dir needs first: the model, a whole errand file, commands, where to read more
- `heimdall docs`: the docs as one searchable page: settings, pages by reader, their graph
- `heimdall status`: each configuration's points: complete, stale, running, failed or stopped (when, and why), incomplete or to run; its events, seeds and tools
- `heimdall records`: the record files: `records upgrade` brings them to today's format (a backup of each beside it)
- `heimdall migrate`: rewrite errand files and their cards in today's forms (a diff, or --apply)
- `heimdall reproduce`: run a finished point again, from its provenance, beside it
- `heimdall clean`: remove what the runner made and no plan uses: working folders (records/…/logs/) and .cache/ (a point's records with --records)
- `heimdall check`: check errand files: every configuration loaded, validated and planned
- `heimdall watch`: attach the live view to a running job
- `heimdall runs`: live jobs (running and paused), each with its index [N]; with --5, --10, --20 or --50 the latest jobs, with --week or --month jobs of the last 7 or 28 days
- `heimdall tag`: a Run's tag and labels: show them, set them (word, or key=value; key= removes), or --clear them
- `heimdall log`: a record's own account, a point's attempts and logs, or a tool's log
- `heimdall show`: what a Run, a point or a tool did, read from its record: identity, seed, tools, cross section, products, attempts
- `heimdall library`: the points library: list its points, verify them, prune the unlinked, adopt a Run's points
- `heimdall diff`: what two Runs of one Errand did differently: the config each ran with, and each point's identity parts, tool by tool
- `heimdall stop`: stop a running job as Ctrl-C would: its points end cleanly, a rerun resumes (a second stop kills its tools at once)
- `heimdall cluster`: run a configuration as Slurm jobs (sbatch): a pre job, a point per array task, a finish job
- `heimdall setup`: make a work dir: the key folders, heimdall.toml and the template's files (never overwrites)
- `heimdall doctor`: what this machine's stack and Heimdall can do, checked
- `heimdall tools`: every tool folder: the work dir's tools/, Himinbjorg's, Heimdall's
- `heimdall build`: compile the work dir's module programs and Rivet plugins (make all)
- `heimdall make`: make one source of the work dir (or --framework, Heimdall's): <path>/<X>.exe, <path>/<x>.so
- `heimdall stack`: this machine's stack: heimdall stack build\|list\|status\|doctor [options]
- `heimdall help`: a command's help: heimdall help <command>
- `heimdall refresh`: reload this shell's environment (gjallarhorn.sh's shell function)
- `heimdall quit`: leave this shell's environment (gjallarhorn.sh's shell function)
- `heimdall cd`: cd to a work dir's folder: heimdall cd ASSIGNMENT [configs\|modules\|results\|records\|logs] (gjallarhorn.sh's shell function)
- `heimdall recognise`: record work dirs by title, in Himinbjorg's workdirs.toml (gjallarhorn <title> goes to one)
- `heimdall bifrost`: the environment's packages (conda-forge; -python: PyPI), added, dropped or shown; --shell: gjallarhorn's block in ~/.bashrc and ~/.zshrc
- `heimdall image`: Apptainer images of Heimdall and a Himinbjorg: list them, or build one
- `heimdall where`: which Heimdall and which work dir this shell sees

## Where to read more

`heimdall where --heimdall` is Heimdall's folder. Under it, `docs/MAP.md` lists every page in a line. For a work dir:

| To | Read |
|---|---|
| vary things, target native keys | `docs/stable/guide/sweeps.md` |
| wire tools together, other generators | `docs/stable/guide/chains.md`, `docs/stable/tools/` |
| your own programs | `docs/stable/guide/programs.md` |
| pages, sets, figures, statistics | `docs/stable/guide/plots.md` and its neighbours |
| a failure | `docs/stable/guide/failures.md` |
| every key, in full | `docs/reference/settings/`, `docs/reference/keys.md` for grep |
