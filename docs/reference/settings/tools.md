---
id: settings-tools
summary: every key of a [tools.<name>] table, and each standard tool's own options
code: framework/schema/v3.toml, framework/tools
generated: true
---

Generated from the code; change it there. `heimdall explain <key>` says the same. A tool's own settings beyond these go in its card; `heimdall tools <folder>` shows a folder.

# `[tools.<name>]`

[`uses`](#uses) · [`card`](#card) · [`input`](#input) · [`output`](#output) · [`timeout`](#timeout) · [`stall_after`](#stall_after) · [`status`](#status) · [`filters`](#filters) · [`executable`](#executable) · [`arguments`](#arguments) · [`consumes`](#consumes) · [`config`](#config) · [`streamable`](#streamable) · [`consumes_events`](#consumes_events) · [`settings`](#settings) · [`cores`](#cores) · [`shards`](#shards) · [`keep`](#keep)

## `uses`

| Type | Default | Acceptable |
|---|---|---|
| string | — | — |

The tool folder, when it is not the table's name: a second table of one tool, `[tools.<name>] uses = "<folder>"` (`heimdall tools` lists the folders)

## `card`

| Type | Default | Acceptable |
|---|---|---|
| string or list | — | — |

Native base card(s), read in order (root `configs/<A>/`). Tools with a card only.

## `input`

| Type | Default | Acceptable |
|---|---|---|
| string or list | — | — |

What it reads: a producer's table name (`input = "pythia"`: what that tool writes), another tool's output by name, a pre product, (post) a product of every point, or a path. The first input is `{input}`

## `output`

| Type | Default | Acceptable |
|---|---|---|
| string or list | — | — |

What it writes. Read in its own group, a FIFO; in a later group, a file: a product in `results/`, or with `keep = false` a scratch file in the point's working folder. An array is fan-out; one writer per output (C6)

## `timeout`

| Type | Default | Acceptable |
|---|---|---|
| number | — | at least 0 |

The tool fails when it runs longer.

## `stall_after`

| Type | Default | Acceptable |
|---|---|---|
| number | — | at least 0 |

The tool fails when silent this long: no log line, status message or heartbeat (a prepare step waits at least 3600)

## `status`

| Type | Default | Acceptable |
|---|---|---|
| string | — | `"standard"`, `"filters"`, `"none"` |

`"standard"` (`$HEIMDALL_STATUS_FD`), `"filters"` (the folder's `filters.toml`), `"none"`

## `filters`

| Type | Default | Acceptable |
|---|---|---|
| string | — | — |

Your own rules in place of the folder's, a bare name beside the file naming it; implies `status = "filters"`

## `executable`

| Type | Default | Acceptable |
|---|---|---|
| string | — | — |

Exec and module: bare → `build/<A>/<E>` (must be built); `path:<command>` → `PATH`

## `arguments`

| Type | Default | Acceptable |
|---|---|---|
| list | — | — |

Exec and module: argv after the config; placeholders. Not paths: the tool runs in the point's folder, so a script of yours is `{work}/modules/…`

## `consumes`

| Type | Default | Acceptable |
|---|---|---|
| list of strings | — | — |

Exec and module: quantities written into the config.

## `config`

| Type | Default | Acceptable |
|---|---|---|
| table | — | — |

Exec and module: `[tools.<tag>.config]`, extracted to a file.

## `streamable`

| Type | Default | Acceptable |
|---|---|---|
| true or false | — | — |

May it read a FIFO?

## `consumes_events`

| Type | Default | Acceptable |
|---|---|---|
| true or false | — | — |

Is its event count checked against the producer's sidecar?

## `settings`

| Type | Default | Acceptable |
|---|---|---|
| table | — | — |

Native card settings as written, `"HeavyIon:mode" = 1`, with no base card needed: over the base card, refused when a quantity sets the same key (one source per key, C8); a tool with no card refuses them.

## `cores`

| Type | Default | Acceptable |
|---|---|---|
| integer | — | at least 1 |

How many cores it keeps busy, for `--plan`'s note and the crowded warning; an integrated program is estimated as the generator's threads and one more.

## `shards`

| Type | Default | Acceptable |
|---|---|---|
| integer | `1` | at least 1 |

K > 1: K processes of this tool, each on a share of the events, merged into its `output` by the folder's merge tool (rivet). The chain is unchanged.

## `keep`

| Type | Default | Acceptable |
|---|---|---|
| true or false | `true` | — |

`false`: what it writes for a later group is a scratch file of the point (`records/…/logs/<point>/`), not a product (`results/`)

## Each tool's own options

### `merge`

#### `equivalent`

| Type | Default | Acceptable |
|---|---|---|
| flag | `true` | — |

The inputs are replicas of one process (-e): averaged σ.

### `rivet`

[`analyses`](#analyses) · [`options`](#options)

#### `analyses`

| Type | Default | Acceptable |
|---|---|---|
| list | **required** | — |

The analyses to run, with options: "photo_eic:R=0.4".

#### `options`

| Type | Default | Acceptable |
|---|---|---|
| table | — | — |

Analysis options applied to every analysis: { R = 0.4 }.

### `yd2rt`

#### `select`

| Type | Default | Acceptable |
|---|---|---|
| list | — | — |

YODA path globs to convert (default: everything but /RAW, /TMP)
