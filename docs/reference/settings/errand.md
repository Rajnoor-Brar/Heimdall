---
id: settings-errand
summary: every key of an errand file's [file], [errand], [cfgs.*] and [quantities.*]: type, default, values, effect
code: framework/schema/run.toml, framework/schema/v3.toml
generated: true
---

Generated from the code; change it there. `heimdall explain <key>` says the same. Plot, tool and cluster keys have their own pages.

# `[file]`

[`master`](#master) · [`import`](#import) · [`drop`](#drop) · [`vars`](#vars) · [`meta`](#meta) · [`schema`](#schema)

## `master`

| Type | Default | Acceptable |
|---|---|---|
| string | — | — |

Overlays the tool folders' mappings key by key (`[quantities.<tool>.compatible_quantities]`): an entry for a (tool, quantity) pair replaces the framework's. The file must exist.

## `import`

| Type | Default | Acceptable |
|---|---|---|
| string or list of strings or tables | — | — |

Errand files this one starts from, in order, named as `heimdall run` names a config: `name` is this assignment's (`configs/<A>/name.toml`), `<A>/<E>` another assignment's, `./…` from the work dir; `.toml` optional. **This file wins**: a quantity or configuration of the file replaces the imported one whole; a tool table, `[plot]`, `[cluster]` and `[errand]`'s own keys merge key by key, tables recursively. Imports nest, depth-first; a circle is refused. Another assignment's file keeps its bare paths its own assignment's. The file that imports sets its own `[errand].name` and `assignment`. An entry may be `{ from = "<config>", only = ["quantities", "cfgs.default", …] }`: only those tables or dotted keys, each of which the file must have.

## `drop`

| Type | Default | Acceptable |
|---|---|---|
| list of strings | — | — |

Dotted keys (`cfgs.default4`, `plot.figures.statistics`, `quantities.radius`, `tools.jets`) taken out of what the imports brought in, before this file's own tables are laid over them. Each must name something an import gave, so a misspelt drop is refused rather than keeping what it meant to remove; a file that imports nothing has nothing to drop.

## `vars`

| Type | Default | Acceptable |
|---|---|---|
| table | — | — |

`name = value`, cited in any string of the file as `{var:name}` and replaced when the file is read, after its imports and `--set`, so an identity sees only the result. A string that is exactly one var takes its value as it is: `events = "{var:events}"` is an integer, and a list stays a list; inside a longer string a var must be a scalar (`"rivet:{var:ana}"`). An unknown name is refused with the nearest. An imported file's `{var:…}` takes this file's value; its own `[file.vars]` come with whatever is taken of it, under this file's. `--set file.vars.<name>=…` changes one for a job.

## `meta`

| Type | Default | Acceptable |
|---|---|---|
| table | — | — |

Descriptive: it never changes a point. Any key is free text for people (`author`, `references`, …) except `versions = { pythia8 = "8.317", rivet = "4.1.3" }`: the packages of `env/stack.toml` the file was run with, each version a string. A version the stack does not have (`6.5` matches 6.5.6) is a **warning** in `--plan`, at the job's start and in `heimdall check`, which still passes: the job goes ahead, at your own risk. A package stack.toml does not name is refused, since its warning could never come.

## `schema`

| Type | Default | Acceptable |
|---|---|---|
| integer | — | — |

`3`, or `2` to keep a v2 file v2 for one release; a file with `[file]` is v3 without it.

# `[errand]`

[`name`](#name) · [`assignment`](#assignment) · [`run`](#run) · [`serial`](#serial) · [`events`](#events) · [`threads`](#threads) · [`parallelism`](#parallelism) · [`plot`](#plot) · [`stats`](#stats) · [`description`](#description) · [`tag`](#tag) · [`sweep_runs`](#sweep_runs) · [`notify`](#notify) · [`chain`](#chain) · [`vary`](#vary) · [`plot_points`](#plot_points) · [`combine`](#combine) · [`pre`](#pre) · [`post`](#post) · [`generate_cards`](#generate_cards) · [`seed`](#seed) · [`commands`](#commands)

## `name`

| Type | Default | Acceptable |
|---|---|---|
| string | **required** | — |

The errand's folder name, `<E>` in `results/<A>/<E>/` (its Runs below it)

## `assignment`

| Type | Default | Acceptable |
|---|---|---|
| string | **required** | — |

The subfolder of `configs/`, `modules/`, `records/`, `results/`; must equal the folder the file is in, when it is under `configs/`

## `run`

| Type | Default | Acceptable |
|---|---|---|
| string | — | — |

The configuration `heimdall run <file>` runs, a `[cfgs.<name>]` (C2). Under `sweep_runs` it may be left out.

## `serial`

| Type | Default | Acceptable |
|---|---|---|
| integer | — | — |

The prefix `NN_` of each Run's folder, `<E>/NN_<folder>`: **location, never identity**. Left out, the runner numbers it: the newest folder made from these inputs, else a new one. Set, a changed configuration is refused there rather than overwrite what it made (`--rerun` overwrites) A configuration inherits it from `[errand]`.

## `events`

| Type | Default | Acceptable |
|---|---|---|
| integer | — | at least 1 |

Every configuration's event count, unless it gives its own. A configuration inherits it from `[errand]`.

## `threads`

| Type | Default | Acceptable |
|---|---|---|
| integer | `1` | at least 0 |

Default for configurations. `0` means every core, **resolved to a number at plan time**. A configuration inherits it from `[errand]`.

## `parallelism`

| Type | Default | Acceptable |
|---|---|---|
| integer or string | `1` | `"auto"`, at least 1 |

Default for configurations: how many points run at once; `"auto"`: as many as the cores hold, `os.cpu_count() // the costliest point's cores`. `threads` stays each point's; never part of an identity or a seed, so changing it reruns nothing. A configuration inherits it from `[errand]`.

## `plot`

| Type | Default | Acceptable |
|---|---|---|
| true or false or list of strings | `true` | — |

The plot follow-up: `true` draws every set of the Run's plot document (its `totality` and the `[plot].sets`), `false` none (the document is written all the same, for `heimdall plot` later), a list draws those sets (`["totality", "pdf_by_generator"]`) and is the document's `[plot].draw`. A configuration may set its own; `heimdall run … --no-plot` turns it off for one job. A configuration inherits it from `[errand]`.

## `stats`

| Type | Default | Acceptable |
|---|---|---|
| true or false or list of strings | `true` | — |

The statistics follow-up: `true` measures the sets the Run draws (or, with `plot = false`, every set, undrawn), `false` none, a list those sets (the document's `[stats].sets`). A configuration may set its own; `heimdall run … --no-stats` turns it off for one job. A configuration inherits it from `[errand]`.

## `description`

| Type | Default | Acceptable |
|---|---|---|
| string | — | — |

What the errand is for.

## `tag`

| Type | Default | Acceptable |
|---|---|---|
| string | — | — |

Default for configurations: a short name kept with the Run (its record's `tag` file and its plot document's `[source].tag`), which `heimdall runs`, `heimdall status` and a report show beside it. Never part of a point's identity: tagging reruns nothing. `heimdall run … --tag NAME` gives one for a job; a Run that has a tag keeps it (`heimdall tag` changes it); `""` is none. A configuration inherits it from `[errand]`.

## `sweep_runs`

| Type | Default | Acceptable |
|---|---|---|
| true or false or list of strings | `false` | — |

`true`: `heimdall run <config>` runs every configuration, one after another, in the order of the file; `["a", "b"]`: these, in this order.

## `notify`

| Type | Default | Acceptable |
|---|---|---|
| string | `"none"` | `"none"`, `"desktop"` |

`"desktop"`: a desktop notification (`notify-send`) when `heimdall run` ends, with its verdict; never fails a job.

## `chain`

| Type | Default | Acceptable |
|---|---|---|
| list | — | — |

Every configuration's tools, unless it gives its own. A configuration inherits it from `[errand]`.

## `vary`

| Type | Default | Acceptable |
|---|---|---|
| list | — | — |

A string is an independent axis, and the points are the grid of the axes. An array is an entangled group: its quantities move together, value i with value i, so they need equal point counts. `{ points = [...] }` lists combinations by hand, one row a point. The order decides point names and running order. `[]` is one point. A configuration inherits it from `[errand]`.

## `plot_points`

| Type | Default | Acceptable |
|---|---|---|
| list of strings | — | — |

The swept quantities whose values make the pages: each combination is a cell, with a page per object, and the other swept quantities become its curves. Left out, every point is on one page. `[plot].sets` chooses cells by hand instead. A configuration inherits it from `[errand]`.

## `combine`

| Type | Default | Acceptable |
|---|---|---|
| list of strings | — | — |

Swept quantities whose points are merged into one curve. A configuration inherits it from `[errand]`.

## `pre`

| Type | Default | Acceptable |
|---|---|---|
| list | — | — |

The form of `tools` A configuration inherits it from `[errand]`.

## `post`

| Type | Default | Acceptable |
|---|---|---|
| list | — | — |

The form of `tools` A configuration inherits it from `[errand]`.

## `generate_cards`

| Type | Default | Acceptable |
|---|---|---|
| list of strings | — | — |

Tool tables (tags) whose cards and configs are made for the point although they do not run in it, for a program that runs them itself (an integrated program: Pythia and Rivet inside it); and `"<tag>:<product>"` for a product made on demand (Herwig's `run`, Sherpa's `results`, MadGraph's `process`). The chain's tools are always in the context file, which every tool finds through `HEIMDALL_CONTEXT` A configuration inherits it from `[errand]`.

## `seed`

| Type | Default | Acceptable |
|---|---|---|
| string or integer | `"identity"` | — |

`"identity"`: from the generator's identity; `"random"`: drawn when the point runs; an integer: exactly that seed for every point (a replica, `to = { "pythia/seed" = true }`, gives a point its own)

## `commands`

| Type | Default | Acceptable |
|---|---|---|
| list | — | — |

Argv arrays run in each point's output folder before its tools, in order; output to the point's `prelim.log`; a nonzero exit fails the point. Placeholders: `{work}`, `{heimdall}`, `{out}`, `{res}`, `{file:<name>}`

# `[cfgs.<name>]`

[`extends`](#extends) · [`serial`](#serial-1) · [`name`](#name-1) · [`folder`](#folder) · [`title`](#title) · [`description`](#description-1) · [`tag`](#tag-1) · [`events`](#events-1) · [`threads`](#threads-1) · [`parallelism`](#parallelism-1) · [`plot`](#plot-1) · [`stats`](#stats-1) · [`vary`](#vary-1) · [`plot_points`](#plot_points-1) · [`combine`](#combine-1) · [`chain`](#chain-1) · [`generate_cards`](#generate_cards-1) · [`pre`](#pre-1) · [`post`](#post-1) · [`fixed`](#fixed) · [`vars`](#vars-1) · [`data`](#data) · [`cluster`](#cluster) · [`seed`](#seed-1)

## `extends`

| Type | Default | Acceptable |
|---|---|---|
| string | — | — |

Another configuration this one starts from (chains are followed; a circle is refused)

## `serial`

| Type | Default | Acceptable |
|---|---|---|
| integer | — | — |

- `"default"`: the layer below's value, as if left out

This configuration's `NN_`, over `[errand]`'s; left out in both, the runner numbers it.

## `name`

| Type | Default | Acceptable |
|---|---|---|
| string | — | — |

The errand folder above this configuration's Run: `<A>/<E>/NN_<label>/`

## `folder`

| Type | Default | Acceptable |
|---|---|---|
| string | — | — |

The Run's folder name, after the serial: `NN_<folder>`; empty means the table key.

## `title`

| Type | Default | Acceptable |
|---|---|---|
| string | — | — |

The header line of the Run under `[errand].sweep_runs`: `run 02 - <title> -`

## `description`

| Type | Default | Acceptable |
|---|---|---|
| string | — | — |

What the configuration is for.

## `tag`

| Type | Default | Acceptable |
|---|---|---|
| string | — | — |

The tag a job gives this configuration's Run (a letter or digit, then letters, digits, `.`, `_`, `+`, `-`; at most 40), unless `--tag` gives another or the Run already has one: a Run keeps its tag when it is run again, and `heimdall tag <A>/<E>/<R>` shows or changes it. `""` gives none over `[errand]`'s. Never part of a point's identity.

## `events`

| Type | Default | Acceptable |
|---|---|---|
| integer | — | at least 1 |

- `"default"`: the layer below's value, as if left out

Required here if `[errand]` has none. A list is one configuration per count, `<name>_<count>` (`pdf_10k`), run in turn as `<name>`

## `threads`

| Type | Default | Acceptable |
|---|---|---|
| integer | — | at least 0 |

- `"default"`: the layer below's value, as if left out

`0` = every core.

## `parallelism`

| Type | Default | Acceptable |
|---|---|---|
| integer or string | — | `"auto"`, at least 1 |

- `"default"`: the layer below's value, as if left out

Points at once (`"auto"`: cores ÷ a point's cores); `--plan` and the job's title say about how many cores that is, and warn past the machine's.

## `plot`

| Type | Default | Acceptable |
|---|---|---|
| true or false or list of strings | — | — |

- `"default"`: the layer below's value, as if left out

The plot follow-up for this configuration: `true`, `false`, or the sets it draws, so that sets defined once for the file are each drawn by the configurations they fit.

## `stats`

| Type | Default | Acceptable |
|---|---|---|
| true or false or list of strings | — | — |

- `"default"`: the layer below's value, as if left out

As [errand].stats, for this configuration: true, false, or the sets it measures.

## `vary`

| Type | Default | Acceptable |
|---|---|---|
| list | — | — |

A string is an independent axis, and the points are the grid of the axes. An array is an entangled group: its quantities move together, value i with value i, so they need equal point counts. `{ points = [...] }` lists combinations by hand, one row a point. The order decides point names and running order. `[]` is one point.

## `plot_points`

| Type | Default | Acceptable |
|---|---|---|
| list of strings | — | — |

The swept quantities whose values make the pages: each combination is a cell, with a page per object, and the other swept quantities become its curves. Left out, every point is on one page. `[plot].sets` chooses cells by hand instead.

## `combine`

| Type | Default | Acceptable |
|---|---|---|
| list of strings | — | — |

Swept quantities whose points are merged into one curve.

## `chain`

| Type | Default | Acceptable |
|---|---|---|
| list | — | — |

Each entry is a tool table's name, or an array of names that run together as one group (one level only). Groups run in order: one starts when the previous succeeded and its products passed their checks. What a tool writes for a reader in its own group is a FIFO; for a later group, a file. `"@<quantity>"` is replaced, per point, by that quantity's value: a tool table's name or a piece of chain. `[errand]`'s when left out.

## `generate_cards`

| Type | Default | Acceptable |
|---|---|---|
| list of strings | — | — |

Tool tables (tags) whose cards and configs are made for the point although they do not run in it, for a program that runs them itself (an integrated program: Pythia and Rivet inside it); and `"<tag>:<product>"` for a product made on demand (Herwig's `run`, Sherpa's `results`, MadGraph's `process`). The chain's tools are always in the context file, which every tool finds through `HEIMDALL_CONTEXT`

## `pre`

| Type | Default | Acceptable |
|---|---|---|
| list | — | — |

The form of `tools`

## `post`

| Type | Default | Acceptable |
|---|---|---|
| list | — | — |

The form of `tools`

## `fixed`

| Type | Default | Acceptable |
|---|---|---|
| table | — | — |

`{ quantity = "tag" }`: this configuration's fixed points, over each quantity's own `fixed`

## `vars`

| Type | Default | Acceptable |
|---|---|---|
| table | — | — |

Merged over `[file.vars]` for this configuration alone, before any `{var:…}` is replaced: a configuration may run other cards (`pythia_card = "../zeus/dis.cmnd"`), another analysis, another output, in the same file as the others. Only the configuration run, planned or drawn reads them.

## `data`

| Type | Default | Acceptable |
|---|---|---|
| table | — | — |

Replaces `[plot.data]` for this configuration: its pages' data, its plot document's, its statistics' reference, when it runs another analysis than the file's others.

## `cluster`

| Type | Default | Acceptable |
|---|---|---|
| table | — | — |

Merged over the errand file's `[cluster]`, key by key, for this configuration's jobs (a longer `time` for its many events, say); the same keys.

## `seed`

| Type | Default | Acceptable |
|---|---|---|
| string or integer | `"identity"` | — |

`"identity"`: from the generator's identity; `"random"`: drawn when the point runs; an integer: exactly that seed for every point (a replica, `to = { "pythia/seed" = true }`, gives a point its own)

# `[quantities.<q>]`

[`shape`](#shape) · [`to`](#to) · [`format`](#format) · [`description`](#description-2) · [`exclude`](#exclude) · [`points`](#points) · [`fixed`](#fixed-1) · [`fields`](#fields)

## `shape`

| Type | Default | Acceptable |
|---|---|---|
| string or list | — | — |

The values' shape, in the vocabulary's grammar: `"pdg"`, `"float|int"`, `["float", "float"]`; checked when the TOML is read. For a quantity of your own (one the vocabulary, `framework/schema/quantities.toml`, does not name); a vocabulary quantity has its own shape.

## `to`

| Type | Default | Acceptable |
|---|---|---|
| string or table | — | — |

Where the value goes: `{ pythia = "PDF:pSet" }` a native key per tool table or tool; `{ "rivet/photo_eic" = "R" }` an analysis option; `{ "pythia/seed" = true }` a replica. An entry with a `/` or `true` makes the entries the only consumers.

## `format`

| Type | Default | Acceptable |
|---|---|---|
| string | — | — |

A Python format for the value: `"{}*GeV"`

## `description`

| Type | Default | Acceptable |
|---|---|---|
| string | — | — |

What the quantity is.

## `exclude`

| Type | Default | Acceptable |
|---|---|---|
| list | — | — |

Points a vary leaves out, by their **1-based** place (as `fixed = "#2"` and `--points 2` count): `exclude = [2]` varies the others. The remaining points keep their names and identities and are numbered 1… over what is varied. In an entangled group, a point any member excludes leaves the group. `fixed` may still pick an excluded point. Refused: a place outside the points, or none left.

## `points`

| Type | Default | Acceptable |
|---|---|---|
| list | — | — |

The points, one row each: `{ tag, value, label, style }`; `value` is required, `tag` names the point's folder.

## `fixed`

| Type | Default | Acceptable |
|---|---|---|
| string or integer or number | — | — |

The point a configuration that does not vary the quantity takes: a tag, a value or `"#N"`

## `fields`

| Type | Default | Acceptable |
|---|---|---|
| table | — | — |

A compound quantity: `{ <field> = <its binding> }`, each field a quantity of its own, its rows' values set together.
