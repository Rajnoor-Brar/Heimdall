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
- `toolkits/` and `patches/` live in the machine root (02 §3). A user toolkit may define new packages
  outright, with one registry generating the environment's package list (U34).

---

## 3. Customising a standard tool: five sources, one rule

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

## 4. Verification of the design (for its phase)

| Check | Expected |
|---|---|
| a study's `tools/fit/tool.toml` (copied from `exec`) | `hep tools` lists `fit (work)`; a run uses it; Heimdall's tree untouched |
| `tools/pythia/tool.toml` with `extends = "pythia"` and another executable | used for that study only; `hep tools` says "pythia (work, extends shipped)" |
| a vocabulary name declared in `tools/fit/quantities.toml` | `[quantities.<name>]` binds without `key`; `hep explain <name>` describes it |
| a module setting misspelt | refused before the first event, naming the nearest declared key |
| `HEP_KIT=<kit> hep run …` | runs `$HEP_MACHINE/stacks/<kit>/apps/App_Pythia.exe` (via `{apps}`) |
