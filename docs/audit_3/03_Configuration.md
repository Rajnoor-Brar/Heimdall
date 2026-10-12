# 03 — Configuration: the run TOML

A run TOML has eight top-level tables (`framework/schema/run.toml:27`; any other is refused with a
did-you-mean, `config.py:623-626`):

| Table | Holds |
|---|---|
| `[config]` | how the file is read: `import`, `drop`, `vars`, `meta`, `master` |
| `[run]` | identity (`project`, `name`, `serial`) and the defaults every configuration starts from |
| `[run.cfgs.<cfg>]` | one recipe: `sweeps`, `tools`, `event_count`, `static`, `prelim`, `cluster`, … |
| `[prelim]` | interfaces made before tools start: `fifo`, `files`, `commands` |
| `[static]` | fixed values of quantities that are not swept |
| `[quantities.<q>]` | a parameter: `values`, `tags`, `labels`, `styles`, `key`, `target`, `exclude`, … |
| `[tools.<tag>]` | one process: `tool`, `baseconfig`, `input`, `output_file`, `settings`, … |
| `[plot]` (+ `data`, `style`, `figures`) and `[cluster]` | the pages, and Slurm |

Two more layers live outside the file: the quantity vocabulary
(`framework/schema/quantities.toml`), and each tool's mapping
(`framework/tools/<tool>/quantities.toml`).

The loader is strict and helpful within a table:
- unknown keys get the nearest name;
- old forms are refused with the form to write and a pointer to `hep migrate`;
- `hep check` plans everything.

The problems are **between** tables. One concern is written in several, and the loader rarely says
so.

---

## 1. One concern, many tables

### a. A quantity — U35 (18), U36 (40)

What one parameter needs, from `tests/fixtures/work/configs/Demo/jets.toml`:

```toml
[run.cfgs.mpi]                                   # whether it varies   (l.51-56)
sweeps = ["pt0ref"]
static = { energies = "18x275" }                 # another quantity's fixed value, here

[static]                                         # its fixed value, by tag   (l.121)
pt0ref = "pt32"

[quantities.pt0ref]                              # its values, names and binding   (l.189-194)
key    = { pythia = "MultipartonInteractions:pT0Ref" }
values = [3.0, 3.2, 3.4]
tags   = ["pt30", "pt32", "pt34"]
labels = ['$p_{T0}^{\mathrm{ref}}$ = 3.0 GeV', '$p_{T0}^{\mathrm{ref}}$ = 3.2 GeV', '$p_{T0}^{\mathrm{ref}}$ = 3.4 GeV']
```

- **Values, tags, labels and styles are parallel arrays, aligned by position.** One more value means
  editing four lists in step. `exclude` counts positions from 1.
- **The fixed value is a tag string,** written in `[static]` far from the tag it must match.
- **An entangled sweep aligns positions across tables.** A user's electron–ion scan varies the
  nucleus, the beam energies and the nuclear-PDF switch together:
  `sweeps = [["ions", "energies", "nuclear"]]`. That is six values in each of three tables, matched
  only by position. A seventh nucleus is three edits that must agree.
- **A declared quantity that is neither swept nor static does nothing, silently** (04 §7: "inactive …
  renders nothing, and the base card's value stands"). A user who forgets `[static]` gets the card's
  value, a valid run, and wrong physics. **U36 is the most dangerous finding of this chapter.**

### b. A tool — U37 (14)

A chain of three tools is written in three places: the chain (`[run]` or each configuration),
the tool tables, and the interfaces in `[prelim]`. The FIFO between Pythia and Rivet is named three
times:

```toml
[run.cfgs.single]
tools = [["pythia", "rivet"], "yd2rt"]     # the chain (jets.toml repeats it in 11 configurations)

[prelim]
fifo = ["events.hepmc"]                    # the interface

[tools.pythia]
tool        = "pythia"                     # the table's name, again
output_file = "events.hepmc"               # … and the producer's end

[tools.rivet]
tool  = "rivet"
input = "events.hepmc"                     # … and the consumer's end
```

- **A configuration that doesn't use the file-wide FIFO must clear it** (`prelim = {}`, jets.toml:98),
  or it fails "every FIFO needs a writer".
- **Writing to a file instead needs a second Pythia table** that differs in `output_file` only
  (`[tools.pythia_file]`, jets.toml:149-152), plus a per-configuration `prelim = { files = [...] }`
  (:105).
- **`shards = 10` on Rivet silently rewrites `prelim` and the chain** (`tools.py:522-590`).

### c. Events and parallelism — U38 (18)

Eight places:
- `[run]` or a configuration: `event_count`, `threads`, `parallelism`;
- a quantity named `events` or `threads`, which replaces them;
- `[tools.X].shards` and `cores`;
- `[cluster].cpus` and `max_running` (where `parallelism` is ignored);
- a module's own `rivet_threads`;
- the base card's `Main:numberOfEvents` and `Parallelism:numThreads`, ignored with only a note.

Users reason across them in comments (jets.toml:25: `threads = 12 # Pythia's; with rivet's 10 shards
that fills the 24 hardware threads`). Only Pythia maps `threads`, yet it is part of every point's
identity. And `threads = 0` resolves to the planning machine's core count, so an identity can change
by machine.

**Repetition follows.** The user's validation file has seven configurations that differ only in
`event_count` and `label`:

```toml
[run.cfgs.default01]
extends = "default"
label = "PDFs_010M"
event_count = 10_000_000

[run.cfgs.default0]
extends = "default"
label = "PDFs_025M"
event_count = 25_000_000
# … default1, default2, default3, default4 …
```

A swept `events` quantity exists (V56), but nobody found it. Also, the counts belong in separate
folders, which a sweep would not give (U43).

### d. Seeds — U39 (18)

Five places:
- `seed_type` and `manual_seed` (in `[run]` or a configuration);
- a quantity with `target = "pythia/seed"`, whose meaning depends on `seed_type` set elsewhere (a
  replica index under `"identity"`, the seed itself under `"manual"`);
- the tool folder's `[card] seed_range`;
- `combine = ["replica"]`, or else a merged figure `over = ["replica"]`.

### e. Beams — U40 (18)

Four representations in the fixtures:
- `energies` plus a user quantity `lepton` with `key = { pythia = "Beams:idB" }`, while `Beams:idA`
  stays in the base card (jets.toml:172-182, ep.cmnd);
- `beams = [[2212, -11]]` (sherpa.toml);
- `beam_a` and `beam_b` (Decay/decay.toml);
- `beams` with `target = "madgraph"` (madgraph.toml).

The order follows an implicit `[hadron, lepton]` convention. Values and tags are written in opposite
orders: `values = [[275, 18]]` but `tags = ["18x275"]`.

### f. How a quantity is drawn — six places

1. labels and styles in `[quantities.X]`;
2. page or curve roles through `plot_points` and `combine`;
3. `[plot].band`;
4. a figure's `over` and `x`;
5. the palette in `[plot.style]`;
6. page texts citing `{q:X}`.

### g. A run folder's name — U41 (20)

Six keys:
- `[run].project` and `[run].name`;
- a configuration's `name`, `serial` and `label` (falling back to its key);
- the tags, which make the point name.

`serial` is bumped by hand to start fresh, and a forgotten bump overwrites.

### h. Imports replace tools whole — U42 (20)

A shared file that defines the chain must expose any per-study tool option as a `{var:}`. One Rivet
`shards` value then takes three files:
- the shared file's `shards = "{var:shards}"`;
- each study's `[config.vars] shards = …`;
- a third file that imports the second and sets it again.

That's because an imported `[tools.X]` is replaced whole, not merged key by key (`config.py:313,320`).

### i. Cluster — four layers

`hep.toml [cluster]` → the run TOML's `[cluster]` → `[run.cfgs.c].cluster` → `--set`. The
`cpus = 0` default is derived from `threads` and `shards`. These are reasonable layers. The
machine's part belongs in the machine's file ([02 §1](02_Organisation.md#1-two-axes-owner--lifecycle)).

---

## 2. Silent behaviours — U44 (35)

- **A base-card line that a quantity or `settings` also sets is overridden silently.** The point card
  is appended, and the last setting wins (`tools.py:819-831`). Lines for keys the runner owns (events,
  threads) are dropped with only a `--plan` note. The starter's own card says the opposite: "A card
  that sets them too is rejected, not overridden" (`framework/templates/work/starter/run.cmnd:4`).
- **Inactive quantities** (U36, above).
- **`shards` rewrites the chain** (b).
- **A module's unknown config keys** fall back to defaults ([04](04_Extending.md), U54).

The fix is one rule: **a value set in two places is an error that names both**, unless one of them
says `override = true`. The card is the lowest layer, and it can't silently win or lose.

---

## 3. Errors and help that stop at a table's edge — U46 (24), U47 (20), U48 (20), U49 (25)

- **No error crosses tables.** `threads` written in `[tools.pythia]` gives "unknown key 'threads' for
  a pythia tool … pythia takes no extra keys" (`tools.py:433-436`), not "`threads` belongs in `[run]`
  or a configuration".
- **Unused tool tables are never checked.** Tool-specific keys and `tool =` are checked only for
  tables in a chain (`tools.py:620-672`). `hep check` skips files without `[run]`, which are exactly
  the shared files where tools are defined.
- **`hep explain` knows only `run.toml`'s keys.** It doesn't cover:
  - a table (`hep explain plot` fails);
  - a tool's options (`analyses`, `pythia_cmnd`);
  - the style keys;
  - the vocabulary (`hep explain pdf`);
  - `[static]`;
  - placeholders, `deck.toml` or `hep.toml`.

  `hep explain static` silently answers for `[run.cfgs.<cfg>].static`, not the top-level `[static]`.
- **`--show-config`** prints `cluster = null` (`cli.py:471-478`) and shows no resolved values or
  origins for tools, quantities and plot.
- **The editor schema (`run.schema.json`) is wrong:**
  - it marks `[run].tools` required (`schema.py:61` copies `required` through `RUN_GIVES`), so every
    fixture is flagged in an editor;
  - it allows any key in a tool table (`schema.py:187`);
  - it gives `[static]` no types.

---

## 4. Names that mean several things — U45 (12)

| Word | Meanings |
|---|---|
| config | the file (`hep run <config>`); `[config]` (how it's read); `[tools.X.config]` (a program's settings); `{config}`; `baseconfig` (a native card); `config_file` (tool.toml); `configuration`/`cfgs`; `--show-config` (values); a compare figure's `"<P>/<config>:<cfg>"` |
| label | a configuration's **folder** name; a quantity's **legend** text; a figure's legend; a deck block's `"events"`/`"folder"`. A compare figure's legend falls back to the folder label |
| name / title | `[run].name` and a configuration's `name` are folders, a figure's `name` is a file stem; `title` is a sweep's header line or a page's title |
| tag | a tool table's key (`[tools.<tag>]`) and a value's short name (`tags`), sometimes in one table |
| nested lists | `tools = [["pythia","rivet"], "yd2rt"]`: an inner list runs **concurrently**; `sweeps = [["pdf","alphas"]]`: an inner list is **zipped** |
| pre / prelim | a stage, and interface set-up: unrelated, nearly the same word |
| key / target | `key` is a string only with `target`, else a table; in a tool folder `key` names a form; `target = "pythia/seed"` vs `"rivet/photo_eic"` (a magic word or an analysis after the slash) |
| `"default"` | omitting `y_gutter` gives 0.5, but `"default"` gives none; `auto_range` omitted is true, `"default"` turns it off; a `[static]` value `"default"` means unset, so no tag can be called "default"; yet `"default"` is the most common configuration name |

---

## 5. Contradictions in the docs, schema and fixtures — U50 (30)

- **`swept`** is in the schema and docs (`run.toml:271-274`, 04 §5) but refused by the loader ("swept
  is gone (V79)", `config.py:654`).
- **Examples use `run.default`/`run.default4`** paths (`run.toml:53,62`; 04 §3; 02 §4.9).
  Configurations are `run.cfgs.<cfg>` now, so `only = ["run.default"]` fails.
- **`test_docs.py:84` checks `run[run["configuration"]]`,** the old shape. No complete example in the
  docs is loaded any more.
- **The import example doesn't match the fixture.** 02 §4.9 shows `seed_sweep.toml` importing
  `validation`, but the fixture imports nothing and repeats ~150 lines. Its `drop` names things the
  fixture lacks, so it would be refused.
- **Sections:** 04 §1 and 02 say seven top-level tables; the schema has eight (`[cluster]`).
- **`arguments = ["./modules/…"]`** (02 §6; 04 §9.2 "./… from the repo"): arguments are not paths,
  and tools run in the point's folder (`execute.py:342`). `{work}/…` is right.
- **Stale card comments:** `Decay/decay.cmnd` cites a `[beams]` table and `ep.cmnd` cites v1's
  `[sweep.cmnd.*]`.

These are fixed in phase 7.3 regardless of v3: today's users read them.

---

## 6. Schema v3

Five principles, then three before/after examples.

1. **One concern, one table.** A quantity holds its points as rows, its fixed point and its bindings.
   A configuration says only what it varies and what it changes.
2. **Tools are typed by their table's name** (`uses =` only for a second instance). An input names its
   producer. Whether an interface is a FIFO or a file is inferred from the chain (same group: FIFO;
   otherwise a file; `keep = true` keeps a stream as a file too). `[prelim]` is retired; its
   `commands` become a `pre` step.
3. **Every concern has one home:**
   - **events and parallelism:** `[run]` and a configuration;
   - **seeds:** one `seed` key;
   - **beams:** one `beams` quantity.
4. **Names say what they are:**
   - `[config]` → `[file]`;
   - `baseconfig` → `card`;
   - a folder `label` → `folder`;
   - `[prelim]` gone (no `pre`/`prelim` pair);
   - `"default"` means "the layer below's value" and nothing else;
   - serial numbers optional (the user's choice): automatic unless the file sets `serial`, and then a
     changed identity under the same serial is refused with the hint to bump it, so a forgotten bump
     can't overwrite;
   - configurations are `[cfgs.<name>]` at the top level (the user's choice), picked by
     `hep run <file> <name>`.
5. **Every error crosses tables:**
   - a key in the wrong table names the right one;
   - a value set twice names both places;
   - unused tool tables and shared files are checked;
   - `hep explain` answers for every key, tool option, style key and vocabulary name.

`hep migrate` rewrites v2 files into v3, as it did for v2's own changes (V79, V93, V98).

### Example 1: the starter

Today (`framework/templates/work/starter/run.toml`, 53 lines, abridged):

```toml
[run]
name = "{{p}}"
project = "{{P}}"
configuration = "pdf"
event_count = 500
threads = 2

[run.cfgs.single]
sweeps = []
tools = [["pythia", "rivet"], "yd2rt"]

[run.cfgs.pdf]
sweeps = ["pdf"]
tools = [["pythia", "rivet"], "yd2rt"]

[prelim]
fifo = ["events.hepmc"]

[static]
sqrts = "13tev"
pdf = "nnpdf23"

[tools.pythia]
tool = "pythia"
baseconfig = "{{p}}.cmnd"
output_file = "events.hepmc"

[tools.rivet]
tool = "rivet"
input = "events.hepmc"
analyses = ["MC_JETS"]
output_file = "jets.yoda"

[tools.yd2rt]
tool = "yd2rt"
input = "jets.yoda"
output_file = "jets.root"

[quantities.sqrts]
values = [13000.0]
tags = ["13tev"]
labels = ["13 TeV"]

[quantities.pdf]
values = [13, 8]
tags = ["nnpdf23", "cteq6l1"]
labels = ["NNPDF 2.3 QCD+QED LO", "CTEQ6L1"]
```

v3:

```toml
[run]
project = "{{P}}"
name    = "{{p}}"
run     = "pdf"                        # the configuration `hep run` picks
events  = 500
threads = 2
chain   = [["pythia", "rivet"], "yd2rt"]

[tools.pythia]                         # the table's name is the tool
card   = "{{p}}.cmnd"
output = "events.hepmc"                # a FIFO: its reader runs in the same group

[tools.rivet]
input    = "pythia"                    # by producer
analyses = ["MC_JETS"]
output   = "jets.yoda"

[tools.yd2rt]
input  = "rivet"
output = "jets.root"

[quantities.sqrts]
fixed  = "13tev"
points = [{ tag = "13tev", value = 13000.0, label = "13 TeV" }]

[quantities.pdf]                       # in the vocabulary: each tool's PDF key (`hep explain pdf`)
fixed  = "nnpdf23"
points = [
  { tag = "nnpdf23", value = 13, label = "NNPDF 2.3 QCD+QED LO" },
  { tag = "cteq6l1", value = 8,  label = "CTEQ6L1" },
]

[cfgs.single]
description = "One run at the fixed point"

[cfgs.pdf]
description = "Two proton PDFs: a curve each on every page"
vary        = ["pdf"]
```

**What changed:**
- every fact is written once: the chain, the interface, a quantity's points and its fixed value;
- the FIFO is inferred, so `[prelim]` and `[static]` are gone;
- `tool = "…"` is gone;
- a quantity can be read top to bottom.

### Example 2: an entangled scan becomes one compound quantity

Today (a user's electron–ion scan, names neutral; 6 values in each of 3 tables):

```toml
[run.cfgs.single]
sweeps = [["ions", "energies", "nuclear"]]

[quantities.energies]
values = [[130, 9], [275, 9], [130, 9], [166, 9], [115, 9], [100, 9]]
tags   = ["9x130", "9x275", "9x130d", "9x166", "9x115", "9x100"]

[quantities.ions]
key    = { pythia = "PDF:nPDFBeamA" }
values = [2212, 2212, 1000010020, 1000020040, 1000471070, 1000791970]
tags   = ["p", "p275", "d", "He4", "Ag107", "Au197"]

[quantities.nuclear]
key    = { pythia = "PDF:useHardNPDFA" }
values = [false, false, true, true, true, true]
tags   = ["free", "free275", "npdf", "npdfHe", "npdfAg", "npdfAu"]
```

v3:

```toml
[quantities.collision]                 # one quantity, three fields set together
fields = { energies = "energies", nucleus = { pythia = "PDF:nPDFBeamA" }, npdf = { pythia = "PDF:useHardNPDFA" } }
points = [
  { tag = "p",     label = "p",           energies = [130, 9], nucleus = 2212,       npdf = false },
  { tag = "p275",  label = "p (275 GeV)", energies = [275, 9], nucleus = 2212,       npdf = false },
  { tag = "d",     label = "d",           energies = [130, 9], nucleus = 1000010020, npdf = true },
  { tag = "He4",   label = '$^{4}$He',    energies = [166, 9], nucleus = 1000020040, npdf = true },
  { tag = "Ag107", label = '$^{107}$Ag',  energies = [115, 9], nucleus = 1000471070, npdf = true },
  { tag = "Au197", label = '$^{197}$Au',  energies = [100, 9], nucleus = 1000791970, npdf = true },
]

[cfgs.nuclei]
vary = ["collision"]
```

A seventh nucleus is one line. A point that mixes up fields is visible on its own row.

### Example 3: the same study at several event counts

Today: the seven `[run.cfgs.default*]` tables of §1c.

v3: a list-valued count makes one folder per count, named from the count:

```toml
[cfgs.pdfs]
description = "Proton-PDF comparison"
vary        = ["pdf"]
events      = [10e6, 25e6, 50e6, 100e6, 150e6, 200e6]   # → pdfs_10M/, pdfs_25M/, …
```

### Seeds and beams in v3

```toml
[run]
seed = "identity"        # or "random", or an integer (the old manual_seed); one key
replicas = 3             # a configuration may ask for replicas; merged pages follow by default

[quantities.beams]       # one representation; ids and energies per named beam
points = [{ tag = "ep920", a = { id = 2212, energy = 920 }, b = { id = -11, energy = 27.5 }, label = "27.5x920 GeV e+p" }]
fixed  = "ep920"
```

A card that also sets its beams is refused with the line, because the run TOML owns beams.

### Compatibility

- `hep migrate --v3` rewrites a file and shows the diff; `--apply` writes it.
- The v2 loader stays for one release behind `schema = 2` in `[file]`, refusing to mix forms.
- Identities are kept wherever the meaning didn't change (renames only). The record notes where
  meaning did change (e.g. `threads` out of the identity of tools that ignore it).
