# 04 — Extending: one tool system

> "In theory, standard tools are just predefined user tools, and a general system accepts and
> coordinates all." — the user, 2026-10-12

Heimdall is most of the way there. The runner names no tool (V61: a test enforces it). Everything a
tool does is data in its folder, `framework/tools/<tool>/`:
- `tool.toml`: its category, executable, argv, card style, options schema, outputs, exports,
  identity, prepare cache, checks, shards and beam slots (`tools.py:38-53`);
- `quantities.toml`: how it consumes the vocabulary;
- `filters.toml`: how its log becomes status;
- an optional `render.py`.

What breaks the principle is **where folders may live**, and **two special kinds**.

---

## 1. What is special today

### Folders come only from Heimdall — U51 (24)

`tools.folders()` globs `framework/tools/*/tool.toml` (`tools.py:36,99-125`), and the vocabulary
mappings are found the same way (`quantities.py:73`). `paths.py:12` says it outright: "there is no
search path".

So a tool kind the user writes needs Heimdall's own tree edited, and it can't ship with the study
that needs it. A tool kind here means a generator they compiled, an experiment's simulation, or a
fitting program with its own card format and log patterns. Adding one takes seven places
(`06_Internals.md` §16–17):
1. `tool.toml`
2. `filters.toml`
3. `quantities.toml`
4. a new vocabulary name in `framework/schema/quantities.toml`
5. `env/stack.toml`
6. tests
7. three doc places, enforced by `test_docs.py:141-146`

That's U53 (15).

### `custom` and `module` are kinds, not tools — U52 (15)

- **`tool = "custom"`** runs any executable. Its `[tools.<tag>.config]` and consumed quantities are
  written to a TOML passed as the first argument (04 §9.2). But everything a folder would say (how to
  read its count, its log, its identity's files, its options' types) can't be said. It's a per-run
  table, so sharing it needs a common file and `[config] import`.
- **A typical custom tool touches 3–5 places:** the tool table, the chain, often `[prelim]` and
  `streamable`, the quantities' `target`/`key` or `consumes`, and a `filters` file. Exports
  (`pythia_cmnd = true`) rely on a `<tool>_<export>` naming convention (`tools.py:55,446-483`).
- **`tool = "module"`** is the same for programs built with `src/Module.hh`, with a fixed argv
  (`--input`, `--output`, `--events`, `--sidecar`).

### A module's settings are never checked — U54 (28)

A module reads its config with defaults, and nothing reports keys it doesn't know (`src/Module.hh`
has no such check). A typo in `[tools.decay.config]` (`mass_tolernace = 0.1`) runs with the default
and gives plausible, wrong curves. Heimdall refuses exactly this for Rivet analysis options (L19),
but not for its own modules.

### Quantities bind by name — U56 (18)

`[quantities.pdf]` reaches Pythia's `PDF:pSet` because it is called `pdf`: the vocabulary
(`framework/schema/quantities.toml`) plus `framework/tools/pythia/quantities.toml:7-14`. Call it
`pdfs` and it binds to nothing. A quantity that binds to nothing and isn't swept is inactive and
silent (03 U36).
- **The vocabulary has no user overlay:** neither has `latex.toml`.
- **The project-level `[config].master`** overlays a tool's mapping, but not the vocabulary.

### Style, toolkits and patches are Heimdall's files — U25 (16), U26 (16)

- **The house style** is `src/Apps/Paint/base.toml`, read at run time ("edit it to change them
  all"). A study can only restyle per run (`root_style`, `[plot.style]`).
- **A user's toolkit** goes in `recipes/toolkits.d/` (tracked tree, untracked file, not ignored). It
  can only override existing packages: a new package needs `--config` or an edit to `packages.toml`,
  plus `hep_env.sh`'s list to reach `PATH`.
- **A user's patch** must sit in `recipes/patches/`: paths resolve from the repo root.

### Plot code shares the tools folder — U55 (8)

`framework/tools/` also holds `mpl`, `yoda` (backends), `figures` (derive, layout), `merge` and
`plotmerge`. They are folders the plot stage loads by path (`plot.py:127,397,486,1118`), and they
look like chain tools.

---

## 2. Proposed: one system, a search path

**One loader, one schema, three roots, nearest wins:**

```
framework/tools/<tool>/        the shipped set ("standard tools")
$HEP_MACHINE/tools/<tool>/     this machine's (an experiment's software installed here)
<work dir>/tools/<tool>/       this study's (travels with it in git)
```

- **A folder in a nearer root with a shipped tool's name either replaces it, or extends it.** To
  extend, it writes `extends = "pythia"` in its `tool.toml` and gives only what differs: a different
  executable, an extra option, its own filters.
- **Every folder is checked by the same `FOLDER_SECTIONS` rules,** and listed by **`hep tools`** with
  its origin (shipped / machine / work) and whether it overrides one.
- **`custom` and `module` become two ordinary shipped folders:**
  - `exec`: any program, config as its first argument;
  - `module`: a `Module.hh` program.

  A user copies either to `tools/<mine>/` and adds what it lacks (count check, filters, identity
  files). **`hep tools new <name> --from exec`** writes that copy with comments.
- **A folder's quantity mapping and vocabulary additions travel with it.**
  `tools/<mine>/quantities.toml` can declare a new vocabulary name (`shape`, `unit`, `doc`), so
  `[quantities.<that name>]` binds in every study that uses the tool.
- **`hep explain <tool>.<option>`** works for every folder (its `[options]` table gets `doc` strings).
  `test_docs` keeps the shipped folders documented; a user folder is documented by its own `doc`
  strings.
- **`{apps}`** is a placeholder like `{hep}` and `{work}`, so shipped folders stop hardcoding
  `{hep}/framework/Apps`. That fixes isolated stacks (U27).

**Modules get key checking** (U54):
- a module declares its settings with defaults and docs (`Module::setting("mass_tolerance", 0.15,
  "…")`);
- `Module.hh` refuses keys it never declared, before the first event;
- `--describe` prints the declarations, which `hep explain decay.mass_tolerance` reads.

**Plot code moves** to `framework/plot/` (backends, figures). `framework/tools/` then holds chain
tools only, the same kind of thing in every root.

**Style, toolkits, patches:**
- a work dir's `style.toml` (and a machine's) is laid over `base.toml`. `base.toml` moves to
  `framework/style/`;
- `toolkits/` and `patches/` live in the machine root (02 §3). Toolkits, the stack's build
  configurations, are [§5](#5-toolkits-the-stacks-build-configurations).

---

## 3. The tool contract: its own arguments, and one context file

The user's design (2026-10-12): **each tool defines the arguments it takes, and the run provides one
more thing, a TOML listing the cards of the other tools.**

**Today:**
- one tool reaches another's set-up through **exports**: `<tool>_<export> = true | "<tag>"` in its
  table (`pythia_cmnd = true`, `rivet_analyses = true`; `tools.py:446-483`, C13);
- each tool folder declares what it offers (`[exports.cmnd]`, `[exports.analyses]`, …);
- a `custom` or `module` tool gets them as `[standard.<key>]` tables in its config file.

It works, but it is opt-in per pair of tools, and it is named by convention.

**Proposed:**
- **Arguments are the tool's own.** A tool's folder declares its argv with placeholders: `{card}`,
  `{config}`, `{input}`, `{output}`, `{events}` and so on. Inputs and outputs stay arguments, as a
  program expects them.
- **The context file is the one thing the run adds.** When a point starts, the runner writes one
  standard TOML for it. For each tool whose card it generated, it gives:
  - the path of that tool's **card** (its native card, if it has one);
  - its **config** (the tool's resolved table as TOML: options, analyses, settings).
- **Cards are generated only for the tools that are used** (the user, 2026-10-12): the tools in the
  point's chain, plus the ones named in `run.generate_cards`. A tool table that is defined but not
  used (a shared file's spare Pythia, a Delphes table for another configuration) gets no card and
  isn't in the context. It is still checked by `hep check` (U46).

  An integrated program shows why the list exists. InprocJets runs Pythia and Rivet inside itself,
  so its chain is `["jets", "yd2rt"]`, yet it needs Pythia's card and Rivet's analyses:

  ```toml
  [run]
  chain          = ["jets", "yd2rt"]
  generate_cards = ["pythia", "rivet"]    # not run as processes; their cards and configs are made for jets
  ```

  A configuration may set its own `generate_cards`, as it may set its own chain.

  ```toml
  # the point's context file (HEP_CONTEXT), written when the point starts
  [tools.pythia]
  tool   = "pythia"
  card   = "/…/output/Demo/jets/03_pdf/NNPDF23lo/cards/pythia.point.cmnd"
  config = "/…/output/Demo/jets/03_pdf/NNPDF23lo/config/pythia.toml"

  [tools.rivet]
  tool   = "rivet"
  config = "/…/config/rivet.toml"          # analyses, options, plugin path

  [tools.jets]
  tool   = "module"
  config = "/…/config/jets.toml"
  ```

- **Delivery, environment first.**
  - Every tool's process gets `HEP_CONTEXT=<path>`, so any program can find the file without an argv
    change. Third-party tools (Rivet, Delphes, Sherpa) simply ignore it.
  - A tool whose folder wants it on the command line puts `{context}` in its argv. Heimdall's apps
    and the user's tools can.
- **Lifetime.**
  - The file is written when the point starts and removed when the point ends.
  - It lives in the point's ephemeral area (`logs/`, 02 §3), never in its record.
  - The cards and configs it names stay in the record, as now. So nothing is lost, and the
    provenance doesn't depend on the file.
- **What it replaces.**
  - The `<tool>_<export> = true` keys and the `[standard.<key>]` tables go: an integrated program
    reads Pythia's card and Rivet's analyses from the context, because `generate_cards` named them.
  - **The expensive products use the same key** (a proposal). Herwig's run file, MadGraph's process
    directory and Sherpa's integration take minutes to hours, so they are made only when listed as
    `"<tool>:<product>"` (`generate_cards = ["sherpa:results"]`), and then appear in the context
    too. One key says what the run prepares beyond its chain.
- **What it doesn't carry** (the user's choice): inputs and outputs (they are arguments), and the
  point's quantity values and paths (each tool gets its own through its card, config and arguments).

---

## 4. Customising a standard tool: five sources, one rule

Pythia's settings can come from five places today:
1. the base card;
2. `[tools.pythia].settings`;
3. a quantity with `key = { pythia = … }`;
4. a vocabulary name;
5. `[config].master`'s mapping overlay.

The card loses silently to the others, and owned keys are dropped with a `--plan` note (03 §2).

**v3 keeps the sources, but adds one rule and one view:**
- **the rule:** each native key has one source; a second is an error naming both, unless the later
  one says `override = true`;
- **the view:** `hep run … --plan --card pythia` prints the point card with each line's origin (card
  line N / setting / quantity `pdf` / vocabulary `energies` / runner-owned).

---

## 5. Toolkits: the stack's build configurations

A toolkit is a **configuration for building the stack**: which packages, with which flags and
settings. It is not a run-time tool.

**Today:**
- `recipes/packages.toml` defines every package's recipe (47 tables);
- `recipes/toolkits.toml` holds 21 presets in one file (`[primary]`, `[lab]`, `[generators]`, …);
- a user's own toolkit goes in `recipes/toolkits.d/*.toml`, in Heimdall's tree. It may override a
  package but not add one (U26);
- the Mac's platform fixes are a third file, `--config mac.toml`.

**Proposed (the user's design, 2026-10-12):**

- **`toolkits/standard.toml`** holds every package's definition:
  - url (with mirrors), version and sha256;
  - its flags;
  - its **conditional flags**, evaluated on the final set: what is installed, plus what this build
    adds (today's `optional = { root = [...] }`, as for YODA's HDF5 or Delphes' Pythia 8);
  - its `verify`;
  - its groups (`core`, `generators`, `data`, …).

  `@standard` builds the usual set.
- **One TOML per toolkit**, invoked as `@<name>` (`toolkits/lab.toml` → `@lab`). Shipped ones are in
  Heimdall's `recipes/toolkits/`; the user's are in the machine root's `toolkits/`, nearest first, as
  for tools. A toolkit file:

  ```toml
  # toolkits/heavy-ion.toml — invoked as @heavy-ion
  description = "heavy-ion work: JETSCAPE with HDF5, on the lab set"
  extends     = "lab"                   # start from another toolkit (optional)

  [standard]                            # which of standard.toml's recipes to borrow
  core     = true                       # a group …
  jetscape = true                       # … or a package
  hdf5     = true
  sherpa   = false                      # take one out of what `extends` brought

  [settings]                            # cxx_std, opt_flags, cores: changing the ABI makes it an isolated stack
  cores = 16

  [packages.jetscape]                   # override fields of a borrowed recipe (merged, not replaced)
  extra = ["-DUSE_ROOT=ON"]

  [packages.my-generator]               # or a recipe of its own, with the same keys as standard.toml's
  release = "1.2"
  url     = "https://example.org/my-generator-{release}.tar.gz"
  kind    = "cmake"
  needs   = ["hepmc3"]
  ```

  Dependencies are added automatically. The resolved set prints with `--list @heavy-ion`, showing
  where each package and each flag came from.
- **Platform fixes are not a toolkit.** `recipes/platforms/<platform>.toml` (the Mac's fixes of
  [01 D](01_Process.md#d-toolchain-drift--u8-40)) is applied by platform, under every toolkit. The
  machine's `machine.toml` is applied last.
- **Versions** (the user's decision): the recipes move to the newer versions the Mac proved (YODA
  2.1.4, Rivet 4.1.4, Pythia 8318, MadGraph 3.8.1). The lab PC takes them when it is repaired
  (phase 2.3). Old points stay valid as recorded; new ones record the new versions.
- **HDF5** (the user's decision) is a recipe in `standard.toml`, in `@primary` and `@lab` as well as
  `@data` and `@heavy-ion`. YODA is built with `.yoda.h5` support when HDF5 is in the build (a
  conditional flag), else `--disable-h5`.

---

## 6. Verification of the design (for its phase)

| Check | Expected |
|---|---|
| a point runs; a module prints `$HEP_CONTEXT` | a TOML with every tool's card and config path; gone after the point |
| an integrated program (InprocJets) with no `pythia_cmnd`/`rivet_analyses` keys | runs from the context file alone |
| `toolkits/mine.toml` in the machine root, `extends = "lab"`, one package off, one added | `--list @mine` shows the set and each value's origin; the build does it |
| `@primary` on a fresh machine | HDF5 built; YODA with `.yoda.h5`; `hep doctor` confirms |
| a study's `tools/fit/tool.toml` (copied from `exec`) | `hep tools` lists `fit (work)`; a run uses it; Heimdall's tree untouched |
| `tools/pythia/tool.toml` with `extends = "pythia"` and another executable | used for that study only; `hep tools` says "pythia (work, extends shipped)" |
| a vocabulary name declared in `tools/fit/quantities.toml` | `[quantities.<name>]` binds without `key`; `hep explain <name>` describes it |
| a module setting misspelt | refused before the first event, naming the nearest declared key |
| `HEP_KIT=<kit> hep run …` | runs `$HEP_MACHINE/stacks/<kit>/apps/App_Pythia.exe` (via `{apps}`) |
