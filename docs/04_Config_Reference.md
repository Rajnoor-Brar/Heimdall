# 04 — Configuration reference

Every key a run TOML accepts: its type, default and meaning, and what is checked. **The key tables
are generated** from `framework/schema/run.toml` and `src/Apps/Paint/base.toml` (`make docs`).
`hep explain KEY` and the editor schemas read the same source, so the tables cannot drift from the
code. The prose around them says what a table cannot.
- **Worked pipelines:** [02](02_User_Guide.md).
- **Plots and figures:** [03](03_Plots.md).
- **Each standard tool's own keys:** [05](05_Commands_and_Tools.md).

**The form.** This page writes the run TOML's third form (v3, audit 3 phase 6), which says each fact
once. The second form (v2) is still read, for one release, and is the same run: the same points,
folders and identities. §17 maps its names, and `hep migrate --v3` rewrites a v2 file.

**Conventions.**
- *Type* uses TOML's words: a string, an integer, a number (an integer or a float), true or false,
  a list, a table.
- A key marked **required** has no default. A key that may take `"default"` or `"native"` says so.
- Everything is checked **at plan time**, before any process starts: `hep check` and `hep run …
  --plan` run every check below.
- **A quantity a file declares must be used:** varied in a configuration, fixed (its own `fixed`, or
  a configuration's), or choosing a tool (`"@<quantity>"`). One that changes nothing is refused,
  with the fix. An imported file's quantities may go unused.
- **Your editor can check a file as you type:** put `#:schema <Heimdall>/framework/schema/run.v3.schema.json`
  on its first line (Taplo, Even Better TOML). The schema knows every table and key, and each
  standard tool's own keys.

A whole file, to see the tables together:

```toml
[run]
project = "Demo"
name    = "pair"
run     = "pdf"                          # the configuration `hep run Demo/pair` runs
events  = 500
threads = 2
chain   = [["pythia", "rivet"], "yd2rt"] # every configuration's tools, unless it says its own

[tools.pythia]                           # the table's name is the tool
card   = "ep.cmnd"
output = "events.hepmc"                  # rivet reads it in the same group: a FIFO

[tools.rivet]
input    = "pythia"                      # what pythia writes
analyses = ["photo_eic"]
output   = "jets.yoda"                   # read by a later group: a product, in results/

[tools.yd2rt]
input  = "rivet"
output = "jets.root"

[quantities.pdf]
fixed  = "MSTW08lo"                      # the point a configuration that does not vary it takes
points = [
  { tag = "MSTW08lo",  value = "LHAPDF6:MSTW2008lo68cl",         label = "MSTW 2008 LO" },
  { tag = "NNPDF23lo", value = "LHAPDF6:NNPDF23_lo_as_0130_qed", label = "NNPDF 2.3 LO" },
]

[cfgs.single]
description = "One point, at the fixed PDF"

[cfgs.pdf]
vary = ["pdf"]                           # one point per PDF
```

---

## 1. Files, and which wins

| File | Holds | Written by |
|---|---|---|
| native base cards: `configs/<P>/*.cmnd`, `.in`, `.yaml`, `.sin`, `.mg5`, `.tcl` | the physics | you; never modified by the runner |
| the run TOML: `configs/<P>/<run>.toml` | configurations, quantities, tools, wiring, plots | you |
| `framework/schema/quantities.toml` (what each quantity name means) and each tool folder's `quantities.toml` (how that tool consumes it), optionally overlaid by a project's master | how each standard tool consumes named quantities (§3) | the framework; a project may add to it |
| `src/Apps/Paint/base.toml`, optionally a style file | the look of the pages (§12) | the framework; you, to change every page |

**Physics stays in the native card.** A quantity renders an *override* into a point card. The base
card is read first, and the override is applied by the tool's own rule: last wins for Pythia, a
YAML merge for Sherpa, and so on (see [05](05_Commands_and_Tools.md)).

**Precedence of a value, lowest to highest:**

```
<tool>/quantities.toml (shipped < machine < work dir)  <  [file].master  <  [quantities.<q>].to  <  --set
a quantity's fixed  <  [cfgs.<name>].fixed  <  --set …fixed…  <  the value a vary gives the point
[run]  <  extends  <  [cfgs.<name>]  <  --set
[file].import files  <  this file
base.toml  <  machine style.toml  <  work dir style.toml  <  [plot].root_style file  <  [plot.style]  <  [plot.figures.<figure>].style
[plot]  <  [plot.figures.<figure>]
```

A run TOML has exactly these top-level tables, and any other is an error (C1): `[file]`, `[run]`,
`[cfgs]`, `[tools]`, `[quantities]`, `[plot]`, `[cluster]`.

**`"default"` means "the layer below's value"**, as if the key were left out (03 §6): in a
configuration, `[run]`'s or the one it extends; in a figure, `[plot]`'s; in a style layer, the one
below; at the top, the runner's default (the tables' *Default*). Only a key whose type says so takes
it, and `--set key=default` works for one run.

**`"native"` means "what the drawing tool does by itself"**, for the page keys of `[plot]` and a
figure that say so: no gutter, the `.plot`'s log axes, the tool's own range (§11). v2 wrote this as
`"default"` in `[plot]` itself, and `hep migrate --v3` rewrites it.

---

## 2. Paths

Every key that takes a path has **one** convention root. There is no search path and no fallback.
The roots are the **work dir**'s: the folder whose `hep.toml` has a `[work]` table, found by walking
up from the working directory (or `$HEP_WORK`), never the working directory itself (05 §2).

| Written as | Resolves to |
|---|---|
| `name` or `sub/name` | the key's convention root (table below) + `name` |
| `./sub/name` | the **work dir** + `sub/name` (never the working directory) |
| `/abs/path` | as written |
| `../x`, `a/../b` | **an error** (C12): write `./…` or an absolute path |

| Key | Root of a bare name | Example |
|---|---|---|
| `hep run <config>`, `hep plot <config>` | `configs/`, `.toml` optional | `Demo/jets` → `configs/Demo/jets.toml` |
| `[file].master`, `[file].import` | `configs/<project>/` | `master.toml` |
| `[tools.*].card` | `configs/<project>/` | `ep.cmnd` |
| `[tools.*].executable` | `build/<project>/`, which must exist; `path:<command>` asks for a command on `PATH` by name | `Decay.exe` → `build/Decay/Decay.exe`; `path:python3` |
| `[tools.*].filters` | `configs/<project>/` | `fit_filters.toml` |
| `[tools.*].input` | a tool table's name (what it writes), another tool's `output` by name, a pre product; otherwise a path under the point's output directory | `"pythia"`, `events.hepmc` |
| `[tools.*].output` | a FIFO or a scratch file (§6) → the point's output directory; **anything else → the point's results directory** (a product) | `jets.yoda` → `results/…/<point>/jets.yoda` |
| `[plot].root_style` | `configs/<project>/`, `.toml` optional | `talk` → `configs/<P>/talk.toml` |
| `[plot.data].file` | `datasets/`, or `rivet:<Analysis>` for Rivet's own reference data | `rivet:ZEUS_2012_I1116258` |

**The one judgement:** what a tool writes is a product, in `results/`, unless it is technical: a
FIFO (its reader is in the producer's group) or a scratch file (its producer says `keep = false`),
both in `logs/` (§6). So a HepMC file kept for another configuration is a product: leave `keep`
out.

**Where a point lives** (by lifecycle):

```
results/<P>/<run>/<cfg>/<point>/    the products: yours
records/<P>/<run>/<cfg>/<point>/    provenance.json  identity.json  .complete: what the run recorded, kept
logs/<P>/<run>/<cfg>/<point>/       cards/  config/  logs/  FIFOs and scratch files  .lock: safe to delete
```

`.cache/<P>/` holds what is rebuilt on demand (prepare caches, card checks, converted data). Deleting
`logs/` or `.cache/` reruns nothing; deleting `records/` makes every point "to run" again. A point
another session is running is skipped, naming who runs it, unless `--wait`.

- `<run>` is `[run].name`, or the configuration's own `name`.
- `<cfg>` is `NN_<folder>`. `<folder>` is the configuration's `folder`, or its table key when that is
  empty or unset.
- `<point>` is the varied quantities' tags joined by `_`, in `vary` order, or `point` when nothing
  is varied. Two points with the same name are an error (C11).

**The serial `NN`** is where a configuration's results go, never part of an identity (03 §6):
- **Left out** (in the configuration and in `[run]`), the runner numbers the folder. It takes the
  newest folder whose points were made from the configuration as it stands now, or an older one
  when a change was undone. When nothing there was made yet, it takes the newest folder. Otherwise
  it takes a new number, so a changed configuration never overwrites what it made. `--plan` says
  which folder and why (`note: folder 02: new (01 holds other inputs)`).
- **Set** (`serial = 3`, the configuration's or `[run]`'s), the folder is yours: `03_<folder>`. A
  run that would overwrite points made there from other inputs is refused, with the bump as the
  hint (`serial = 4`). `--rerun` overwrites them, and `--why` says what changed. `hep cluster`
  checks before it submits.

Two configurations of a file may not write one folder, and a numbered folder is one configuration's:
a configuration the runner numbers takes every `NN_<folder>` of its folder name.

---

## 3. `[file]`

How the file is read: what it imports, a project master, its vars and its meta.

```toml
[file]
import = ["common.toml"]         # optional: run TOMLs whose tables this one starts from; this file wins
master = "master.toml"           # optional: configs/<project>/master.toml overlays the tool folders' mappings
```

<!-- generated: keys3 file -->
| Key | Type | Default | Meaning |
|---|---|---|---|
| `master` | a string |  | overlays the tool folders' mappings key by key (`[quantities.<tool>.compatible_quantities]`): an entry for a (tool, quantity) pair replaces the framework's. The file must exist. |
| `import` | a string or a list (a string or a table each) |  | run TOMLs this one starts from, in order, named as `hep run` names a config: `name` is this project's (`configs/<project>/name.toml`), `<Project>/<name>` another project's, `./…` from the work dir; `.toml` optional. **This file wins**: a quantity or configuration of the file replaces the imported one whole; a tool table, `[plot]`, `[cluster]` and `[run]`'s own keys merge key by key, tables recursively. Imports nest, depth-first; a circle is refused. Another project's file keeps its bare paths its own project's. The file that imports sets its own `[run].name` and `project`. An entry may be `{ from = "<config>", only = ["quantities", "cfgs.default", …] }`: only those tables or dotted keys, each of which the file must have |
| `drop` | a list (a string each) |  | dotted keys (`cfgs.default4`, `plot.figures.statistics`, `quantities.radius`, `tools.jets`) taken out of what the imports brought in, before this file's own tables are laid over them. Each must name something an import gave, so a misspelt drop is refused rather than keeping what it meant to remove; a file that imports nothing has nothing to drop. |
| `vars` | a table |  | `name = value`, cited in any string of the file as `{var:name}` and replaced when the file is read, after its imports and `--set`, so an identity sees only the result. A string that is exactly one var takes its value as it is: `events = "{var:events}"` is an integer, and a list stays a list; inside a longer string a var must be a scalar (`"rivet:{var:ana}"`). An unknown name is refused with the nearest. An imported file's `{var:…}` takes this file's value; its own `[file.vars]` come with whatever is taken of it, under this file's. `--set file.vars.<name>=…` changes one for a run |
| `meta` | a table |  | descriptive: it never changes a run. Any key is free text for people (`author`, `references`, …) except `versions = { pythia8 = "8.317", rivet = "4.1.3" }`: the packages of `env/stack.toml` the file was run with, each version a string. A version the stack does not have (`6.5` matches 6.5.6) is a **warning** in `--plan`, at the run's start and in `hep check`, which still passes: the run goes ahead, at your own risk. A package stack.toml does not name is refused, since its warning could never come. |
| `schema` | an integer |  | `3`, or `2` to keep a v2 file v2 for one release; a file with `[file]` is v3 without it |
<!-- /generated -->

**`import`**. The imported files are read in order, then this file's tables are laid over
them:
- a quantity or configuration of the file replaces the imported one whole;
- a **tool table merges key by key**: `[tools.rivet] analyses = ["photo_eic:R=0.7"]` changes that
  key of the imported rivet table and keeps the rest (03 §6);
- `[plot]`, `[cluster]` and `[run]`'s own keys merge key by key, tables recursively;
- `"default"` in this file keeps the imported value.

Its rules:
- **Names:** an import is named as `hep run` names a config: `validation_common` is this project's,
  `Demo/validation` another project's, and `./…` is from the work dir.
- **Nesting:** an imported file is read the same way first, so its own imports come before it,
  depth-first. A circle is refused, naming it.
- **Another project's file:** its bare paths stay its own project's (the keys the schema marks
  `path`: `card`, `filters`, `executable`, `root_style`, `master`). They are made absolute when it
  is read, so its tools find their cards and plan to the same identities as in their own file.
- **Location:** the file that imports sets its own `[run].name` and `project`; location is never
  imported. It may share an imported run's name, so its results sit beside the other's
  (`results/Demo/validation/03_PDFs_150M` beside validation's own `02_PDFs_150M`), but no
  configuration of the two may have the same folder, or their points would overwrite each
  other's.
- **Part of a file**: an entry `{ from = "validation", only = ["tools", "quantities",
  "cfgs.default"] }` takes only those tables or dotted keys, each of which the file must have.
- **Taking out**: `drop = ["cfgs.default4", "plot.figures.statistics"]` removes dotted keys
  from what the imports gave, before this file's tables. Each must name something an import gave,
  and a file that imports nothing has nothing to drop. An imported file's own `drop` applies to its
  own imports.
- **Two forms:** a v3 file may import a v2 file and the other way round; `only` and `drop` are
  written in the importing file's own names.

`--show-config` lists where each quantity, tool and configuration came from, through every file
(`run.cfgs.default from validation.toml ← validation_common.toml`).

**`vars`**. Names said once and cited anywhere in the file:

```toml
[file.vars]
ana    = "ZEUS_2012_I1116258"
events = 1_000_000

[run]
events = "{var:events}"             # one var, the whole value: an integer, as written there

[tools.rivet]
analyses = ["{var:ana}"]

[plot.data]
file = "rivet:{var:ana}"            # inside a longer string: a scalar, as text
```

They are replaced when the file is read, after its imports and `--set` (`--set
file.vars.events=50000`), so a point's identity is that of the same file written out. An imported
file's `{var:…}` takes this file's value: a shared file can be written with parameters. An imported
file's own `[file.vars]` come with whatever is taken of it, `only` included, below this
file's, so the tables it gives always find the vars they cite. An unknown name is refused with the
nearest. `{var:…}` is the run TOML's own; the page texts' placeholders (`{cell}`, `{q:…}`, `{opt:…}`,
§10) are filled later, per page.

**`meta`**. About the file, for people; it never changes a run:

```toml
[file.meta]
author     = "R. Brar"
references = ["ZEUS, Nucl. Phys. B 864 (2012) 1"]
versions   = { pythia8 = "8.317", rivet = "4.1.3", lhapdf = "6.5" }   # the stack the file was run with
```

`versions` names packages of `env/stack.toml`, each with a version string. When the stack has
another version, `--plan`, the run's start and `hep check` say so as a **warning**, and the run goes
ahead at your own risk. What is written is compared: `6.5` matches 6.5.6. A package stack.toml does
not name is refused, since its warning could never come. Every other key is free.

**The vocabulary** (`framework/schema/quantities.toml`) says what each quantity name means for every
tool:
- its **shape**: `energies` is two numbers, `[beam A, beam B]`; `beams` is two PDG ids; `pdf` is a
  string or a set number;
- its **unit**.

A run TOML's quantity of that name is checked against the shape when the file is read (`value =
[275, 18]` in a row). A name the vocabulary does not have is the user's own, and reaches a tool
through its `to` (§8.1), unless a tool folder declares it: an entry of a folder's `quantities.toml`
for a new name, with a `shape` (and `unit`, `doc`), adds that word to the vocabulary (a study's own
tool, `tools/fit/quantities.toml`: `window = { config = "cuts.window", shape = ["float", "float"], doc
= "the fit window" }`; `config` is a key of an exec or module tool's config, dotted keys nesting). It
then binds like Heimdall's words, with no `to`; `hep explain <name>` describes any of them, and how
each tool maps it. A folder cannot redefine Heimdall's words.

**Each tool folder** says how that tool consumes the vocabulary, in
`<tool>/quantities.toml` (Heimdall's `framework/tools/`, then the machine root's and the work dir's
`tools/`, each over the folder it extends: [06 §16](06_Internals.md#16-the-tool-folder-contract)); a
project master overlays those mappings in the same form:

```toml
[quantities.pythia.compatible_quantities]           # [quantities.<tool>.compatible_quantities]
sqrts    = { key = "Beams:eCM" }                      # the card line  Beams:eCM = value
energies = { keys = ["Beams:eA", "Beams:eB"] }        # an array value spread over several keys, in order
pdf      = { key = "PDF:pSet", check = "lhapdf:pythia" }  # the value as written; a provider check (C10)

[quantities.herwig.compatible_quantities]
seed_offset = { flag = "-x" }                         # a command-line argument instead of a card line
```

- **One form per entry:** each entry takes **exactly one** of `key`, `keys` and `flag`; `format` and
  `check` are additions.
- **`check`** is a provider check (C10), giving the `lhapdf install <set>` line to type when a set is
  not under `LHAPDF_DATA_PATH`.
  - `"lhapdf:bare"` takes a bare set name, `<set>[/member]`, as Sherpa does.
  - `"lhapdf:pythia"` takes the value exactly as Pythia's `PDF:pSet` reads it (no prefix is
    added). That is `"LHAPDF6:<set>[/member]"`, whose set must be installed; one of Pythia's own set
    numbers (`13`, checked against its `PDFSelection.xml`); or a grid file.
  - A bare name that is an installed LHAPDF set is refused with the `LHAPDF6:` spelling, since Pythia
    would read it as a file.
- **A tool with a `render.py`** takes plain `key` mappings and interprets the keys itself: a YAML
  path for Sherpa, a SINDARIN variable for Whizard.

**What the tool folders map:**

| Quantity | pythia | sherpa | herwig | whizard | madgraph |
|---|---|---|---|---|---|
| `energies` `[E_A, E_B]` | `Beams:eA`, `Beams:eB` | `BEAM_ENERGIES` | `Luminosity:BeamEMaxA`, `…MaxB` (×GeV), in Herwig's slots (lepton on A) | `beams_momentum` | `ebeam1`, `ebeam2` |
| `sqrts` | `Beams:eCM` | `BEAM_ENERGIES = [√s/2, √s/2]` | `Luminosity:Energy` | — | — |
| `beam_a`, `beam_b` | `Beams:idA`, `Beams:idB` | — | — | — | — |
| `beams` `[id_A, id_B]` | `Beams:idA`, `Beams:idB` | `BEAMS` | — | `beams` (model names) | `lpp1`, `lpp2` |
| `pdf` (checked, C10) | `PDF:pSet = <value>`: write `"LHAPDF6:<set>"`, or a Pythia set number | `PDF_SET[0]` (and `MPI_PDF_SET`): the bare `<set>` | — | — | — |
| `events` (built-in) | `Main:numberOfEvents` | `EVENTS` | (the `-N` flag) | `n_events` | `nevents` |
| `threads` (built-in) | `Parallelism:numThreads` | — | — | — | — |

**Beam order**.
- `energies` and `beams` are lists in **the run's** beam order, `[beam A, beam B]`.
- A point that gives `beams` (or `beam_a` and `beam_b`) names that order. One that gives none
  follows the convention `[hadron, lepton]`, which every card so far assumes.
- A tool whose card needs its beams in fixed slots says so (`[beams] slots`: Herwig's
  `EPCollider.in`, lepton on A), and the runner reorders every per-beam value for it, the ids and
  the energies together.
- The other tools take the order as given.

`rivet` maps nothing: it reads beams and energies from the events, and its analysis options are
always targeted explicitly (§8.1).

---

## 4. `[run]`

What the run is, and what every configuration starts from.

```toml
[run]
name    = "jets"
project = "Demo"
run     = "pdf"                     # the default; `hep run <config> <configuration>` picks another
events  = 1_000_000                 # every configuration's, unless it says its own
threads = 20
chain   = [["pythia", "rivet"], "yd2rt"]
seed    = "identity"                # the default: from the generator's identity
description = "Inclusive jets in ep collisions"
```

<!-- generated: keys3 run -->
| Key | Type | Default | Meaning |
|---|---|---|---|
| `name` | a string | **required** | the run's directory name |
| `project` | a string | **required** | the subfolder of `configs/`, `modules/`, `records/`, `logs/`, `results/`; must equal the folder the file is in, when it is under `configs/` |
| `run` | a string |  | the configuration `hep run <file>` runs, a `[cfgs.<name>]` (C2). Under `sweep_runs` it may be left out |
| `serial` | an integer |  | the prefix `NN_` of each configuration's folder, `<name>/NN_<folder>`: **location, never identity**. Left out, the runner numbers it: the newest folder made from these inputs, else a new one (04 §2). Set, a changed configuration is refused there rather than overwrite what it made (`--rerun` overwrites) A configuration inherits it from `[run]`. |
| `events` | an integer, ≥ 1 |  | every configuration's event count, unless it gives its own A configuration inherits it from `[run]`. |
| `threads` | an integer, ≥ 0 | `1` | default for configurations. `0` means every core, **resolved to a number at plan time** A configuration inherits it from `[run]`. |
| `parallelism` | an integer or a string: `"auto"`, ≥ 1 | `1` | default for configurations: how many points run at once; `"auto"`: as many as the cores hold, `os.cpu_count() // the costliest point's cores`. `threads` stays each point's; never part of an identity or a seed, so changing it reruns nothing A configuration inherits it from `[run]`. |
| `description` | a string |  | what the run is for |
| `sweep_runs` | true or false or a list (a string each) | `false` | `true`: `hep run <config>` runs every configuration, one after another, in the order of the file; `["a", "b"]`: these, in this order (04 §4.1) |
| `notify` | a string: `"none"`, `"desktop"` | `"none"` | `"desktop"`: a desktop notification (`notify-send`) when `hep run` ends, with its verdict; never fails a run |
| `chain` | a list |  | every configuration's tools, unless it gives its own (04 §5.3) A configuration inherits it from `[run]`. |
| `vary` | a list |  | 04 §5.1; `[]` is one point A configuration inherits it from `[run]`. |
| `plot_points` | a list (a string each) |  | 04 §5.2 A configuration inherits it from `[run]`. |
| `combine` | a list (a string each) |  | swept quantities whose points are merged into one curve (04 §5.5) A configuration inherits it from `[run]`. |
| `pre` | a list |  | the form of `tools` (04 §5.4) A configuration inherits it from `[run]`. |
| `post` | a list |  | the form of `tools` (04 §5.4) A configuration inherits it from `[run]`. |
| `generate_cards` | a list (a string each) |  | tool tables (tags) whose cards and configs are made for the point although they do not run in it, for a program that runs them itself (an integrated program: Pythia and Rivet inside it); and `"<tag>:<product>"` for a product made on demand (Herwig's `run`, Sherpa's `results`, MadGraph's `process`). The chain's tools are always in the context file, which every tool finds through `HEP_CONTEXT` (04 §9.4) A configuration inherits it from `[run]`. |
| `seed` | a string or an integer | `"identity"` | `"identity"`: from the generator's identity; `"random"`: drawn when the point runs; an integer: exactly that seed for every point (a replica, `to = { "pythia/seed" = true }`, gives a point its own: 04 §8.2; 06 §8) |
| `commands` | a list |  | argv arrays run in each point's output folder before its tools, in order; output to `logs/prelim.log`; a nonzero exit fails the point. Placeholders: `{work}`, `{hep}`, `{out}`, `{res}`, `{file:<name>}` |
<!-- /generated -->

Any other key or table in `[run]` is an error (C1). `[run].run` is required unless `sweep_runs` is
set. An event count must be set here or in every configuration. `serial` is optional (§2).

### 4.1 `sweep_runs`: every configuration, one run after another

With `sweep_runs = true`, `hep run <config>` runs every configuration, in the order of the file.
With a list, `sweep_runs = ["pdf", "energies"]`, it runs those, in the list's order. A name
that is not a configuration, or one named twice, is refused.

Each one is **a run of its own**: exactly what `hep run <config> <cfg>` does, with its own title,
blocks, verdict, journal, `points.json` and plots, in its own folder. Each starts after one header
line of its `title`:

```
run 01 - Proton PDFs -
jets · pdf: 4 point(s), 1000000 events, 12 threads
── point 1/4: MSTW08lo ── ok after 12min 4s
…
4 done, 0 failed, 0 skipped
```

- **Every run is planned before the first starts**, so a config error in any of them exits 2 with
  nothing run. Each is planned again when its turn comes, so edits to the TOML made meanwhile
  count; a run an edit has broken fails alone.
- **The runs are pipelined**: a run starts once the one before has started all its points,
  and its points take the cores the earlier run's last points leave free.
  - Each run's own order (pre, points, combined, post, plots), folder, journal and verdict are kept.
  - While two runs overlap, a block's heading names its run: `── point 1/4 (energies): 5x41 ── ok
    after …`.
- **A failed run lets the next start.** Ctrl-C stops the running runs (exit 6) and **starts no
  more**.
- **The exit code** is 6 if a run was stopped, else 1 if any failed, else 0.
- **Running one:** `hep run <config> <cfg>` runs just that one, whether or not the sweep lists it.
- **Options:**
  - `--plan` prints every run's plan under its header;
  - `--rerun`, `--set` and `--only plot` apply to each;
  - `--only pre|post` skips the runs without that stage;
  - `--points` is refused: name the configuration.
- **Being in a sweep changes no run**: not its identity, its seeds or its folder.

---

## 5. `[cfgs.<name>]`

A configuration is a table of `[cfgs]`, picked by `hep run <file> <name>`. It says only what differs
from `[run]`: what it varies, fixes and runs. Any name may be used, `threads` or `default`
included. A configuration's dotted path is `cfgs.<name>.<key>`: `--set cfgs.pdf.threads=8`,
`drop = ["cfgs.default4"]`, `hep explain cfgs.pdf.threads`.

```toml
[run]                                        # what every configuration starts from …
chain   = [["pythia", "rivet"], "yd2rt"]
threads = 20

[cfgs.energy_pdf]
serial      = 3                              # optional: 03_energy_pdf (§2)
title       = "Beams x PDFs"                 # the header line under [run].sweep_runs (§4.1)
description = "Beams x PDF grid: one page per energy, PDF curves on each"
events      = 500_000                        # over [run]'s
vary        = ["energies", "pdf"]            # 4 × 4 = 16 points
plot_points = ["energies"]                   # 4 pages; the PDFs are the curves on each

[cfgs.mpi]
vary  = ["pt0ref"]
fixed = { energies = "18x275" }              # this configuration's fixed point, over the quantity's own

[cfgs.pdfs_100M]
extends = "energy_pdf"                       # everything of energy_pdf, then these
events  = 100_000_000
folder  = "PDFs_100M"                        # its folder name; the table key when left out
```

A configuration's value is, in order:
1. its own;
2. else the one it `extends`'s, in turn;
3. else `[run]`'s;
4. else the default.

`[run]` takes every configuration key (the tables of §4 and §5 say which) but `folder`, `title`,
`extends` and `fixed`, which belong to each configuration alone; a quantity's own `fixed` is the
file-wide one. `"default"` in a layer is the next layer's value. A chain of `extends` is followed,
and a circle is refused. `hep run CONFIG --show-config` prints every value with the layer it came
from.

<!-- generated: keys3 cfgs -->
| Key | Type | Default | Meaning |
|---|---|---|---|
| `extends` | a string |  | another configuration this one starts from (chains are followed; a circle is refused) |
| `serial` | an integer, or `"default"` |  | this configuration's `NN_`, over `[run]`'s; left out in both, the runner numbers it (04 §2) |
| `name` | a string |  | the run folder above this configuration's: `<P>/<name>/NN_<label>/` |
| `folder` | a string |  | the configuration's folder, after the serial: `NN_<folder>`; empty means the table key |
| `title` | a string |  | the header line of the run under `[run].sweep_runs`: `run 02 - <title> -` (04 §4.1) |
| `description` | a string |  | what the configuration is for |
| `events` | an integer, ≥ 1, or `"default"` |  | required here if `[run]` has none. A list is one configuration per count, `<name>_<count>` (`pdf_10k`), run in turn as `<name>` (04 §5.6) |
| `threads` | an integer, ≥ 0, or `"default"` |  | `0` = every core |
| `parallelism` | an integer or a string: `"auto"`, ≥ 1, or `"default"` |  | points at once (`"auto"`: cores ÷ a point's cores); `--plan` and the run's title say about how many cores that is, and warn past the machine's |
| `vary` | a list |  | 04 §5.1; `[]` is one point |
| `plot_points` | a list (a string each) |  | 04 §5.2 |
| `combine` | a list (a string each) |  | swept quantities whose points are merged into one curve (04 §5.5) |
| `chain` | a list |  | 04 §5.3; `[run]`'s when left out |
| `generate_cards` | a list (a string each) |  | tool tables (tags) whose cards and configs are made for the point although they do not run in it, for a program that runs them itself (an integrated program: Pythia and Rivet inside it); and `"<tag>:<product>"` for a product made on demand (Herwig's `run`, Sherpa's `results`, MadGraph's `process`). The chain's tools are always in the context file, which every tool finds through `HEP_CONTEXT` (04 §9.4) |
| `pre` | a list |  | the form of `tools` (04 §5.4) |
| `post` | a list |  | the form of `tools` (04 §5.4) |
| `fixed` | a table |  | `{ quantity = "tag" }`: this configuration's fixed points, over each quantity's own `fixed` (04 §7) |
| `cluster` | a table |  | merged over the run TOML's `[cluster]`, key by key, for this configuration's jobs (a longer `time` for its many events, say); the same keys (04 §16) |
| `seed` | a string or an integer | `"identity"` | `"identity"`: from the generator's identity; `"random"`: drawn when the point runs; an integer: exactly that seed for every point (a replica, `to = { "pythia/seed" = true }`, gives a point its own: 04 §8.2; 06 §8) |
<!-- /generated -->

### 5.1 `vary`

- A **string** is an independent axis. The points are the grid (Cartesian product) of the axes.
- An **array** is an **entangled** group: its quantities move together, value *i* with value *i*,
  so they need equal point counts (C3). The group is one axis of the grid. A compound quantity
  (§8.4) is such a group written once.
- The order decides the point names (tags joined in `vary` order) and the running order.
- Every name must be a declared quantity, and none may appear twice (C3).
- A quantity's `exclude = [i, …]` (1-based) leaves those points out of every vary of it (§8).

```toml
vary = ["energies", ["pdf", "alphas"], "mpi"]    # 4 × 3 × 2 = 24 points: pdf and alphas zipped
```

### 5.2 `plot_points`

Each name must be varied here (C4). The **pages** are the grid of their points, and every other
varied quantity becomes the **curves** on a page. `[]` is one page, with every point as a curve.
Naming one member of an entangled group (or a compound quantity) selects the group.

| `vary` | `plot_points` | Page folders | Curves per page |
|---|---|---|---|
| `["pdf"]` | `[]` | 1 (no folder) | 4 |
| `["energies", "pdf"]` | `["energies"]` | 4 (`5x41/`, …) | 4 |
| `["pt0ref", "mpi"]` | `["mpi"]` | 2 | 3 |

### 5.3 `chain`

- **Entries:** each entry is a **tool table's name** (a key of `[tools]`) or an **array of names**
  that run **together** as one group (one level only; C5). An empty group is an error.
- **Order:** groups run in order. A group starts only when the previous one succeeded and its
  products passed their checks.
- **The interfaces follow from it** (§6): what a tool writes for a reader in its own group is a
  FIFO; for a later group, a file.
- **`"@<quantity>"`** is replaced, per point, by the tool table that quantity's value names:
  `chain = [["@generator", "spectra"]]` with points whose values are `"pythia"`, `"herwig"` and
  `"sherpa"`. The quantity must be varied or fixed, and every value must be a tool table (C5).
- **Cards for tools not run:** a table in `generate_cards` (§9.4) need not be in the chain; its card
  and config are rendered for the point's context file, and it is not run.

### 5.4 `pre` and `post`

The same form as `chain`, run **once**:

| | When | Where | Inputs | Identity |
|---|---|---|---|---|
| `pre` | before the first point; a failure stops the run | `…/<cfg>/pre/` | `{points}` (the manifest) | its own; **part of every point's**, so a changed pre stage reruns the points |
| `post` | after the points, **only when every point is complete** | `…/<cfg>/post/` | an `input` naming a product of the points reads that product **of every point** (`{inputs}`, `{named_inputs}`); `{points}` | its own plus every point's: it reruns when any point changes |

- **What they take:** neither takes quantities, FIFOs or scratch files.
- **Names:** a point may not be named `pre` or `post`.
- **Pre products** are interfaces every point may name as `input`.
- **Post outputs:** a post tool may not write a file with the name of the points' product.

### 5.5 `combine`

`combine = ["replica"]` merges the points that differ **only** in the combined quantities, so
each group becomes one curve with their statistics added. The typical use is seed replicas, so that
one PDF's five 1M-event seeds become one 5M-event curve:

```toml
[cfgs.default]
vary    = ["pdf", "replica"]        # 4 PDFs × 5 seeds = 20 points
combine = ["replica"]               # 4 groups, one per PDF: rivet-merge -e of its 5 seeds
chain   = [["pythia", "rivet"]]

[quantities.replica]
to     = { "pythia/seed" = true }   # a seed block of its own per point (§8.2); renders nothing
points = [{ tag = "s1", value = 1 }, { tag = "s2", value = 2 }, { tag = "s3", value = 3 },
          { tag = "s4", value = 4 }, { tag = "s5", value = 5 }]
```

| | |
|---|---|
| The groups | points with the same values of every other varied quantity; named by those values' tags (`MSTW08lo`), or `combined` when every varied quantity is combined |
| The merge | a stage per group, after its points: the `merge` tool (`rivet-merge -e`, [05 §7](05_Commands_and_Tools.md#7-merge--rivet-merge-in-post)) of the points' YODA product into `results/…/<cfg>/<group>/<product>`, beside the points' folders; skipped when complete, rerun when any of its points changes; `--plan` lists them |
| The pages | drawn from the groups, not the points: the combined quantities are neither pages nor curves |
| Rules (C14) | each name is varied here as an axis of its own (not inside an entangled group), and is not in `plot_points` |

The points keep their own products. Another configuration with the same vary and no `combine`
draws each seed as its own curve, from the same seeds and events. To merge for one figure only, use
a `merged` figure ([03 §7.4](03_Plots.md#74-merged-points-merged-for-this-figure)). The whole
example is `configs/Demo/seed_sweep.toml`.

### 5.6 `events` as a list: one configuration per count

```toml
[cfgs.pdf]
vary   = ["pdf"]
events = [100_000, 1_000_000, 10_000_000]
```

A list of event counts makes one configuration per count, named `<name>_<count>` (`pdf_100k`,
`pdf_1M`, `pdf_10M`), each in its own folder (`<folder>_<count>`). `hep run <file> pdf` runs them
in turn, as a sweep of runs (§4.1), and `hep run <file> pdf_1M` runs one. A configuration cannot
`extends` such a family: extend one of its counts. To vary the count within one configuration, with
the counts as curves, declare `events` as a quantity (§8.3).

---

## 6. Interfaces: FIFOs and files, from the chain

How one tool's output reaches another is not written: it follows from the chain (03 §6).

| The reader of an `output` is | It is | It lives in |
|---|---|---|
| in the producer's group | a **FIFO**, made fresh per attempt before the group starts, removed when the point ends | the point's output directory |
| in a later group | a **file**: a product | the point's **results** directory |
| in a later group, and the producer says `keep = false` | a **scratch file**, created empty before the point (the writer truncates) and kept | the point's output directory |
| nobody | a product | the point's results directory |

```toml
[run]
chain = ["pythia_file", "delphes", "jets_reco"]   # three groups: files between them

[tools.pythia_file]
uses   = "pythia"
card   = "ep.cmnd"
output = "showered.hepmc"
keep   = false                                    # a scratch file of the point, not a product
```

- A FIFO connects tools **in one group** only, has **one reader**, and never feeds a tool whose
  folder is not `streamable` (C6): put that tool in a later group, so it reads a file.
- A configuration with another chain has its own interfaces, worked out from its chain.
- `[run] commands`, argv arrays, run in each point's output directory before its first group, in
  order. Their output goes to `logs/prelim.log`, and a nonzero exit fails the point.

`hep run … --show-config` lists each configuration's interfaces, "inferred from the chain". v2
declared them in `[prelim]` (`fifo`, `files`), which a v3 file refuses.

---

## 7. Fixed points and selectors

A quantity a configuration does not vary takes its **fixed** point, if it has one:

```toml
[quantities.energies]
fixed  = "27x920"       # a tag …
points = [{ tag = "18x275", value = [275, 18] }, { tag = "27x920", value = [920, 27.5] }]

[cfgs.eic]
fixed = { energies = "18x275" }   # this configuration's, over the quantity's own
```

- **When it applies:** a fixed point applies **only when the quantity is not varied** in the
  active configuration.
- **What it may name:** a configuration's `fixed` names declared quantities. It is merged over the
  quantities' own, and `--set cfgs.<name>.fixed.<q>=…` or `--set quantities.<q>.fixed=…` over both.
- **Inactive quantities:** a quantity that is neither varied nor fixed is **inactive**: it renders
  nothing, and the base card's value stands. A declared quantity no configuration uses is refused
  (the conventions above).
- **Selectors** (`fixed` values and `--points q=…`), tried in order: a declared **tag**, then an
  exact **value** (numbers compare numerically: 6 finds 6.0), then **`#N`**, the N-th point
  (1-based). A selector that matches nothing lists the tags.

---

## 8. `[quantities.<q>]`

A quantity is a table of its points, one row each, its fixed point, and where its value goes.

```toml
[quantities.pdf]                     # in the vocabulary: no `to` needed; Pythia reads the value as written
fixed  = "MSTW08lo"
points = [
  { tag = "MSTW08lo",  value = "LHAPDF6:MSTW2008lo68cl",         label = "MSTW 2008 LO" },
  { tag = "NNPDF23lo", value = "LHAPDF6:NNPDF23_lo_as_0130_qed", label = "NNPDF 2.3 LO", style = { line = "dashed" } },
]

[quantities.pt0ref]                  # not in the vocabulary: name the key per tool
to     = { pythia = "MultipartonInteractions:pT0Ref" }
points = [{ tag = "3.0", value = 3.0 }, { tag = "3.2", value = 3.2 }, { tag = "3.4", value = 3.4 }]

[quantities.radius]                  # a Rivet analysis option
to     = { "rivet/photo_eic" = "R" }
points = [{ tag = "R04", value = 0.4 }, { tag = "R07", value = 0.7 }, { tag = "R10", value = 1.0 }]
```

<!-- generated: keys3 quantities -->
| Key | Type | Default | Meaning |
|---|---|---|---|
| `shape` | a string or a list |  | the values' shape, in the vocabulary's grammar: `"pdg"`, `"float\|int"`, `["float", "float"]`; checked when the TOML is read. For a quantity of your own (one the vocabulary, `framework/schema/quantities.toml`, does not name); a vocabulary quantity has its own shape |
| `to` | a string or a table |  | where the value goes: `{ pythia = "PDF:pSet" }` a native key per tool table or tool; `{ "rivet/photo_eic" = "R" }` an analysis option; `{ "pythia/seed" = true }` a replica. An entry with a `/` or `true` makes the entries the only consumers (04 §8.1) |
| `format` | a string |  | a Python format for the value: `"{}*GeV"` |
| `description` | a string |  | what the quantity is |
| `exclude` | a list |  | points a vary leaves out, by their **1-based** place (as `fixed = "#2"` and `--points 2` count): `exclude = [2]` varies the others. The remaining points keep their names and identities and are numbered 1… over what is varied. In an entangled group, a point any member excludes leaves the group. `fixed` may still pick an excluded point. Refused: a place outside the points, or none left |
| `points` | a list |  | the points, one row each: `{ tag, value, label, style }`; `value` is required, `tag` names the point's folder |
| `fixed` | a string or an integer or a number |  | the point a configuration that does not vary the quantity takes: a tag, a value or `"#N"` (04 §7) |
| `fields` | a table |  | a compound quantity: `{ <field> = <its binding> }`, each field a quantity of its own, its rows' values set together (04 §8.4) |
<!-- /generated -->

**A row** is `{ tag, value, label, style }`:
- `value` is required: a scalar or an array (an energy pair), checked against the vocabulary's
  shape;
- `tag` names the point's folder: keep it short and unique;
- `label` is legend text, in **LaTeX** (`$e^-$`, `$\sqrt{s}$`), the one label language of every text
  a run TOML gives a page. Math goes in `$…$`; the rest is text, where a bare `_` or `^` is the
  character (`"PDF4LHC21_40"`). A label in ROOT's TLatex (`#sqrt{s}`, `p_{T}` with no `$`) is
  refused, with its LaTeX as the hint. `\_`, `\^` and `\#` also give the character; in TOML write
  them in single quotes, `'PDF4LHC21\_40'`, since in `"…"` a backslash starts a TOML escape. Left
  out, the label is the tag;
- `style` is its curves' look, `{ colour, line, width }`:
  - `colour` is `"#rrggbb"`, a ROOT name (`"kBlue+1"`) or a number (the yoda backend draws
    `#rrggbb` only);
  - `line` is `solid`, `dashed`, `dotted` or `dashdot`;
  - `width` is in points.

  A key left out, or `"default"`, is the style's. Curves with no colour take the palette in turn.
  A point keeps its look on every page, so a PDF is one colour throughout. With two curve axes, the
  later one's keys win.

A row too long for one line can be a table of its own, since TOML keeps an inline table on one line:
`[[quantities.pdf.points]]`, then `tag = …`, `value = …`, `label = …`, `style = { … }` on lines
of their own, once per point (03 §5 shows it).

### 8.1 Who consumes a quantity

This is decided at plan time, for every **active** quantity (varied, or fixed).

**With `to`**, each entry names a consumer and how it takes the value:

| Entry | Tool | Effect |
|---|---|---|
| `pythia = "<native key>"` (a table's name or a tool) | a tool with a card | that card line, in place of the folder's mapping |
| `fit = "<config key>"` | `exec` or `module` | a **config key** in the tool's extracted config (§9.2); dotted keys nest |
| `"<tag>/<analysis>" = "<option>"` | rivet (any tool with `analyses`) | an **analysis option** `<analysis>:<option>=<value>`, which must be declared in the analysis's `.info` (C9) |
| `"<tag>/seed" = true` | any | a **replica**: enters the generator's identity, so its seeds; renders nothing. Under `seed = <integer>` the value **is** the point's seed |
| `"<tag>" = true` | any | that tool, by its folder's own mapping or its config's quantity name |

An entry with a `/` or `true` makes the entries the **only** consumers (a target list). Entries that
are all `<tool> = "<key>"` only say how those tools write it, and every tool that consumes the
quantity anyway still does. A target not in this configuration's chain is skipped.

**Otherwise**, every tool in the chain (and every tool in `generate_cards`) is asked, in order:

1. the quantity's `to` has an entry for its table name or its tool → that native key;
2. else the master maps the quantity for its tool → the master's mapping;
3. else the quantity is in the tool's `consumes` list (exec and module tools) → its config.

**Zero consumers is an error** (C7): a value that changes a directory name and nothing else is what
v1 kept finding.
- More than one consumer is fine, and `--plan` prints the table.
- In an `@quantity` chain, a consumer among the configuration's alternatives is enough, and the
  selector quantity is consumed by the choice itself.

**Two sources for one native key** in one card (a quantity and a built-in, or two quantities) is an
error (C8). An override equal to the base card's value is written, but does not change the identity.

### 8.2 Replicas

```toml
[quantities.replica]
to     = { "pythia/seed" = true }
points = [{ tag = "s1", value = 1 }, { tag = "s2", value = 2 }, { tag = "s3", value = 3 }]
```

Replicas are statistically equivalent runs. The value enters the generator's identity, so each point
gets its own seed block. Seeds are never written by hand ([06 §8](06_Internals.md#8-identity-seeds-and-skip)).

### 8.3 Built-in quantities

`events` (the configuration's event count) and `threads` are provided by the runner. They reach a
tool only through the master (the table in §3), and need no consumer. Declared as quantities, they
can be varied or fixed: each point then has that event count or thread count in place of the
configuration's, and it reaches the tools as the built-in does.

```toml
[quantities.events]
points = [{ tag = "010M", value = 10_000_000 }, { tag = "025M", value = 25_000_000 },
          { tag = "050M", value = 50_000_000 }]
```

A list-valued `events` in a configuration (§5.6) is the other way: one configuration, and one
folder, per count.

### 8.4 Compound quantities and beams

Quantities that only ever move together are one quantity with **fields**: one row a point, a value
per field.

```toml
[quantities.collision]
fields = { energies = "energies", nucleus = { pythia = "PDF:nPDFBeamA" } }
fixed  = "p"
points = [
  { tag = "p",  energies = [130, 9], nucleus = 2212,       label = "$e$p" },
  { tag = "Au", energies = [100, 9], nucleus = 1000791970, label = "$e$Au" },
]
```

- A field bound by a vocabulary word (`energies = "energies"`) is that quantity. One bound by a
  table (`{ pythia = "PDF:nPDFBeamA" }`) is a quantity of its own with that `to`: the compound's name
  for the first field, `<name>_<field>` for the others.
- `vary = ["collision"]` varies the fields together; `fixed`, `plot_points`, `combine` and
  `exclude` name the compound quantity. The point's name is its row's tag, and the label and style
  are the row's.
- **Beams** are written so: in `[quantities.beams]`, rows with `a = { id, energy }` and `b = { … }`
  set the `beams` and `energies` of a point together, beam A and beam B.

```toml
[quantities.beams]
fixed  = "ep"
points = [
  { tag = "ep",   a = { id = 2212, energy = 275 }, b = { id = 11, energy = 18 } },
  { tag = "ep27", a = { id = 2212, energy = 920 }, b = { id = 11, energy = 27.5 } },
]
```

---

## 9. `[tools.<name>]`

### 9.1 Keys every tool table takes

```toml
[tools.rivet]                      # the table's name is the tool folder: rivet
input    = "pythia"                # what the pythia table writes
analyses = ["photo_eic"]           # a key of the rivet folder's [options]
output   = "jets.yoda"

[tools.rivet_hard]                 # a second rivet: its folder by `uses`
uses     = "rivet"
input    = "pythia_hard"
analyses = ["photo_eic"]
output   = "jets_hard.yoda"
```

<!-- generated: keys3 tools -->
| Key | Type | Default | Meaning |
|---|---|---|---|
| `uses` | a string |  | the tool folder, when it is not the table's name: a second table of one tool, `[tools.<name>] uses = "<folder>"` (05 §3; `hep tools` lists the folders) |
| `card` | a string or a list |  | native base card(s), read in order (root `configs/<project>/`). Tools with a card only. |
| `input` | a string or a list |  | what it reads: a producer's table name (`input = "pythia"`: what that tool writes), another tool's output by name, a pre product, (post) a product of every point, or a path. The first input is `{input}` |
| `output` | a string or a list |  | what it writes. Read in its own group, a FIFO; in a later group, a file: a product in `results/`, or with `keep = false` a scratch file in `logs/` (04 §6). An array is fan-out; one writer per output (C6) |
| `timeout` | a number, ≥ 0 |  | the tool fails when it runs longer |
| `stall_after` | a number, ≥ 0 |  | the tool fails when silent this long: no log line, status message or heartbeat (a prepare step waits at least 3600) |
| `status` | a string: `"standard"`, `"filters"`, `"none"` |  | `"standard"` (`$HEP_STATUS_FD`), `"filters"` (the folder's `filters.toml`), `"none"` |
| `filters` | a string |  | your own rules in place of the folder's, root `configs/<P>/`; implies `status = "filters"` |
| `executable` | a string |  | exec and module: bare → `build/<project>/<name>` (must be built); `path:<command>` → `PATH` |
| `arguments` | a list |  | exec and module: argv after the config; placeholders (04 §10). Not paths: the tool runs in the point's folder, so a script of yours is `{work}/modules/…` |
| `consumes` | a list (a string each) |  | exec and module: quantities written into the config |
| `config` | a table |  | exec and module: `[tools.<tag>.config]`, extracted to a file (04 §9.2) |
| `streamable` | true or false |  | may it read a FIFO? |
| `consumes_events` | true or false |  | is its event count checked against the producer's sidecar? |
| `settings` | a table |  | native card settings as written, `"HeavyIon:mode" = 1`, with no base card needed: over the base card, refused when a quantity sets the same key (one source per key, C8); a tool with no card refuses them |
| `cores` | an integer, ≥ 1 |  | how many cores it keeps busy, for `--plan`'s note and the crowded warning; an integrated program is estimated as the generator's threads and one more |
| `shards` | an integer, ≥ 1 | `1` | K > 1: K processes of this tool, each on a share of the events, merged into its `output` by the folder's merge tool (rivet, 05 §5.1). The chain is unchanged. |
| `keep` | true or false | `true` | `false`: what it writes for a later group is a scratch file of the point (`logs/`), not a product (`results/`) |
<!-- /generated -->

Every other key is **tool-specific**. It is checked against the tool folder's `[options]` (type and
`required`, 05 §4–15). An unknown key is an error that lists the keys the tool takes (C1), or names
the table it belongs in (`'threads' belongs in [run] (or a configuration)`); an old export key
(`pythia_cmnd = true`) is refused with the way on (§9.4). A tool table no configuration's chain,
`pre`, `post` or `generate_cards` names is reported by `hep check`. In your editor, the schema
(`run.v3.schema.json`) knows each standard tool's keys.

### 9.2 Exec tools

Any executable, as `uses = "exec"`. To make one a tool folder of its own, `hep tools new fit --from
exec` copies the folder into the work dir's `tools/fit/`
([06 §16](06_Internals.md#16-the-tool-folder-contract)), and the table is then `[tools.fit]` alone.

```toml
[tools.fit]
uses        = "exec"
executable  = "fit_peaks.py"                # build/<P>/fit_peaks.py (path:<command> for PATH; ./… from the work dir)
arguments   = ["{in:lambda.yoda}", "{res}/fit.json"]
input       = "lambda.yoda"
output      = "fit.json"
consumes    = ["energy"]                    # written under [quantities] in its config
filters     = "fit_filters.toml"

[tools.fit.config]                          # written verbatim to logs/…/<point>/config/fit.toml
model  = "gauss+poly2"
window = [1.09, 1.14]
```

The runner writes `logs/…/<point>/config/<name>.toml` when the table has a `config` or consumes a
quantity. It passes it as the **first argument** (the folder's argv is
`{exe} {config} {arguments}`). The file holds:

- the `[tools.<name>.config]` table, verbatim;
- consumed values:
  - a value mapped to a **config key** (`to = { fit = "window" }`) is set at that key (dotted keys
    nest: `"cuts.window"`);
  - a value consumed **by its quantity name** (`consumes`, or `to = { fit = true }`) goes under
    `[quantities]`.

The other tools' cards and configs are in the point's context file (§9.4), at `$HEP_CONTEXT`.

An exec tool is count-checked only if its table sets `consumes_events = true` and its folder names
how to read the count (the `exec` folder names none). A product it writes should go to
`{partial:output}`; the runner renames it after the checks pass.

### 9.3 Module tools

```toml
[tools.decay]
uses       = "module"
executable = "Decay.exe"                  # build/Decay/Decay.exe, from modules/Decay/Decay.cc
input      = "to_module.hepmc"
output     = "decay.root"

[tools.decay.config]
mass_tolerance = 0.15
```

A module tool works as an exec tool does, for a program built with `src/Module.hh`
([06 §21](06_Internals.md#21-modulehh)). It always gets a config, and its argv is
`{exe} {config} --input={input} --output={partial:output} --events={events}
--sidecar={input_sidecar} {arguments}`. Its count is checked from its report (`<output>.json`, key
`events`). **Every key of its config must be one the program reads:** a misspelt setting is refused
before the first event, with the nearest name, instead of running with its default.
`hep explain <Name>.exe` lists the settings a program reads (`<Name>.exe --describe`).

### 9.4 The context file: every tool's card and config

When a point starts, the runner writes **one context file** for it, `logs/…/<point>/context.toml`,
and removes it when the point ends. Every tool of the point finds it through `$HEP_CONTEXT` (set in
each tool's environment, never in your shell), or `{context}` in its arguments. It lists, by table
name:

```toml
[tools.pythia]
tool       = "pythia"
card       = "/…/cards/pythia.cmnd"            # base and point card in one file, seeds included
card_parts = ["/…/ep.cmnd", "/…/cards/pythia.point.cmnd"]

[tools.rivet]
tool        = "rivet"
analyses    = ["photo_eic:R=0.4"]               # what its folder's [context] gives
plugin_path = "/…/build/Rivet"

[tools.jets]
tool   = "module"
config = "/…/config/jets.toml"
```

**Which tools are in it:** the chain's, and the ones in `generate_cards`. A tool table that is defined
but not used gets no card. A program that runs other tools inside itself (an **integrated program**:
Pythia and Rivet in one process) names them, so their cards are rendered for it although they do not
run:

```toml
[cfgs.inproc]
chain          = ["jets", "yd2rt"]
generate_cards = ["pythia", "rivet"]          # not run: their cards and configs, in the context file
```

| Rule | |
|---|---|
| Where | `generate_cards` in `[run]` or a configuration (the nearer one wins), a list of tool tables |
| Rendered as in a chain | the same card a process of that tool would get for this point, **seeds included** |
| Consumed | the quantities such a tool consumes count as consumed (C7) |
| Products on demand | `"<name>:<product>"` (`"herwig:run"`, `"sherpa:results"`, `"madgraph:process"`) runs that tool's prepare step (cached) and puts the product's path in its table: `run = "…/point.run"`. A tool makes only the products its folder declares (`[context.products]`) |
| What each tool gives | `tool`; `card` and `card_parts` for a tool with a card; `config` for one with a config file; its folder's `[context] values` (Rivet's `analyses` and `plugin_path`); the products asked for |
| On the command line | `{context}` is the file's path; `{context:<name>.<key>}` one value of it (`{context:herwig.run}`) |
| In a module program | `job.card("pythia")`, `job.tool("rivet").list("analyses")`: by table name, else by the one tool of that kind ([06 §21](06_Internals.md#21-modulehh)) |
| Identity | the cards of every tool in it are part of the point's identity; so are the products asked for |

The program then owns what the chain would have done: σ over threads, the final σ to Rivet,
and catching at thread boundaries. There is no FIFO, so the runner checks its exit code and its
outputs.

**Before (C13):** a tool asked for one other tool at a time with `<tool>_<export> = true` keys
(`pythia_cmnd`, `rivet_analyses`, `herwig_run`), and got `[standard.<key>]` tables in its config.
Those keys are refused now; `hep migrate` turns them into `generate_cards` and `{std:<key>}` into
`{context:<tag>.<key>}`.

---

## 10. Placeholders

**In argv, cards and arguments.** `{name}` is replaced from the point's plan in:
- a folder's argv, env, cwd, card lines and footers;
- an exec or module tool's `arguments`.

The rules:
- `{{` and `}}` are literal braces.
- An argument that is exactly one placeholder whose value is a list is **spliced** into argv:
  `{inputs}` becomes several arguments, and an empty list becomes none.
- An unknown placeholder is an error with the nearest name.

| Placeholder | Is |
|---|---|
| `{work}` | the work dir (its root folder) |
| `{hep}` | Heimdall (`$HEP`): its apps are `{apps}/…` |
| `{exe}` | the tool's executable |
| `{out}`, `{res}` | the point's output and results directories |
| `{config}` | the extracted config file (exec, module), or empty |
| `{arguments}` | the table's `arguments`, expanded |
| `{input}` | the first input's path |
| `{inputs}` | every input's path (post: that product of every point, in point order) |
| `{named_inputs}` | post: `<point>=<path>` for every point |
| `{in:<name>}` | the path of the input named `<name>` |
| `{file:<name>}` | the path of a FIFO or scratch file of the point, by name (§6) |
| `{input_sidecar}` | the first input's producer sidecar, **only** when that producer ran in an earlier group (a file); empty in a FIFO chain |
| `{output}`, `{outputs}` | the first output's final path / every output's, comma-joined |
| `{partial:output}` | the first product's partial name (`jets.partial.yoda`), which the runner renames after the checks |
| `{output_name}` | the first output's file name |
| `{q:<quantity>}` | the point's value of an active quantity |
| `{threads}`, `{events}` | the configuration's |
| `{seed}` | the point's seed (filled in last: identities stay seed-free) |
| `{cards}` | the base cards, then the point card |
| `{card}` | the combined card (base + point card in one file) |
| `{analyses}` | rivet: `-a <analysis[:options]>` for each |
| `{prepared}`, `{prepare_card}` | the tool's prepare cache entry / the card its prepare step reads |
| `{context}`, `{context:<tag>.<key>}` | the point's context file / one value of it (§9.4) |
| `{points}` | pre and post: `points.json` |
| `{<option>}` | every key of the folder's `[options]`: its value, empty when unset; `kind = "flag"` → the flag or nothing |

`{repo}`, High-Energy's single root, is refused, naming `{work}` and `{hep}`; `hep migrate` rewrites
it (`{repo}/build/App_*` → `{apps}/App_*`, `{repo}/utils/` → `{hep}/src/`, any other
`{repo}` → `{work}`).

**In the run TOML itself**, `{var:name}` is a `[file.vars]` value (§3), replaced when the file is
read, everywhere, before any of these.

**In page texts**. These are the titles, `legend_header`, the axis labels, `[plot.data].legend`,
a figure's `labels`, the quantities' `labels` and the `.plot`'s own. They may cite the points:

| Placeholder | Is |
|---|---|
| `{cell}` | the page's `plot_points` values, joined |
| `{q:<quantity>}` | the label of the quantity's value at the point, swept or static |
| `{opt:NAME}`, `{opt:<analysis>:NAME}` | Rivet's: the analysis option at the point (the `.info`'s `(default X)` when not set) |

A page text's placeholder must have one value across the page's curves; a curve label's is its own
point's. A cited name the points don't have is refused at plan time, with the nearest name.

---

## 11. `[plot]`

The plot stage, and how to use it, is [03](03_Plots.md). A configuration whose run TOML has no
`[plot]` draws nothing.

<!-- generated: keys plot -->
| Key | Type | Default | Meaning |
|---|---|---|---|
| `backend` | a string or a list (a string each): `"root"`, `"yoda"`, `"mpl"`, `"both"`, or `"default"` | `"root"` | `"root"` (Paint), `"yoda"` (rivet-mkhtml; frozen), `"mpl"` (matplotlib, mkhtml's pages drawn in-process), `"both"` (root and yoda) or an array of them, from the same pages |
| `formats` | a list (a string each): `"pdf"`, `"png"`, `"svg"`, `"eps"`, or `"default"` | `["pdf"]` | `pdf`, `png`, `svg`, `eps`. mkhtml writes pdf and png always. The root backend writes `plots/root/index.html`: a section per `plot_points` cell, each page by its PNG or SVG, else an embedded PDF, linked to every format; add `png` for thumbnails a browser shows at once |
| `band` | a list (a string each) |  | curve axes drawn as an envelope: per value of the other curve axes, one curve, the band quantity's first value, with the min–max of all its values shaded around it in the curve's colour (the usual PDF or scale band). Its legend entry ends `(<q> envelope)`; its own statistical errors are not drawn. A name that is not a curve axis of the configuration (swept, not `plot_points`, not combined) is refused at plan time. The yoda backend draws the same envelope as mkhtml's error band |
| `objects` | a list (a string each), or `"default"` |  | matched against the option-free YODA path (`/photo_eic/d01-x01-y01`) or any variant's path. No object matching is an error. |
| `ratio` | true or false, or `"default"` or `"native"` | `false` | a ratio pad: each curve over the data, or over the first curve when there are no data |
| `y_gutter` | a number, ≥ 0, or `"default"` or `"native"` | `0.5` | the top of the y axis at (1 + g) × the largest drawn value (on a log axis, g of the decades shown); `0`: no headroom. `"native"`: no gutter, the tool's own range (a v2 file's [plot] says `"default"`) |
| `x_gutter` | a number, ≥ 0, or `"default"` or `"native"` |  | widens x by g of its span, symmetrically (in decades on a log axis). `"default"`: the range the bins give |
| `logy` | true or false, or `"default"` or `"native"` |  | log y (default: the .plot's) |
| `logx` | true or false, or `"default"` or `"native"` |  | log x (default: the .plot's) |
| `logz` | true or false, or `"default"` or `"native"` |  | a heat map's colour scale |
| `auto_range` | true or false, or `"default"` or `"native"` | `true` | trim x to the bins with content, in curves and data |
| `normalise` | a string or true or false: `"area"`, `false`, or `"default"` or `"native"` | `false` | `"area"`: every curve, and the data, scaled to unit area, Σ value × bin width over the bins drawn (after voiding and the data's alignment), so pages compare shapes. Both backends scale the same way. The y label stays the `.plot`'s: set `y_label` (e.g. `"$1/\sigma\,\mathrm{d}\sigma/\mathrm{d}E_T$"`) on the pages it applies to. A figure (04 §11.2) may set it for its own |
| `void_empty` | true or false, or `"default"` or `"native"` | `false` | blank a bin that is zero in **every** curve |
| `use_data` | true or false | `true` | `false`: the `[plot.data]` table stays in the file but is not drawn, and a `ratio` divides each curve by the page's first curve, the first value of its curve axis |
| `min_entries` | an integer, ≥ 0, or `"default"` or `"native"` | `0` | blank a bin that fewer raw entries went into, in **any** curve (read from the `/RAW` twin; objects without one are not voided this way) |
| `range_pad` | an integer, ≥ 0, or `"default"` or `"native"` | `0` | whole bins kept either side of the filled ones |
| `root_style` | a string, or `"default"` |  | a style file over base.toml (04 §12). Refused by the yoda backend alone. |
| `title` | a string, or `"default"` or `"native"` |  | the main title, centred above the frame. Every page; a figure (04 §11.2) overrides it for its own |
| `title_left` | a string, or `"default"` or `"native"` |  | small text just above the frame's top-left and top-right corners, inherited the same way |
| `title_right` | a string, or `"default"` or `"native"` |  | small text just above the frame's top-left and top-right corners, inherited the same way |
| `legend_header` | a string, or `"default"` or `"native"` |  | the legend's first line, inherited the same way. Children inherit every key their parent has and a key means the same at both levels |
| `data` | a table |  | 04 §11.1 |
| `style` | a table |  | 04 §12 |
| `figures` | a table |  | `[plot.figures.<figure>]`: a recipe for pages, with every page key of `[plot]` for its own (04 §11.2) |
<!-- /generated -->

**What `"native"` gives** (what the drawing tool does by itself; v2 wrote it as `"default"` in
`[plot]` itself):

| Key | `"native"` gives |
|---|---|
| `min_entries`, `range_pad` | 0: every bin drawn |
| `void_empty` | false: neither Paint nor mkhtml voids a bin by itself |
| `normalise` | false: neither tool scales a curve by itself |
| `auto_range` | off: the tool's own x range |
| `y_gutter`, `x_gutter` | no gutter: the tool's own range |
| `logx`, `logy`, `logz` | the analysis's `.plot` `LogX`/`LogY`/`LogZ` |
| `ratio` | the `.plot`'s `RatioPlot`, else a ratio pad when the page has reference data (mkhtml's rule) |
| `title`, `title_left`, `title_right`, `legend_header` | the `.plot`'s (`Title`, `LegendTitle`), else none |

`formats`, `objects`, `backend` and `root_style` take `"default"` only, which is their default: pdf
(mkhtml writes pdf and png anyway), every object, `"root"`, no style file. In a figure, `"default"`
keeps `[plot]`'s value, as if left out, and `"native"` is the drawing tool's own, whatever `[plot]`
says. `x_label` and `y_label`, which only a figure sets, keep the `.plot`'s labels when left out.

`[plot].legend` is no longer a key: it moved to the style, as `legend.position`, and the error says
so.

### 11.1 `[plot.data]`

<!-- generated: keys data -->
| Key | Type | Default | Meaning |
|---|---|---|---|
| `file` | a string |  | `rivet:<Analysis>`: Rivet's own reference file (`build/Rivet/`, then `rivet-config --datadir`, `.yoda` or `.yoda.gz`); otherwise a path under `datasets/` (not in git) |
| `legend` | a string | `"Data"` | the data's legend entry |
| `map` | a table |  | MC object name (`d01-x01-y01`) → reference path. **Explicit only**, never matched by name. A file without a map, or a map without a file, is an error. |
<!-- /generated -->

A file without a map, or a map without a file, is an error. The reference is drawn on the pages its
map names, **aligned** to the drawn binning: cut to its longest run of bins whose edges are all MC
edges, or dropped (with a warning) when none line up.

### 11.2 `[plot.figures.<figure>]`

A figure is a recipe for pages; its classes, each with an example, are
[03 §7](03_Plots.md#7-figures). These are its own keys:

<!-- generated: keys figure -->
| Key | Type | Default | Meaning |
|---|---|---|---|
| `class` | a string: `"defined"`, `"overlay"`, `"merged"`, `"compare"`, `"derived"`, `"scan"`, `"sheet"` | `"defined"` | how the pages are built. `defined`: an analysis object's own pages, `<cell>/<object>`, its curves the cell's points (and option variants). `overlay`: several objects of each point on one page, `<cell>/<name>`; a curve per object and point, labelled by `labels` (plus the point's, when the page has several); a ratio divides by the first curve. `merged`: the objects' pages, `<cell>/<name>/<object>`, with the points merged over the `over` axes: per value of the other axes, their YODAs merged by the combine folder's command (`rivet-merge -e`: statistics add, σ averaged), once per change of a member's YODA, into `logs/…/plots/merged/<name>/`. The run keeps its points apart; the figure alone merges them (`combine` merges them for the whole configuration). `sheet`: drawn pages laid out in a grid (`pages`, `columns`; below). `compare`: the objects' pages across configurations, `<run>/compare/<name>/<cell>/<object>` beside the configurations' own folders (in `logs/` and `results/`, a folder per backend). A curve per configuration and point (or combined group), labelled by the configuration (`labels`, else its `label`) and then the point's curve axes. The configurations must have the same page and curve axes (checked at plan time); the figure is drawn by the plot stage of each of them once all have complete points, and says what it waits for otherwise (`hep plot` draws it too). `derived`: a new object per point, `/FIGURES/<name>` (`/FIGURES:R=0.4/<name>` per analysis-option variant): `op = "ratio"`, `"difference"` or `"sum"` of its two objects (histograms made estimates first; the same binning, else an error naming both), or `"projection-x"`/`"projection-y"` of its one 2D object (summed over the other axis: a histogram's weights, an estimate's values × widths, as a Scatter2D whose x ranges are the bins). It is appended to a copy of each point's YODA (`logs/…/plots/derived/`, remade when the product or the figures change, by `framework/plot/figures/derive.py`: YODA's Python, so `load_hep`), and is then an object like any: its pages `<cell>/<name>` (labels from its first object's `.plot`; set `y_label`), an overlay or a merged or compare figure may name it (`"r15"`). `scan`: one number per point against a swept quantity: `x` a curve axis whose values are numbers, `y` = `sigma` (the point's `/_XSEC`), `entries` (its events, or its object's raw entries), or `integral`, `mean`, `bin:N` of its one object. A page per cell, `<cell>/<name>`, a curve per value of the other curve axes: a Scatter2D, a point per x value with an x range halfway to its neighbours centred on it (so every backend can draw it as a bin; it is drawn as markers, `type = "Scatter2D"`). Axis titles: the quantity's name and the y read, until set. A quantity of names (PDF sets) cannot be an x yet |
| `type` | a string: `"Hist1D"`, `"Scatter2D"`, `"HeatMap"` |  | what is drawn: `Hist1D`, steps per curve; `Scatter2D`, a marker per bin at its centre with its y error, in the curve's colour (`data.marker`, `data.marker_size` of the style), as Paint draws data; the legend shows the marker. The page TOML says `markers = true`; mkhtml and mpl draw the curves as they draw points (`ConnectBins=0`, with their x bars). `HeatMap`: a 2D object (a YODA `Histo2D` or `Estimate2D`), the default for one: a page per point of the cell, `<cell>/<object>/<point>`, coloured by value with its scale on the right (labels from the `.plot`, `ZLabel` and `LogZ` too; no ratio, data or voiding). Paint draws heat maps; mkhtml and mpl draw the 1D pages only, and the plot stage says so. A 1D object cannot be a HeatMap, a 2D object neither a Hist1D nor a Scatter2D, nor in an overlay |
| `name` | a string |  | an overlay's page file stem, a merged figure's folder. A defined figure takes none: its pages are the objects' own |
| `objects` | a list (a string each) |  | matched against the short name (`d04-x01-y01`), the option-free path or a variant's path. A glob matching no object of the points is an error, at the plot stage |
| `op` | a string: `"ratio"`, `"difference"`, `"sum"`, `"projection-x"`, `"projection-y"` |  | a derived figure's: `ratio`, `difference`, `sum` (two objects), `projection-x`, `projection-y` (one) |
| `x` | a string |  | a scan figure's quantity (a numeric curve axis) and number (`sigma`, `entries`, `integral`, `mean`, `bin:N`); `sigma` and `entries` need no object |
| `y` | a string |  | a scan figure's quantity (a numeric curve axis) and number (`sigma`, `entries`, `integral`, `mean`, `bin:N`); `sigma` and `entries` need no object |
| `pages` | a list (a string each) |  | a sheet's: the drawn pages whose names (`18x275/d02-x01-y01`, `*/eta_algorithms`) the globs match, in the globs' order, tiled `columns` wide into `plots/<backend>/sheets/<name>.pdf` and `.png`, each pad the page as it was drawn alone (pdflatex places the PDFs as vectors, a PNG where a page has no PDF; the `.png` is that PDF rendered by pdftoppm). For Paint's and mpl's pages. A sheet takes no page keys (its pages' figures set those); a glob naming no page fails the sheet |
| `columns` | an integer, ≥ 1 |  | a sheet's: the drawn pages whose names (`18x275/d02-x01-y01`, `*/eta_algorithms`) the globs match, in the globs' order, tiled `columns` wide into `plots/<backend>/sheets/<name>.pdf` and `.png`, each pad the page as it was drawn alone (pdflatex places the PDFs as vectors, a PNG where a page has no PDF; the `.png` is that PDF rendered by pdftoppm). For Paint's and mpl's pages. A sheet takes no page keys (its pages' figures set those); a glob naming no page fails the sheet |
| `over` | a list (a string each) |  | a merged figure's: curve axes of the configuration (swept, not `plot_points`, not combined), checked at plan time; it may not also `band` them |
| `configurations` | a list (a string each) |  | a compare figure's, two or more, in curve order; one at least of this file. `"<Project>/<config>:<cfg>"` names a configuration of another run TOML: its points (as its last run left them) are curves beside this run's, labelled `<its run> <its label>` by default and by its own quantities; its page axes must have this run's tags. The pages are this run's (`<run>/compare/<name>/`), drawn by this run's plot stage or `hep plot` |
| `labels` | a list (a string each) |  | an overlay's: one legend label per object; a compare figure's: one per configuration (default: each configuration's `label`) |
| `x_label` | a string, or `"default"` |  | the axis titles (LaTeX) |
| `y_label` | a string, or `"default"` |  | the axis titles (LaTeX) |
| `style` | a table |  | a style layer for these pages (04 §12) |
| *every page key of `[plot]`* | as there | `[plot]`'s | `band`, `ratio`, `y_gutter`, `x_gutter`, `logy`, `logx`, `logz`, `auto_range`, `normalise`, `void_empty`, `use_data`, `min_entries`, `range_pad`, `title`, `title_left`, `title_right`, `legend_header`: the figure's value, for its pages only |
<!-- /generated -->

When each rule is checked:

| When | What is checked |
|---|---|
| when the file is read | each class's keys: a scan's `x` and `y`, a derived figure's `op` and its object count, a merged figure's `over`, a sheet's `pages`; the keys a class may not take (`labels` on a defined figure, `pages` on any but a sheet) |
| at plan time | the axes a band, `over` or a scan's `x` names, the configurations a compare figure names |
| at the plot stage | that its globs match objects, and that two defined figures do not claim one object |

`[plot.overlay.<name>]` and `[plot.object."<glob>"]` are figures now. They are refused with the
figure to write, and `hep migrate` rewrites them:
- an overlay becomes `[plot.figures.<name>]` with `class = "overlay"`;
- an object table becomes `[plot.figures.<glob, as a name>]` with `objects = ["<glob>"]`;
- in a figure, a style key written bare (`ratio.range = …`) becomes `style.ratio.range`.

Object tables that matched the same object (they were applied in file order) become figures that
overlap, which the plot stage refuses: merge them by hand.

---

## 12. The style

The look of the ROOT pages is TOML. **`src/Apps/Paint/base.toml`** holds every key with its
default (rivet-mkhtml's look); edit it to change every page. Over it, key by key:

1. the machine root's `style.toml`: every work dir's on this machine;
2. the work dir's `style.toml`: its studies' house style;
3. `[plot].root_style`: a style file (a bare name under `configs/<project>/`, `.toml` optional);
   `hep overlay FILE… --style FILE` for files;
4. `[plot.style]`;
5. a figure's `style` (`[plot.figures.<figure>]`), for its pages.

**What a layer may hold.** Each layer names **only what it changes**, in base.toml's tables, and is
checked:
- a key base.toml does not have is an error, with the nearest spelling;
- so is a value of another kind: a number for a number, a pair of numbers for a pair, a list for the
  palette;
- the runner checks at plan time, and Paint checks again.

**What a page holds.** A page's document holds only what the layers changed; `$HEP_APPS/Paint.exe
PAGE.toml --dump-style` prints the whole merged style. Sizes are **points** (1/72 in) of the page,
unless said otherwise.

<!-- generated: style -->
| Key | Default | Means |
|---|---|---|
| `page.size` | `[4.67, 4.21]` | inches: the PDF's page; the PNG is size × dpi pixels |
| `page.dpi` | `300` | PNG resolution: 300 → 1400 × 1264 pixels |
| `page.font` | `"serif"` | serif \| sans \| mono (ROOT's Times, Helvetica, Courier) |
| `page.margins.left` | `0.16` | fractions of the page, around the axes |
| `page.margins.right` | `0.032` | fractions of the page, around the axes |
| `page.margins.top` | `0.066` | fractions of the page, around the axes |
| `page.margins.bottom` | `0.11` | fractions of the page, around the axes |
| `text.title` | `10.0` | axis titles |
| `text.labels` | `8.0` | tick labels |
| `text.legend` | `9.0` | legend entries (the yoda backend follows it) |
| `text.header` | `9.0` | the legend's first line: legend_header |
| `text.page_title` | `12.0` | title, centred above the frame |
| `text.corner` | `9.0` | title_left and title_right, just above the frame's corners |
| `curves.palette` | `["#EE3311", "#3366FF", "#109618", "#FF9900", "#990099"]` | #rrggbb, ROOT names (kBlue+1) or numbers |
| `curves.width` | `1.0` | points: the steps and their error bars |
| `curves.errors` | `"bars"` | bars (at the bin centres) \| band \| none |
| `data.colour` | `"kBlack"` | the reference data |
| `data.marker` | `20` | ROOT's marker style |
| `data.marker_size` | `2.0` | points |
| `data.x_bars` | `true` | the bin width as a horizontal bar |
| `axes.tick_length` | `6.0` | points; minor ticks are half as long |
| `axes.ticks_all_sides` | `true` | ticks on the top and right edges too |
| `axes.titles_at_ends` | `true` | the x title at the right end, the y title at the top; false centres them |
| `axes.title_offset` | `[1.0, 1.55]` | x, y: ROOT's title offsets (larger is further from the axis) |
| `axes.label_offset` | `2.5` | points between an axis and its tick labels |
| `legend.position` | `"top-right"` | top-right \| top-left \| bottom-right \| bottom-left, or [x, y]: its top-right corner in fractions of the frame (then right-aligned) |
| `legend.inset` | `[5.0, 5.0]` | points from the frame's corner (x, y), for a named position |
| `legend.spacing` | `1.2` | line pitch, × the legend's text size |
| `legend.symbol` | `16.0` | points: the width of the "+" beside each entry |
| `legend.gap` | `5.0` | points between the "+" and its text |
| `ratio.heights` | `[2.0, 1.0]` | the main pad to the ratio pad (mkhtml's 6:3) |
| `ratio.range` | `[0.5, 1.5]` | always shown; widened to the ratios drawn … |
| `ratio.limits` | `[0.0, 3.0]` | … but never past these |
| `ratio.divisions` | `512` | ROOT's axis divisions: at most 12 labelled (0.1 on ~0.4–1.5), 5 minor each |
| `ratio.decimals` | `true` | labels 1.0, 1.2, … rather than 1, 1.2, … |
<!-- /generated -->

**What the other backends honour.** mkhtml and mpl draw with mkhtml's own look. They honour:
- a `legend.position` corner (or `best`: Paint takes the corner with the fewest drawn points under
  the legend, and matplotlib chooses its own);
- `text.legend` and `text.header`;
- `ratio.divisions`;
- `ratio.range` with `ratio.limits` (each page's window by Paint's rule, so both show the same
  window).

**What they refuse.** Alone, they refuse `root_style` and every other style key. Beside the root
backend those are Paint's to honour, and are allowed, but a legend at `[x, y]` is still refused,
because the two page sets would disagree about it. A `best` legend, like any other, is placed within
the y range drawn, so give it headroom with a numeric `y_gutter`.

---

## 13. Validation rules

All of these are checked at plan time. Every error names **where** (the file and key) and gives a
**hint** (what to do), and a misspelt name gets the nearest spelling. `hep run` exits 2 on any of
them, before anything runs.

| # | Rule | Example message |
|---|---|---|
| **C1** | An unknown section or key is an error; a tool-specific key is checked against the tool folder's `[options]` (type, `required`). | `unknown key 'min_entry'` · `did you mean 'min_entries'?` |
| **C2** | `[run].run`, and a configuration named on the command line, must name a `[cfgs.<name>]`. | `no configuration 'energy-pdf'` |
| **C3** | Every `vary` entry names a declared quantity; entangled quantities have equal point counts; no quantity is varied twice. | `entangled quantities need equal value counts` · `pdf: 4, alphas: 3` |
| **C4** | `plot_points` names only quantities varied in this configuration. | `plot_points names 'mpi', which is not swept here` |
| **C5** | Every `chain`/`pre`/`post` entry is a `[tools.<name>]` table; groups nest one level; an `@q` entry's values are tool tables. | `'pythya' is not a [tools.<tag>] table` · `did you mean 'pythia'?` |
| **C6** | Connections (§6): a FIFO within one group only, one reader per FIFO, a writer for every FIFO, no FIFO into a non-streamable tool; every input made by someone or already on disk; one writer per output. | `'delphes' cannot read a FIFO` · `put it in a later group, so it reads a file` |
| **C7** | Every active quantity has at least one consumer in the chain (in an `@q` chain: among the alternatives). | `[quantities.lepton] is set but no tool in this chain consumes it` |
| **C8** | One source per native key in one card. | `'PDF:pSet' is set by both [quantities.pdf] = … and …` |
| **C9** | A Rivet analysis has a `.info` (our plugins in `build/Rivet/`, or Rivet's), and every option it is given is declared there. | `'photo_eic' does not declare the option RADIUS` · `declared: ETMIN, ETMIN2, R` |
| **C10** | Providers: a PDF set named by a checked mapping is installed; base configs exist; executables are built; files a tool folder needs (`[checks] files`, e.g. Herwig's repository) exist. | `the PDF set 'CT14lo' is not installed` · `lhapdf install CT14lo` |
| **C11** | Point directory names are unique. | `these points would share a directory: …` |
| **C12** | Paths: no `../`; a missing file is reported under its convention root. | `'../cards/x.cmnd' climbs out of its root` |
| **C13** | `generate_cards` names tool tables, and a `"<tag>:<product>"` a product that tool's folder makes (§9.4); an old export key is refused with the way on. | `pythia makes no product 'run'` · `'pythia_cmnd' is retired: …` |
| **C14** | `combine` names quantities varied here as axes of their own, none of them in `plot_points`. | `combine names 'pdf', which is not swept here as an axis of its own` · `'replica' is both combined and a page axis (plot_points)` |

The plot checks follow the same shape:
- an unknown backend, format, gutter value, `[plot.data]` key, figure key or style key;
- a data file without a map;
- a style key a backend cannot honour;
- a band or `over` that is not a curve axis;
- a figure's class rules (§11.2);
- a TLatex label;
- a page text citing a placeholder the points don't have.

---

## 14. Files the runner writes

**Per point**, in `logs/…/<point>/` (its working folder) and, the last three, `records/…/<point>/`:

| File | Holds |
|---|---|
| `cards/<tag>.point.<ext>` | the overrides (append style) |
| `cards/<tag>.<ext>` | base + point card in one file (what an export hands out); for render style, the whole card |
| `cards/<tag>.json` | each key's value and where it came from (a folder with `[card] merge`: pythia) |
| `cards/<tag>.prepare.<ext>` | the card a prepare step reads, when the tool's `render.py` makes one |
| `config/<tag>.toml` | an exec or module tool's extracted config |
| `context.toml` | the point's context file (§9.4): every tool's card and config; there only while the point runs |
| `logs/<tag>.log`, `logs/<tag>.prepare.log`, `logs/prelim.log` | a failed tool's last 200 lines of stdout and stderr (a failed `[run] commands` command's output); with `--logs`, every tool's whole output |
| `provenance.json` | `point`, `run`, `project`, `configuration`, `config_file`, `sets`; `values` (each active quantity's index, tag and value); `identity`, `seed`, `threads`, `events`; per tool `tag`, `tool`, `exe`, `exe_sha256`, `version`, `argv`, `ran`, `card`, `card_sha256`, `config`, `result` (exit, seconds, note); `host`, `platform`, `user`, `git` (`revision`, `dirty`), `started`, `finished` |
| `identity.json` | the parts the identity hashes (each tool's card lines, argv, binaries, options; threads, events, groups, prelim, the seed rule), written when the point completes, for `--why` |
| `.complete` | the point's identity, written **last**; its absence means the point is not done |
| `.lock` (in `logs/`) | held while a session runs the point: `{host, pid, since}`, free when that process ends |

**Per configuration**, in `records/…/<cfg>/` (`points.json`, `cluster/`) and `logs/…/<cfg>/` (the rest):

| File | Holds |
|---|---|
| `points.json` | `run`, `project`, `configuration`, `config_file`, `plot_points`, and per point: `name`, `index`, `values` (tag, label, value, swept), `page`, `products` (name → path), `results`, `output`, `identity`, `seed`, `complete`. Every point, even under `--points` |
| `status.jsonl` | only with `--journal`: the run's events as `{"v", "point", "tool", "t", "k", …}`: every status message, plus the runner's own `run` (started, finished with a `verdict`), `point` (started, done / failed / stopped with `cause` and `msg`) and `exit` (`code`, `seconds`) records |
| `plots/[<cell>/][<figure>/]<object>.toml` | each page's document, as Paint reads it, and `<page>.toml.ranges.json` beside it for the other backends |
| `plots/merged.sha256` | what the merged sweep file was built from |
| `plots/derived/`, `plots/merged/<figure>/`, `plots/scan/<figure>/` | the figures' own YODAs and their stamps (03 §7) |
| `cluster/<stamp>/` | `hep cluster`'s submissions: the scripts, `points.txt`, `jobs.toml`, the jobs' logs |

**Beside products:**
- an event producer's **sidecar** `<first output>.json`: App_Pythia's, or `{"written": N, "source":
  "requested"}`, written by the runner for generators that always make what they are asked for;
- a module program's **report** `<output>.json` (`events`, `sum_w`, `sigma_pb`, …), which travels
  with its product when it is renamed.

**Caches:**
- **prepare caches:** `.cache/<P>/<tool>/<key>/`, with a `.prepared` stamp once the step succeeded
  and left its marker;
- **card checks:** `.cache/<P>/checks/`;
- **reference data converted for Paint:** `.cache/<P>/datasets/<name>.root`.

A work dir made before the split has `output/`: `hep migrate --layout` moves it (a dry run first).

Where everything goes, as a tree, is [06 §14](06_Internals.md#14-where-files-go).

---

## 15. A deck's recipe: `deck.toml`

A deck is written in `decks/<deck>/` and built into `reports/<deck>/` by `hep deck <deck>` (05; a deck
still written in `reports/<deck>/` is read there, and `hep migrate --layout` moves its sources). Its
`deck.toml` says where its
plots come from; `framework/schema/deck.toml` holds every key, as below. A recipe has `[deck]` and
`[blocks.<name>]` tables, and nothing else; with no block, the deck takes the folder's own PDF and PNG
files (folder mode, grouped by `[deck].group`).

**`[deck]`:**

<!-- generated: keys deck -->
| Key | Type | Default | Meaning |
|---|---|---|---|
| `size` | a string: `"full"`, `"half"`, `"a4"`, `"square"` | `"full"` | a composite's size: full, a 16:9 slide's content area under its title; half, one of its two columns; a4, A4 landscape; square |
| `labels` | true or false | `true` | each panel's label above it, on the composite figures |
| `titles` | true or false | `false` | a block's title above its grid, on the composite figures (a slide has its own title) |
| `columns` | an integer, ≥ 1 |  | a composite's columns (default: the count that shows its panels largest) |
| `targets` | a list (a string each): `"pdf"`, `"pptx"`, `"html"`, `"overleaf"`, `"viewer"` | `["pdf", "pptx", "html", "overleaf", "viewer"]` | what a build makes: deck.pdf (Beamer), deck.pptx, deck.html (dzslides, offline), overleaf.zip, index.html (the viewer) |
| `backend` | a string or a list (a string each): `"root"`, `"mpl"`, `"yoda"` | `"root"` | whose drawn pages a block takes, plots/<backend>/ of each result folder; a list in order of preference (per folder, the first that drew the page) |
| `dpi` | an integer, ≥ 50 | `200` | the resolution a composite's PNG is rendered at, from its PDF |
| `group` | a string | `"^(?P<block>.+)_(?P<panel>[^_]+)$"` | folder mode's regex over file stems: its group `block` names the block, `panel` the panel (natural order) |
<!-- /generated -->

**`[blocks.<name>]`:** a block per page its `pages` name, `<name>-<page>` (`validation-d01`), with a panel
per result folder its `folders` name, then its `extra` file.

<!-- generated: keys block -->
| Key | Type | Default | Meaning |
|---|---|---|---|
| `from` | a string | **required** | the run whose result folders the block takes: "<Project>/<run>", results/<Project>/<run>/ |
| `folders` | a list (a string each) | **required** | its result folders (`01_PDFs_010M`), names in their order, globs in natural order: a panel each |
| `pages` | a list (a string each) | **required** | globs of page names in each folder's plots/<backend>/ (`d01-x01-y01`, `18x275/d0*`): a block each, named <block>-<page> |
| `backend` | a string or a list (a string each): `"root"`, `"mpl"`, `"yoda"` |  | as [deck].backend, for this block |
| `label` | a string: `"events"`, `"folder"` | `"events"` | a panel's label: events, the events its folder was run with (its provenance, else the count its name ends in, `_010M`; else what its YODA's /RAW/_EVTCOUNT counted), as 10M; folder, its folder's name without the serial |
| `extra` | a string |  | one more panel, a file of the deck's: a path pattern with {block}, {page} and {short} (`extras/validation_{short}_AB.png`) |
| `columns` | an integer, ≥ 1 |  | as [deck].columns, for this block |
| `size` | a string: `"full"`, `"half"`, `"a4"`, `"square"` |  | as [deck].size, for this block |
| `labels` | true or false |  | as [deck].labels, for this block |
| `titles` | true or false |  | as [deck].titles, for this block |
| `title` | a string |  | its composites' title, a pattern with {block}, {page} and {short} (`ZEUS {short} · PDFs`; default: the block's name and the page's, `validation d01`) |
<!-- /generated -->

No run TOML is read: a block takes its result folders as they are on disk (`results/<Project>/<run>/`),
whichever config file made them. A page a folder lacks is refused, naming the backend that drew it there,
if one did.

---

## 16. `[cluster]`: running on Slurm

`hep cluster` ([02 §7.5](02_User_Guide.md#75-on-a-slurm-cluster), 05 §1.9) submits a configuration as
Slurm jobs with these options. They come in layers, lowest first:
1. the machine root's `machine.toml` `[cluster]`: the machine's, for every work dir on it (account,
   partition, setup lines);
2. the work dir's `hep.toml` `[cluster]`: this work dir's;
3. the run TOML's `[cluster]`, into which an import's merges key by key, as `[plot]`;
4. a configuration's `cluster` table, `[cfgs.<name>.cluster]`;
5. `--set cluster.<key>=…`, for one submission.

`[cluster.pre]` and `[cluster.finish]` take the resource keys (`time`, `partition`, `account`, `qos`,
`constraint`, `gres`, `memory`, `cpus`, `sbatch`) for those jobs only. Nothing here enters an
identity or a seed: changing it reruns nothing. `time` is required in one of the layers.

<!-- generated: keys cluster -->
| Key | Type | Default | Meaning |
|---|---|---|---|
| `scheduler` | a string: `"slurm"` | `"slurm"` | the batch system `hep cluster` submits to: `"slurm"` (`sbatch`, `squeue`, `sacct`, `scancel`), the only one so far |
| `time` | a string |  | each job's wall-time limit, as `sbatch --time` takes it (`"02:00:00"`, `"1-00:00:00"`): one point's, for the points; **required** in one of the layers, because a site's default limit is a surprise `TIMEOUT` |
| `partition` | a string |  | `sbatch --partition`; unset: the site's default |
| `account` | a string |  | `sbatch --account`; unset: the user's default |
| `qos` | a string |  | `sbatch --qos` |
| `constraint` | a string |  | `sbatch --constraint`, the nodes' features (`"avx2"`) |
| `gres` | a string |  | `sbatch --gres` (`"gpu:1"`) |
| `memory` | a string |  | `sbatch --mem` per job (`"8G"`); unset: the partition's default |
| `cpus` | an integer, ≥ 0 | `0` | `sbatch --cpus-per-task`; `0`: the costliest point's cores, as `--plan` counts them (its generator's `threads`, a sharded tool's shards, an integrated program's threads and one more) |
| `max_running` | an integer, ≥ 0 | `0` | the points array's throttle, `--array=1-N%K`; `0`: as many as the scheduler gives. `parallelism` is not used: each job is one point |
| `mail` | a string |  | `sbatch --mail-user`, with `--mail-type=END,FAIL` |
| `setup` | a list (a string each) | `[]` | shell lines each job runs first, before it sources Heimdall's `setup.sh` (`"module load gcc/13"`): what the nodes need that the login shell had |
| `sbatch` | a list (a string each) | `[]` | any other `sbatch` options, each as written (`"--exclusive"`, `"--export=NONE"`, `"--reservation=r"`), after the ones the keys above give |
| `pre` | a table |  | the resource keys (`time`, `partition`, `account`, `qos`, `constraint`, `gres`, `memory`, `cpus`, `sbatch`) for the pre job only, over the others |
| `finish` | a table |  | the resource keys for the finish job only (the combined groups, the post tools and the plots), over the others; its `cpus` default to 1 |
<!-- /generated -->

---

## 17. The v2 form

A file is **v3** when it has `[file]` (unless it says `schema = 2`), `[cfgs]`, or a `[run]` with a
`chain`; any other file is read as **v2**, for one release. `[file] schema = 2` keeps a file v2
while you migrate. Both forms are the same run: the same points, folders and identities.

`hep migrate --v3` shows the rewrite of a v2 file as a diff, and `--apply` writes it, comments kept.
Each v2 name is refused in a v3 file, naming its v3 name, and `hep explain` answers either
(`hep explain run.event_count`, `hep explain events`).

| v2 | v3 |
|---|---|
| `[config]` | `[file]` |
| `[run]`'s `configuration` | `[run]`'s `run` |
| `event_count` | `events`; a list in a configuration is one configuration per count (§5.6) |
| `tools` (a configuration's chain) | `chain`; `[run]`'s is every configuration's |
| `sweeps` | `vary` |
| `seed_type`, `manual_seed` | `seed = "identity"`, `"random"` or an integer |
| `[run.cfgs.<cfg>]` (the `cfgs` table of `[run]`) | `[cfgs.<name>]` |
| a configuration's `label` | `folder` |
| `[static]`, a configuration's `static` | each quantity's `fixed`; a configuration's `fixed = { q = "tag" }` (§7) |
| `[prelim]`'s `fifo` and `files`, a configuration's `prelim` | inferred from the chain (§6); `keep = false` on a scratch file's producer |
| `[prelim]`'s `commands` | `[run]`'s `commands` |
| a tool table's `tool` | the table's name; `uses` for any other name |
| `baseconfig` | `card` |
| `output_file` | `output` |
| `input = "<file>"` | `input = "<producer>"` when one tool writes it; a file's name still works |
| a quantity's `values`, `tags`, `labels`, `styles` | `points = [{ tag, value, label, style }]` (`values` alone still works) |
| a quantity's `key` and `target` | `to` (§8.1) |
| quantities always swept together | a compound quantity with `fields` (§8.4) |
| `beams` and `energies` side by side | `[quantities.beams]` rows with `a = { id, energy }` and `b = { … }` |
| `"default"` in `[plot]` itself: the tool's own | `"native"`; `"default"` is always the layer below |
| a serial, bumped by hand | optional: the runner numbers the folder when none is set; a set one refuses to overwrite (§2) |
| an imported tool table, replaced whole | merged key by key (§3) |
| `--set run.event_count=…`, `only = ["run.default"]` | a file's own names: `--set run.events=…`, `only = ["cfgs.default"]` |
