# 02 — User guide

How to get work done: set up, run, read what came out, and build the pipelines you need, each shown
as a recipe from a run TOML. Every key is in [04](04_Config_Reference.md), every command and tool in
[05](05_Commands_and_Tools.md), the plots and figures in [03](03_Plots.md). Why it works this way is
[01](01_Overview.md); how, [06](06_Internals.md).

---

## 1. Set up and build

There are two places ([01 §1](01_Overview.md#1-what-it-is)): **Heimdall**, the framework and its
stack, one per machine; and your **work dirs**, where studies live.

### 1.1 Heimdall

```bash
git clone <Heimdall's URL> ~/Github/Heimdall && cd ~/Github/Heimdall
python3 recipes/build_stack.py packages=@primary     # the stack, from source, into stack/ (hours)
source setup.sh                                      # the environment, in bash (any shell: ~/Github/Heimdall/launch.sh)
hep build --framework                                # Heimdall's apps, into the machine root's apps/ ($HEP_APPS)
```

The stack's recipes, its toolkits (one file each in `recipes/toolkits/`: `@primary` is the lab set plus
MadAnalysis5; `--toolkits` lists the others, and your own go in the machine root's `toolkits/`) and the
isolated stacks of another C++ standard
are [recipes/README.md](../recipes/README.md). On macOS use `recipes/platforms/mac/`; for an image,
`recipes/platforms/container/`.

`source setup.sh` sets `HEP` to Heimdall's folder, puts the stack and `hep` on `PATH`, activates the
Python environment and adds this machine's lines (the machine root's `machine.sh`). It is bash: from
zsh, or any other shell, `launch.sh` (in Heimdall's folder) opens a bash with it loaded, or runs one
command in it (`launch.sh hep run …`); make that your `load_hep` alias. Another shell sourcing
`setup.sh` is turned away before anything changes. An isolated toolkit's stack is loaded by its own
`stacks/<toolkit>/setup.sh` instead, in a shell of its own. `hep where` says which Heimdall (and which
stack) a shell sees, and which work dir.

Three verbs change the shell itself, so they are the shell function `hep` that `setup.sh` defines:
`hep cd PROJECT [configs|modules|results|output]` (in the current work dir), `hep quit` (leave the
environment: `PATH`, the venv and `machine.sh`'s lines as they were) and **`hep refresh`**, which
reloads the environment in the same shell, from scratch: `quit`, then the same stack again (an
isolated toolkit's included). `hep_status` lists the stack's packages (`hep status --stack`) and
`hep_help` the rest; `quit`, `hep_cd` and `hep_refresh` are the old names. Sourcing another stack's
`setup.sh` takes the loaded one out first. Use it after a stack's rebuild, an edit of `env/hep_env.sh` or of the machine
root's `machine.sh`, or a `git pull` of Heimdall. It is the shell function `hep` that `setup.sh` defines
(also `hep_refresh`), since a program cannot change its shell's variables.

### 1.2 A work dir

```bash
hep setup ~/Github/My-Study --project Jets --git     # the folders, hep.toml, a starter, one commit
cd ~/Github/My-Study
hep build                                            # its module programs and Rivet plugins
hep run Jets/jets                                    # the starter: Pythia → MC_JETS, two PDFs
```

`hep setup <dir>` makes the folders every work dir has (`configs/ modules/ datasets/ results/
records/ reports/ build/`), its `hep.toml` (the marker: `[work] name`, and `[framework] expects`, the
Heimdall revision it was made by), a `Makefile`, `.gitignore`, `README.md`, `CLAUDE.md` and editor
settings. It never overwrites: run it again in a work dir (after a fresh clone, say) and it adds only
what is missing. `--project P` adds `configs/P/p.toml` and `p.cmnd`, a starter that `hep check`
accepts, and `modules/P/`; `--git` commits what it added; `--adopt` makes a work dir of a folder that
already has files.

Every `hep` command finds its work dir by walking up from the working directory to a `hep.toml`
with a `[work]` table; `$HEP_WORK` names one instead. Outside a work dir, `hep run` says so. A work
dir made by a newer Heimdall than the one running (its `expects` is not in Heimdall's history) is
warned about, once per command.

### 1.3 Building

**First, is the machine ready?** `hep doctor` checks what every installed package of the stack can
do (its recipe's checks: versions, compiled-in features, Python modules, short runs), scans every
program and library for libraries that no longer resolve (after an OS upgrade, say), and checks
Heimdall's own: one row each, ok / MISSING / FAIL / n/a, exit 1 on a FAIL. `--quick` skips the
slow runs; `--record` adds this machine to the support matrix (`hep doctor --matrix`).

`hep build` compiles the work dir's sources (`make all`, by `$HEP/framework/work.mk`); `hep build
--framework` compiles Heimdall's own (its `Makefile`). Both take:
- `--tests` (with `--framework`) also builds the C++ tests;
- `--configure` probes the toolchain again (after installing a library);
- `--clean` empties the build first;
- `-j N` limits the jobs.

To build one source, `make` it by its path (`hep make …` works from anywhere in the work dir, `hep
make --framework …` in Heimdall); the output lands where the convention says:

| Source | `make` | Output |
|---|---|---|
| `modules/<P>/<X>.cc` | `make modules/<P>/<X>.exe` | `build/<P>/<X>.exe` |
| `modules/<P>/Rivet/<x>.cc`, `modules/<P>/Rivet_<x>.cc` | `make modules/<P>/Rivet/<x>.so` | `build/Rivet/Rivet_<x>.so` + its `.info`, `.plot`, `.yoda` |
| Heimdall's `src/App_<X>.cc` | `hep make --framework src/App_<X>.exe` | `$HEP_APPS/App_<X>.exe` |
| Heimdall's `src/Apps/<X>/main.cc` | `hep make --framework src/Apps/<X>.exe` | `$HEP_APPS/<X>.exe` |

A source says what it links in one line near the top: `// requires: pythia8 hepmc3 fastjet`. The
names it may use are those of `env/stack.toml` (`pythia8 hepmc3 yoda root fastjet lhapdf rivet
geant4 toml zstd zlib onnx delphes`), or `none`. Without the line it links everything that was found.
Heimdall's headers (`Module.hh`, `Kit.hh`, `Status.hh`, `PythiaRun.hh`) are on the include path. A
folder or file whose name starts with `_` is parked: `hep build` skips it.

---

## 2. A first run

```bash
hep run Demo/jets single --plan    # what would run: cards, argv, connections; runs nothing
hep run Demo/jets single --set run.events=50000
```

`single` is one point:
- App_Pythia generates 27.5 × 920 GeV e⁺p photoproduction into a FIFO;
- Rivet's `photo_eic` reads it;
- the YODA is converted to ROOT;
- 17 pages are drawn against ZEUS data.

The terminal shows the running tools, then one block:

```
── point 1/1: point ── ok after 42.3 s
   done → results/Demo/jets/03_single/point
```

| Look in | For |
|---|---|
| `results/Demo/jets/03_single/point/` | `jets.yoda`, `jets.root`: the products |
| `results/Demo/jets/03_single/plots/root/` | the pages (`d01-x01-y01.pdf`, …), `index.html`, and `single.root`, the sweep in one file |
| `records/Demo/jets/03_single/point/` | `provenance.json`, `identity.json`, `.complete`: what the run recorded |
| `logs/Demo/jets/03_single/point/` | `cards/`, `logs/`: safe to delete (`hep clean`) |

Run the same command again and nothing happens: the point is complete with the same identity. Change
anything that decides the result (a card, an event count, a binary) and it runs again.

```bash
hep run Demo/jets energy_pdf       # 16 points: 4 beam energies × 4 PDFs
hep watch                                    # from another terminal: follow the latest job
hep plot Demo/jets energy_pdf      # redraw its pages from what is on disk
```

---

## 3. Anatomy of a run TOML

A run TOML has a table per concern: `[run]` (the run, and what every configuration starts from),
`[cfgs.<name>]` (each configuration), `[tools.<name>]`, `[quantities.<name>]` and `[plot]`. Here is a
small, complete one:

```toml
# configs/Demo/mini.toml
[run]
name    = "mini"
project = "Demo"
run     = "pdf"                   # what `hep run Demo/mini` runs
events  = 100_000
threads = 8
chain   = [["pythia", "rivet"], "yd2rt"]   # group 1 runs together, then group 2

[cfgs.single]                     # a configuration: one recipe
description = "One point, at the fixed beams and PDF"

[cfgs.pdf]
description = "Two proton PDFs at the fixed beams"
vary        = ["pdf"]             # 2 points

[quantities.energies]             # the vocabulary knows it: Pythia's Beams:eA, Beams:eB
fixed  = "27x920"                 # the point a configuration that does not vary it takes
points = [{ tag = "27x920", value = [920, 27.5] }, { tag = "18x275", value = [275, 18] }]

[quantities.pdf]                  # PDF:pSet = <value>, as written
fixed  = "MSTW08lo"
points = [
  { tag = "MSTW08lo",  value = "LHAPDF6:MSTW2008lo68cl",         label = "MSTW 2008 LO" },
  { tag = "NNPDF23lo", value = "LHAPDF6:NNPDF23_lo_as_0130_qed", label = "NNPDF 2.3 LO" },
]                                 # or Pythia's own sets: value = 13

[tools.pythia]                    # the table's name is the tool
card   = "ep.cmnd"                # configs/Demo/ep.cmnd: the physics
output = "events.hepmc"           # rivet reads it in the same group: a FIFO

[tools.rivet]
input    = "pythia"               # what pythia writes
analyses = ["photo_eic"]
output   = "jets.yoda"            # read by a later group: a product, in results/

[tools.yd2rt]
input  = "rivet"
output = "jets.root"

[plot]
formats = ["pdf", "png"]
ratio   = true
```

- **The physics is in the base card.** A quantity renders an override into the point card
  (`cards/pythia.point.cmnd`). It is read after the base, so it wins.
- **A quantity says everything about itself:** its points as rows (`tag`, `value`, `label`,
  `style`), its `fixed` point, and where its value goes. It reaches tools in one of two ways
  (04 §8.1):
  - through the tool folders' `quantities.toml` (`energies`, `pdf`, `sqrts`, `beams`, `beam_a`,
    `beam_b` for Pythia);
  - through `to = { pythia = "…" }` (a native key), `{ "rivet/photo_eic" = "R" }` (an analysis
    option) or `{ "pythia/seed" = true }` (a replica).

  A quantity that is set but reaches no tool is refused (C7): a value that changes a directory name
  and nothing else is the failure this framework is built to refuse. So is one no configuration
  varies or fixes.
- **Connections follow from the chain**: `input` names what a tool reads, by its producer. A reader
  in the producer's group reads a FIFO; a later group reads a file, a product in `results/` (04 §6).
- **Paths**: a bare name goes under its key's convention root (`card` under `configs/<P>/`), `./x`
  is from the work dir, and `/x` is absolute (04 §2).
- **Folders**: a configuration's results go to `results/Demo/mini/01_pdf/`. The runner numbers the
  folder, and a changed configuration gets a new number rather than overwriting; `serial = 3` makes
  it yours (04 §2).
- **Labels are LaTeX**, as a physicist writes them (`$p_{T}$ > 4 GeV`, `$\sqrt{s}$`). Words outside
  `$…$` are text, as written. A label in ROOT's TLatex (`#sqrt{s}`, `p_{T}` with no `$`) is refused
  with its LaTeX as the hint, and `hep migrate` rewrites old files (§10).

---

## 4. Sweeps and points

Each recipe below is a pattern you can copy. The shipped configurations that use it are named, so
you can run them.

### 4.1 One point

No `vary`: one point. Every active quantity takes its `fixed` point. → `jets single`.

### 4.2 A sweep: one quantity, one page

```toml
[cfgs.pdf]
vary = ["pdf"]                    # the chain is [run]'s
```

One page per histogram, with a curve per PDF. → `jets pdf`, `validation default`.

### 4.3 A grid, split into pages

```toml
[cfgs.energy_pdf]
vary        = ["energies", "pdf"]     # 4 × 4 = 16 points
plot_points = ["energies"]            # a page folder per energy; the PDFs are the curves
```

`plot_points` names the quantities that make **pages**; every other varied quantity makes
**curves**. → `jets energy_pdf`, `jets mpi_grid`, `lambda cuts_grid`.

### 4.4 Quantities that move together

```toml
vary = ["energies", ["pdf", "alphas"]]    # pdf and alphas zipped: point i with point i
```

An inner list is one axis whose quantities have equal point counts (a PDF with its matching αs).
Quantities that only ever move together are better written as one, with fields: a row per point and
a value per field (04 §8.4). A quantity's `exclude = [N, …]` leaves points out of a vary (1-based).

```toml
[quantities.collision]               # vary = ["collision"]: beams and nucleus together
fields = { energies = "energies", nucleus = { pythia = "PDF:nPDFBeamA" } }
fixed  = "p"
points = [
  { tag = "p",  energies = [130, 9], nucleus = 2212,       label = "$e$p" },
  { tag = "Au", energies = [100, 9], nucleus = 1000791970, label = "$e$Au" },
]
```

### 4.5 A configuration's own fixed values

```toml
[cfgs.mpi]
vary  = ["pt0ref"]
fixed = { energies = "18x275" }       # over the quantity's own fixed, for this configuration only
```

→ `jets mpi`, `jets radius`. A fixed point is a tag, an exact value, or `"#N"`. `--set
cfgs.mpi.fixed.energies=10x100` changes it for one invocation.

### 4.6 A quantity Pythia does not know by name

```toml
[quantities.pt0ref]
to     = { pythia = "MultipartonInteractions:pT0Ref" }
points = [
  { tag = "pt30", value = 3.0, label = '$p_{T0}^{\mathrm{ref}}$ = 3.0 GeV' },
  { tag = "pt32", value = 3.2, label = '$p_{T0}^{\mathrm{ref}}$ = 3.2 GeV' },
  { tag = "pt34", value = 3.4, label = '$p_{T0}^{\mathrm{ref}}$ = 3.4 GeV' },
]
```

- **Quoting:** write LaTeX labels in **single** quotes. In `"…"`, TOML reads a backslash as an
  escape and refuses the file.
- **Underscores:** only a brace makes a sub- or superscript, so `"PDF4LHC21_40"` shows its
  underscores as they are.
- **No-op overrides:** an override equal to the base card's own value is written, but does not change
  the identity.

### 4.7 Analysis options

```toml
[quantities.radius]
to     = { "rivet/photo_eic" = "R" }    # tool table / analysis = the option, as the .info declares it
points = [{ tag = "r04", value = 0.4 }, { tag = "r07", value = 0.7 }, { tag = "r10", value = 1.0 }]
```

Rivet runs `photo_eic:R=0.4`, and so on. An option the `.info` does not declare is refused (C9):
Rivet would ignore it silently and give identical curves. Each variant is a curve on the object's
page, labelled `… [R=0.4]`.

**Each value is its own generation** (V9): a three-point option vary runs Pythia three times. To
avoid that, keep the events once as a file (the generator in a group of its own) and analyse them
in another configuration (§5.1 shows the file interface). → `jets radius`, `lambda sets`.

### 4.8 Every configuration, one run after another

To run several of a TOML's configurations in one go, list them, or say `true` for all:

```toml
[run]
sweep_runs = ["pdf", "energies"]   # hep run jets: these, in this order (true: every one, in file order)

[cfgs.pdf]
title = "Proton PDFs"              # the header line: run 01 - Proton PDFs -

[cfgs.delphes]                     # not listed: hep run jets delphes still runs it
```

- **Each configuration is an ordinary run**, with its own title, blocks, verdict and folder, exactly
  as `hep run jets <cfg>` would make it.
- **They are all checked before the first starts**, so a typo in the last one costs nothing.
- **They are pipelined**: a run starts once the run before has started all its points, and they
  share the machine's cores.
- **A failed run lets the next one start**; Ctrl-C stops everything.
- **`hep watch` follows the whole sweep**, from one run to the next.

That is what a shell loop can't do. In `for c in …; do hep run jets $c; done`, a Ctrl-C only ends the
current run (hep exits 6 and bash carries on), and a typo in a later configuration shows up hours in.
`hep run jets pdf` still runs only `pdf`, and `--set run.sweep_runs=false` turns the sweep off for one
call.

### 4.9 A study built on another

When a run shares most of another's set-up (its beams, tools, quantities, data and plots), import it
instead of copying it, and write only what differs:

```toml
[file]
import = [{ from = "validation", only = ["tools", "quantities", "plot"] }]
drop   = ["quantities.mpi", "plot.backend"]     # its MPI scan, and its mpl+yoda pages: Paint's here

[run]
name       = "seed_study"                     # a file that imports always names its own run
project    = "Demo"
sweep_runs = ["default", "spread"]
chain      = [["pythia", "rivet"]]

[cfgs.default]
vary    = ["pdf", "replica"]
combine = ["replica"]

[cfgs.spread]
vary        = ["pdf", "replica"]
plot_points = ["pdf"]

[tools.rivet]                                 # one key over validation's rivet table: the rest stays
shards = 10

[quantities.replica]                          # its own quantity, beside the imported ones
to     = { "pythia/seed" = true }
points = [{ tag = "s1", value = 1 }, { tag = "s2", value = 2 }, { tag = "s3", value = 3 },
          { tag = "s4", value = 4 }, { tag = "s5", value = 5 }]
```

- **Taking a part:** `only` takes those tables or dotted keys (`cfgs.default`, `plot.figures.eta`)
  and nothing else; without it, the whole file comes, its configurations too.
- **Removing:** `drop` takes things back out, before this file's tables. A drop that names nothing
  an import gave is refused, so a typo never keeps what it meant to remove.
- **Overriding:** this file's tables then win. Its own quantity or configuration replaces the
  imported one whole; its tool table's keys go over the imported table's one by one (`shards`
  above), as its `[plot]` keys go over the imported `[plot]`.
- **Nesting:** imports nest, and `Other/run` imports another project's file, whose cards stay its
  own. The points of an unchanged tool keep their identities, so nothing reruns for being imported.
- **Checking:** `hep run … --show-config` says where every value and table came from.

---

## 5. Generators and chains

### 5.1 A file chain: generator → Delphes → your analysis

```toml
[cfgs.delphes]
chain = ["pythia_file", "delphes", "jets_reco"]     # three groups, strictly in order: files between them

[tools.pythia_file]                                 # a second pythia table
uses   = "pythia"
card   = "ep.cmnd"
output = "showered.hepmc"
keep   = false                                      # a scratch file of the point, in logs/

[tools.delphes]                                     # not streamable: in pythia's group it is refused (L11)
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

Delphes' tree is count-checked against the generator's sidecar. The scratch file stays in
`logs/`, so another configuration can read it with `input = "./logs/…/showered.hepmc"`; without
`keep = false` it would be a product in `results/`.
→ `jets delphes`.

### 5.2 Other generators

The chain is the same; only the generator's table changes. Their slow preparation (Sherpa's and
Whizard's integration, `Herwig read`, MadGraph's process directory) is cached per card under
`.cache/<P>/`, so a rerun, a replica or another event count reuses it.

```toml
[tools.sherpa]
card   = "ep.sherpa.yaml"         # the plan owns BEAMS, EVENTS, RANDOM_SEED, EVENT_OUTPUT
output = "events.hepmc"
```

| Generator | Base card | Notes |
|---|---|---|
| `herwig` | `.in` | `hep build --framework` makes its repository; seed and events are flags |
| `sherpa` | `.yaml` | keys are paths into the YAML (`PDF_SET[0]`, `EPA:Q2Max`); `MPI_PDF_SET` follows `PDF_SET` |
| `whizard` | `.sin` | one base card, included after the plan's settings; beams by the model's names; direct photoproduction only |
| `madgraph` | proc card | writes an LHE **file**; shower it with a `pythia` table in a later group (its base card sets `Beams:frameType = 4`) |

A MadGraph chain is `chain = ["madgraph", ["shower", "rivet"], "yd2rt"]`: the LHE file between
the first two groups, a FIFO from the shower to Rivet (05 §15).

Keep each generator's configurations in a run TOML of their own when their quantities differ:
jets's `pt0ref` is a Pythia key, and in a Sherpa chain nothing would consume it (C7). The shipped
examples are in Heimdall's fixture work dir, `tests/fixtures/work/configs/Demo/` (`herwig.toml`, `sherpa.toml`,
`whizard.toml`, `madgraph.toml`).

### 5.3 The same study with several generators

```toml
[cfgs.compare]
vary  = ["generator"]
chain = [["@generator", "spectra"], "yd2rt"]    # "@q": the tool table the point's value names

[quantities.generator]
points = [
  { tag = "py8", value = "pythia", label = "Pythia 8.317" },     # values: tool tables
  { tag = "hw7", value = "herwig", label = "Herwig 7.3" },
  { tag = "sh3", value = "sherpa", label = "Sherpa 3.0.5" },
]
```

This needs a `[tools.pythia]`, a `[tools.herwig]` and a `[tools.sherpa]`, each writing
`events.hepmc`. A value that only one of them consumes (Sherpa's `BEAMS`) is accepted, since it
reaches a tool of the configuration. → `Generators/generators`.

### 5.4 Something every point needs, made once

```toml
[cfgs.pdf]
vary = ["pdf"]
pre  = ["fetch"]                                  # once, before every point

[tools.fetch]
uses       = "exec"
executable = "./modules/Demo/fetch_lhe.sh"        # your script
arguments  = ["{partial:output}"]
output     = "shared.lhe"                         # every point may name it: input = "shared.lhe"
```

A changed pre stage reruns the points; a failed one stops the run.

---

## 6. Your own programs

### 6.1 An analysis program

When Rivet is not the right tool (candidate reconstruction, ML features, detector level), write a
program with the module kit ([06 §21](06_Internals.md#21-modulehh)):

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

[tools.decay.config]                              # its config: argument 1
mass_tolerance = 0.15

[quantities.masstol]                              # one quantity, two consumers
to     = { "decayriv/DecayRiv" = "MASSTOL", decay = "mass_tolerance" }
points = [{ tag = "0.05", value = 0.05 }, { tag = "0.10", value = 0.10 },
          { tag = "0.15", value = 0.15 }, { tag = "0.25", value = 0.25 }]
```

- **Varying its options:** a module's options can be varied; the value lands in its config
  (`mass_tolerance`).
- **Scaling:** fill with raw weights and scale **once** after the loop. Beside a Rivet histogram,
  scale as a density (`out.scale(σ/ΣW, "width")`, L21).

→ `Decay/decay`: the Rivet analysis and the module on the same events, agreeing to YODA's
precision.

### 6.2 An integrated program

One process that runs Pythia (and Rivet) itself, with the runner's sweeps and seeds:

```toml
[cfgs.inproc]
chain          = ["jets", "yd2rt"]                # no FIFO: the events never leave the process
generate_cards = ["pythia", "rivet"]              # not run: their cards, in the point's context file

[tools.jets]
uses       = "module"
executable = "InprocJets.exe"
output     = "jets.yoda"
```

**What it gets:** the point's context file (`$HEP_CONTEXT`, 04 §9.4) lists every tool's card and
config; the program reads `job.card("pythia")`, the same card, seeds included, that App_Pythia would
have got, so `inproc` and `single` give the same events, and `job.tool("rivet")` for the analyses.

**What it owns:** what the chain would do (04 §9.4): σ over threads, the final σ to Rivet, the
counting.

**Speed:** Pythia runs on the configuration's `threads`, and `rivet_threads = K` in
`[tools.jets.config]` runs K Rivets on threads of their own, merged at the end. With 12 + 12 it is
about 1.5× faster than the sharded chain (§7.1). K above 1 needs the SISCone patch in the stack's FastJet (L29; `recipes/patches/`, applied by the build).

**A whole study in one process** imports the chain's run TOML (§4.9) and writes only what differs: the
program, the configurations that run it, and a run name of its own. The physics (quantities, the
pythia and rivet tables, plots) is the chain's, so an edit there is an edit here, and a point with
the chain's event count and `threads` gets the chain's seeds, so the same events:

```toml
[file]
import = [{ from = "validation", only = ["quantities", "tools", "plot"] }]

[run]
name           = "inproc_study"
project        = "Demo"
run            = "default"
events         = 1_000_000
threads        = 12
chain          = ["inproc", "yd2rt"]
generate_cards = ["pythia", "rivet"]   # validation's tables: configured, not run; their cards for inproc

[cfgs.default]
vary = ["pdf"]

[tools.inproc]
uses       = "module"
executable = "InprocJets.exe"
output     = "validation.yoda"

[tools.inproc.config]
rivet_threads = 12
```

→ `inproc_validation` and `inproc_jets` are the shipped ones, written out whole.
How the program is built: [06 §21](06_Internals.md#21-modulehh).

### 6.3 An exec tool, and a Python one

```toml
[tools.fit]
uses       = "exec"                               # any executable
executable = "path:python3"                       # a command on PATH, asked for by name (V54)
arguments  = ["./modules/Decay/fit_mass.py", "{in:decay.root}", "{partial:output}"]   # your script
input      = "decay.root"
output     = "fit.json"
consumes   = ["sqrts"]                            # → [quantities] in its config

[tools.fit.config]
window = [1.09, 1.14]
```

- **Its config:** the file `logs/…/<point>/config/fit.toml` is the first argument. A quantity
  with `to = { fit = "window" }` varies a key of it.
- **Its products:** write them to `{partial:output}`; the runner renames them after the checks.
- **The other tools:** their cards and configs are in the point's context file, `$HEP_CONTEXT`
  (04 §9.4); a tool that is not in the chain goes in `generate_cards`.
- **A tool of your own:** `hep tools new fit --from exec` makes `tools/fit/` in the work dir, a folder
  you can give options, a card or a status of its own, used as `[tools.fit]` (06 §16).
- **Its status:** set `filters = "my_rules.toml"` for a progress bar from your prints
  ([06 §23](06_Internals.md#23-filterstoml)), or speak the status protocol with `framework/hepkit.py`
  ([06 §22](06_Internals.md#22-statushh-and-the-status-protocol)). `hepkit` also gives the exit
  codes and the report a module writes.

---

## 7. Scale and statistics

### 7.1 More Rivets

A Rivet process uses one core, so in a Pythia → Rivet chain it is the limit (about 1,500 events/s
with ZEUS_2012), and more Pythia threads only wait for it. Split its events among several:

```toml
[cfgs.default]
threads = 12                     # Pythia's threads

[tools.rivet]
input    = "pythia"
analyses = ["ZEUS_2012_I1116258"]
output   = "validation.yoda"
shards   = 10                    # 10 Rivet processes, each on a share, merged into validation.yoda
```

Nothing else changes: not the chain, not the file names, not what the later tools and the pages
read. The runner deals the events among ten FIFOs, runs ten Rivets, checks each one's count, and
merges them with `rivet-merge -e` ([05 §5.1](05_Commands_and_Tools.md#51-sharded-rivet-shards--k)).

- **The result:** the events are the same as unsharded, so the result is the same. The point
  reruns, since its commands changed.
- **Cores:** keep `threads + shards` within the machine's cores.
- **For one run only:** `--set tools.rivet.shards=10 --set cfgs.default.threads=12`.
- **Analyses:** every analysis must be re-entrant (`Reentrant: true` in its `.info`).

### 7.2 Several points at once

When one point cannot fill the machine (a Rivet that stops scaling, or many short points each
spending ~5 s in Pythia's init), run several points at once:

```toml
[run]
threads     = 5                  # each point's Pythia threads, as before
parallelism = 4                  # 4 points at a time: ~4 × (5 + its Rivets) cores; "auto": as many as fit
```

- **The results don't change:** every point gets exactly the result it gets one at a time.
  `parallelism` is not in any identity or seed, so it reruns nothing either.
- **The output stays apart:** each point keeps its own folder, and the view prints each point's
  block whole when it ends (in the order they finish).
- **Planning:** `--plan` prints the estimate ("4 at once (~24 of 24 cores)") and warns past the
  machine. For one run: `--set run.parallelism=4`.

### 7.3 Replicas, merged

```toml
[cfgs.replicas]
vary  = ["replica"]
chain = [["pythia", "rivet"]]
post  = ["merge"]                    # once, after every point is complete

[quantities.replica]
to     = { "pythia/seed" = true }    # only changes the seed
points = [{ tag = "s1", value = 1 }, { tag = "s2", value = 2 }, { tag = "s3", value = 3 }]

[tools.merge]                        # rivet-merge -e
input  = "jets.yoda"                 # that product of every point
output = "merged.yoda"               # → results/…/replicas/post/merged.yoda
```

→ `jets replicas`, `lambda replicas`. The post stage runs only when every point is complete, and
reruns when any point changes.

**Seeds per curve, merged** (`combine`, [04 §5.5](04_Config_Reference.md#55-combine)): vary the
replica beside the quantity you compare, and merge each value's seeds into one curve.

```toml
[cfgs.default]
vary    = ["pdf", "replica"]         # 4 PDFs × 5 seeds
combine = ["replica"]                # one curve per PDF: its 5 seeds merged, 5× the statistics
```

- **Where they go:** the merged YODAs are `results/…/default/<pdf>/validation.yoda`, beside the seeds'
  own folders, and the pages are drawn from them.
- **The spread:** a second configuration with the same vary and no `combine` gets the same seeds,
  and draws each as its own curve: how far one seed's result wanders. → `seed_sweep` (and its
  `spread`).
- **For one figure only:** to merge for one figure while the run keeps the seeds apart, use a
  `merged` figure ([03 §7.4](03_Plots.md#74-merged-points-merged-for-this-figure)).

### 7.4 Seeds, and repeating a run

By default a point's seeds follow its generator's identity, so the same setup always gives the same
events. A `Random:seed` in your card is ignored, because the runner writes its own after it. To
choose the seeds yourself:

```toml
[run]
seed = 3245364                   # every point's seed: "identity" (the default), "random" or an integer;
                                 # a configuration can say its own

[quantities.seed]                # or one exact seed per point, varied like anything else
to     = { "pythia/seed" = true }
points = [{ tag = "1001", value = 1001 }, { tag = "2001", value = 2001 }, { tag = "3001", value = 3001 }]
```

- **An integer:** a point gets exactly its seed; at `threads = 12` its threads get seed … seed + 11.
  Space varied seeds by at least `threads`: two points with the same setup whose blocks overlap would
  repeat events, so the plan refuses them. Points with different physics may share one seed.
- **`"random"`:** a new seed is drawn each time a point runs. A complete point keeps its sample (it
  is skipped as usual), and `--rerun` draws again.
- **Repeating a run:** every point's `provenance.json` records the seed it used, and `--plan` shows
  each point's seed.
  - `hep reproduce records/…/<point>/provenance.json` runs the point again exactly as it ran, beside
    the original, and compares the products (§10).
  - Or set `seed` to that seed.

### 7.5 On a Slurm cluster

`hep cluster` runs a configuration as Slurm jobs (V114):
- a **pre job** first, when there are pre tools to run;
- a **points array**, a task per point to run;
- a **finish job** after every point has ended: the combined groups, the post tools and the plots.

Each job is an ordinary `hep run`, so it skips a complete point, writes where a run writes, and gives
the same events as the same point run here. Run it on the cluster's login node, with Heimdall and
the work dir on a filesystem the nodes see. The machine's settings go in the machine root's
`machine.toml` (every work dir there) or the work dir's `hep.toml` (this one, which wins), the
study's in the run TOML:

```toml
[cluster]                     # machine.toml (or hep.toml): this machine's defaults
account   = "my-group"
partition = "standard"
setup     = ["module load gcc/13"]
```

```toml
[cluster]                     # the run TOML: the study's
time        = "04:00:00"      # each point's limit: required in one of the two
memory      = "8G"
max_running = 20              # at most 20 points at once

[cluster.finish]
time = "00:30:00"
```

```bash
hep cluster Demo/jets energy_pdf --dry-run   # write the job scripts, print the sbatch lines
hep cluster Demo/jets energy_pdf             # submit: pre → points (an array) → finish
hep cluster Demo/jets energy_pdf --status    # each point: complete, running, pending, failed (its log)
hep cluster Demo/jets energy_pdf --cancel    # scancel the latest submission
```

- A configuration's own `cluster = { time = "08:00:00" }` is over the run's, and `--set
  cluster.time=…` is over everything, for one submission. Every key is in
  [04 §16](04_Config_Reference.md#16-cluster-running-on-slurm).
- `cpus` defaults to what a point keeps busy (its generator's `threads`, its shards, …), as `--plan`
  counts it. `parallelism` is not used: `max_running` is how many points run at once.
- A second submission of a configuration waits until the first's jobs have ended (`--status`,
  `--cancel`).
- The scripts, the job ids and the jobs' logs are in `records/<P>/<run>/<cfg>/cluster/<stamp>/`.
  `hep watch` cannot reach a node: the logs and `--status` stand in.
- Each script's last line is the `hep run` it makes, which can be typed by hand: `hep run C cfg
  --points <name> --stages points`, then `hep run C cfg --stages combine,post,plot`.
- The points' FIFOs and the prepare caches' locks are on the shared filesystem: NFSv4 and Lustre
  take both (a FIFO's two ends are on one node).

---

## 8. Watching, subsets and reruns

| You want | Type |
|---|---|
| to look before running | `hep run CONFIG CFG --plan` |
| what would rerun, and why | `--why` (what changed since each point last completed) |
| each value and where it came from | `--show-config` |
| a subset | `--points 27x920_MSTW08lo,pdf=NNPDF23lo,3` (names, tags, `q=tag`, indices) |
| fewer events, once | `--set run.events=50000` (dotted keys into the TOML, in its own names; repeatable) |
| a finished point again | `--rerun` (with `--points` for one) |
| only the pages | `--only plot`, or `hep plot CONFIG CFG` |
| only the post (or pre) tools | `--only post` / `--only pre` |
| plain lines (logs, CI) | `--plain` (automatic when not a terminal) |
| to follow a job elsewhere | `hep watch [CONFIG [CFG]]` (a `--journal` run's file: `hep watch --file …`) |
| a desktop notification at the end | `[run] notify = "desktop"` |
| a point faster | `shards = K` on the Rivet table (§7.1); more Pythia `threads` alone do not help |
| many points faster | `parallelism = K` or `"auto"` (§7.2) |

The identity covers cards, argv, binaries, analyses and their plugins, events and threads, and the
seeds derive from it. So a rerun of an unchanged point does nothing, and a changed one reruns by
itself. Threads are part of the identity: `--set cfgs.pdf.threads=8` makes every point "to run".
A changed configuration under a serial you set is refused rather than overwrite its points: bump
the serial, or `--rerun` (04 §2).

---

## 9. When something fails

The run goes on to the next point, and the point's block names the tool to blame. Then:

1. Read `logs/…/<point>/logs/<tool>.log` (and `<tool>.prepare.log`, `prelim.log`): a failed tool's
   last 200 lines. For a tool's whole output, run again with `--logs`.
2. A product that failed its checks keeps its `.partial` name, and the point has no `.complete`, so
   it runs again next time.
3. *"rivet analysed N events; the producer wrote M"*: the chain broke mid-stream. Look at the
   generator's log first.
4. *"… was silent for 300 s"*: a stall. Raise `stall_after` on the tool if it is legitimately quiet.
5. Fix it, then `hep run … --points <that point>`. Complete points are skipped anyway.
6. More to look at:
   - `--plan` shows the exact argv and cards;
   - `--journal` writes the job's every event to `logs/…/<cfg>/status.jsonl`;
   - `provenance.json` records every binary and card of a finished point.

Ctrl-C stops the job cleanly: the running tools get SIGINT, then SIGTERM, then SIGKILL. The exit is
6, and the same command resumes. `hep run` exits:
- 0 when everything is done;
- 1 when a point, a stage or a page failed;
- 2 for a config error (nothing ran).

Common refusals, and what they mean:

| Message | Means |
|---|---|
| `[quantities.X] is set but no tool in this chain consumes it` | nothing would change with X: give it a `to`, or drop it (C7) |
| `'delphes' cannot read a FIFO` | put Delphes in a later group, so it reads a file (C6) |
| `FIFO 'x' connects A and B across groups` | put A and B in one group, or use a file (C6) |
| `'photo_eic' does not declare the option X` | the option is not in the analysis's `.info` (C9) |
| `the PDF set 'X' is not installed` | `lhapdf install X` (C10) |
| `'…' is TLatex; labels are LaTeX` | write the LaTeX the hint gives, or `hep migrate` the file (§10) |
| `[plot.overlay] is a figure now` | `[plot.figures.<name>] class = "overlay"`, or `hep migrate` |
| `base config not found` | the card is not under `configs/<P>/` (write `./path` for elsewhere) |
| `$HEP_APPS/App_Pythia.exe is not built` | `hep build --framework` |
| `not inside a work dir` | `cd` into one, or `hep setup <dir>` (§1.2) |
| `unknown section [schema]` | a v1 (hekit) run TOML: the schema is 04; `git show HEAD:<file>` has the current one |
| `'event_count' is the v2 form: this file is v3, where it is events` | a v2 name in a v3 file: write the v3 name, or `hep migrate --v3` (04 §17) |
| `… made from other inputs; running would overwrite them` | your configuration changed under a serial you set: bump it, or `--rerun` (04 §2) |

---

## 10. Housekeeping: check, status, clean, migrate, reproduce

```bash
hep check                                   # every config: loaded, validated, every point planned; runs nothing
hep ls Demo                      # every config and its configurations (* = what hep run runs)
hep explain plot.y_gutter                   # a key's type, default and meaning
hep status Demo/jets              # each point: complete, stale, incomplete or to run
hep status --stack                          # each package's version
hep clean Demo/jets --dry-run     # what the runner made and no plan uses (logs/ and .cache/)
hep migrate Demo/jets             # a diff of the file in today's forms; --apply writes it
hep reproduce records/…/<point>/provenance.json  # the point again, beside it, compared
```

- **Before a long sweep, or as a pre-commit hook:** `hep check` exits 2 when any config is not
  well.
- **Clean:** `hep clean` never removes a result. It lists first and asks (`--yes` elsewhere), and it
  refuses while a job runs.
- **Migrate:** `hep migrate` rewrites old forms by line, so comments and layout stay, and
  `hep migrate --v3` rewrites a v2 file in v3 (04 §17):
  - TLatex labels;
  - `swept = false`;
  - `[plot.overlay]` and `[plot.object]`;
  - a bare `executable`;
  - base-card lines the runner owns.
- **Which stack a study was made with:** `[file.meta] versions = { pythia8 = "8.317", … }`. A
  different stack is a warning in `hep check` and `--plan`, never a refusal (04 §3).
- **Reproduce:** `hep reproduce` stops and says what changed when the setup is no longer the one the
  provenance records; `--anyway` runs today's setup with the recorded seed.

Each command is in [05 §1](05_Commands_and_Tools.md#1-commands).

---

## 11. Reading results from Python

```python
from runner import results                  # Heimdall's venv has framework/ on its path; elsewhere,
                                            # sys.path.insert(0, os.environ["HEP"] + "/framework")

for point in results.load("Demo/jets", "energy_pdf"):
    print(point.name, point.values["pdf"].label, point.complete, point.yoda())
```

`results.load(CONFIG, CONFIGURATION)` (V77) reads a configuration's `points.json` and returns its
points. Each has:
- `name`;
- `values` (quantity → its `tag`, `label`, `value`, `swept`);
- `products` (name → path), `results`, `output`;
- `complete`, `identity`, `seed`;
- `yoda()` / `root()` for the product of that kind.

`results.runs(CONFIG)` gives every configuration that has run. It plans nothing, so it needs no tool
installed: for notebooks and statistics tools.

---

## 12. A new project

A new study that shares nothing with the others is a new work dir: `hep setup <dir> --project
<Project> --git` (§1.2). A new project in a work dir:

1. `configs/<Project>/`: the native base card(s) and a run TOML with `project = "<Project>"`.
2. `modules/<Project>/`: Rivet plugins in `Rivet/<name>.cc` (with `.info`, `.plot`, `.yoda`), and
   programs as `<Name>.cc` with a `// requires:` line. Headers beside them are shared by both.
3. `hep build`, then `hep check <Project>/<run>`, then `hep run <Project>/<run> --plan`.
4. A quantity the vocabulary does not map gets a `to`. One your project uses everywhere can go in
   `configs/<Project>/master.toml`, named by `[file] master = "master.toml"`.
5. Tables several run TOMLs share can live in one file that each names in `[file] import` (04 §3).
