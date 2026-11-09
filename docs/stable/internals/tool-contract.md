---
id: tool-contract
summary: what a tool folder holds, the search path, every tool.toml section and key, render.py, providers, and what the runner does per point
code: framework/runner/tools.py, framework/tools, framework/runner/paths.py
---

# The tool-folder contract

Everything the runner knows about a kind of tool is in its folder; the core never names a tool, and a test fails if it does. Folders are found nearest first (`paths.tool_chains`): the work dir's `tools/<tool>/`, Himinbjorg's, then `framework/tools/<tool>/`. A nearer folder replaces a farther one whole, unless its `tool.toml` says `extends = "<tool>"`: then it is laid over, table by table, and its other files are the nearest that has them. `heimdall tools` lists them.

```
<tool>/
  tool.toml        required   what the tool is and how to run it
  quantities.toml  optional   how it consumes the vocabulary's quantity names
  render.py        optional   the whole point card, for dialects [card] cannot write
  filters.toml     optional   stdout rules, for a tool without the status protocol
```

## `tool.toml`

Every section and key is checked when folders load: an unknown one is an error. Outside a section, `extends` as above.

| Section | Key | Means |
|---|---|---|
| `[tool]` | `category` | one of the ten, for reading |
| | `executable` | a command on `PATH`, or `{apps}/…` for Heimdall's apps (must exist: "not built", `heimdall build --framework`) |
| | `streamable` | may read its input from a FIFO (default false) |
| | `status` | `standard`, `filters`, `none` (default none) |
| | `consumes_events` | its product's event count is checked against its input's producer sidecar |
| | `produces_events` | an event generator: its identity is the seed basis, and its `[outputs] sidecar` is its sidecar |
| | `config_file`, `config_always` | its table's `config` and consumed quantities go to `config/<tag>.toml`, its first argument (exec, module); `config_always`: even when empty (module) |
| | `template` | `true`: `heimdall tools new <name> --from <it>` copies the folder (exec, module); any other is extended |
| | `formerly` | the folder's old names (`exec`: `["custom"]`): a table naming one is told the new name, and `heimdall migrate` rewrites it |
| | `packages` | the recipes whose installs it runs (`sherpa`: `["sherpa"]`; `pythia`: `["pythia8", "hepmc3"]`): `heimdall tools` shows how each is installed, a missing program names them with `bifrost -b`/`-c`, provenance records them (`tools.package_states`; never identity, which the binary's sha256 is) |
| `[card]` | `style` | `append` (base cards then the point card: last wins), `render` (`render.py` writes the whole card), `none` (no card; values become flags or options) |
| | `ext`, `comment` | the card's extension and comment marker (`cmnd`, `!`) |
| | `bools` | how true and false are written (default `["true", "false"]`; Pythia `["on", "off"]`) |
| | `line` | one value's line (default `"{key} = {value}"`; `"set {key} {value}"` for ThePEG and Tcl) |
| | `footer` | lines after the values (placeholders `{output_name}`, `{tag}`, `{input}`); a line whose placeholders are all empty is left out |
| | `seed`, `seed_parallel` | seed lines, after everything (`{seed}`; `{seeds}`, the block, only at threads > 1) |
| | `seed_range` | `[lo, hi]`: the seeds the tool accepts (default `[1, 900_000_000]`, Pythia's); a point's seeds come from the intersection over its seeded steps |
| | `merge`, `repeatable`, `owned` | `merge = true`: the combined card holds each key once, parsed with the folder's `line`; `repeatable`: commands kept every time (Pythia's particle-data `onIfMatch`, …); `owned`: keys the runner sets |
| | `drop`, `trailing`, `drop_inside_braces` | how the combined card leaves out a base card's comments: `drop` a full-line comment (a regex; default: a line starting with `comment`), `trailing` a comment after a value, `drop_inside_braces = false` keeps comment-looking lines inside `{ … }` (Tcl) |
| `[command]` | `argv` | the argv template; default `["{exe}"]` |
| | `display` | argv pieces that change only how the tool prints its progress, appended after the identity took the argv: **never in the identity**, so they may not change what the tool makes (Sherpa's `BATCH_MODE`, V156) |
| | `env` | extra environment (`RIVET_ANALYSIS_PATH = "{work}/build/Rivet"`) |
| | `cwd` | where it runs (default the point's output directory; Whizard: `{prepared}`) |
| `[options]` | `<key> = { kind, required, flag, default }` | the tool-specific keys a table may carry; `kind` is `list`, `table`, `str`, `int`, `float`, `bool` or `flag` (`flag = "-e"`, `default`); every option is also a placeholder |
| `[outputs]` | `products` | the kinds it writes (for reading) |
| | `event_count` | how a count is read back: `yoda:<path>` (a counter's entries), `json:<key>` (the product's report), `root:<tree>` (a tree's entries) |
| | `sidecar` | where a producer's sidecar is (`"{output}.json"`) |
| | `written` | `"requested"`: it always makes what it is asked for or fails, so the runner writes the sidecar after exit 0 |
| | `combines` | product suffixes this folder merges for `combine`: `["yoda"]` in `merge` |
| | `deal` | `true`: its `{outputs}` may hold a deal group (`A+B+C`: each event to one member), so it can feed a sharded tool; its sidecar must then carry `written_per_output` |
| `[prepare]` | `argv` | the prepare step (`{work}`, `{exe}`, `{card}`, `{prepare_card}`, `{prepared}`, `{out}`), run in the cache entry |
| | `marker` | a file the step must leave; the `.prepared` stamp is written only then |
| | `ignore` | card keys left out of the cache key (`EVENTS`, `n_events`, `seed`) |
| | `key` | `"card"` (default) or `"base"`: key on the base cards only |
| `[context]` | `values` | what the point's context file gives of the tool besides its card and config: a template (`plugin_path = "{work}/build/Rivet"`), or `"identity:<part>"` for a part of its identity (`analyses = "identity:analyses"`) |
| `[context.products.<name>]` | `path` | a product made on demand when `generate_cards` asks for `"<tag>:<name>"`: its path (`{prepared}`, `{card}`), in the tool's table of the context file |
| | `needs_prepare` | asking for it runs the prepare step on demand |
| `[identity]` | `files` | files whose sha256 enters the identity (`{work}`, `{exe}`, `{analysis}`) |
| | `version` | a command whose first line is the version, or `"stack:<name>"` (the stack's, V78), for provenance |
| `[shard]` | `merge` | the tool folder that joins K shards' products into the table's `output_file`; without it, `shards` is refused (rivet: `merge`, i.e. `rivet-merge -e`) |
| `[beams]` | `slots` | the card's fixed beam slots, `["lepton", "hadron"]` (Herwig): the run's per-beam values are reordered into them; without it a tool takes `[beam A, beam B]` as given |
| `[render]` | (free) | data for the folder's `render.py`, handed over as `context["render"]` (MadGraph's `[render.lpp]`, PDG → lpp) |
| `[diagnose]` | `exits` | the exit codes after which the tool is asked again, to say why (V203; pythia: `[3]`, Kit's Init) |
| | `card`, `ext` | the lines of one more card (a file of `ext`), given after its own: messages on, no events |
| | `program` | run in place of its executable, with the same arguments and the card (pythia: `diagnose.py`, one plain Pythia that reads the cards and initialises); without it, the executable again |
| | `quote` | a regex: the matching lines (at most three) are quoted in the failure, "…; asked again: …"; its output's digest is `<tag>.diagnose.log` |
| | `timeout` | seconds (300). Its outputs go to a scratch folder, removed after |
| `[checks]` | `files` | files that must exist at plan time |
| | `card` | argv that reads a card (`{card}`) and prints one JSON line `{"line": N, "text": …}` per line it rejects; run at plan time, cached by the card's text |
| | `info_dirs`, `info_dirs_command` | where analyses' `.info` files are, for C9 |
| | `filled` | `"yoda:<prefix>"`: after the tool, its YODA products' histograms under the prefix with any entry; none filled is a note in the point's block, never a failure (rivet: `yoda:/RAW/`, V195) |

## `render.py`

For a card that is a tree, a script or a launch file. Plain functions, importing only `PLUGINS_MAY_IMPORT`: `card(bases, overrides, context) -> str`; optionally `prepare_card(lines, bases, context) -> str` and `options(extra, targeted, context) -> dict`. The docstrings in `framework/tools/sherpa/render.py` and `rivet/render.py` are the examples.

A value reaches `render.py` through a plain `key` mapping, and the key means what the plugin says (a YAML path for Sherpa). Refuse a base card that sets what the plan owns: seeds, events, outputs, beams. Test with the runner's own `Override` (L26).

**A provider** (`<name>/provider.py`) has no `tool.toml` and one function, `check(form, value, where)`, named by a mapping as `check = "<name>:<form>"`.

## Per point

1. **Options:** extra keys checked against `[options]`; `required` ones present.
2. **Card:** values reaching the tool, each through its `Mapping`: `key`/`keys` become card lines, `flag` argv, `option` an analysis option, `config` a config key, `seed` a replica. Then the header, lines and footer; or `card()`. Seed lines come at `finalise`, after the identity.
3. **Prepare key and argv.**
4. **argv, env, cwd** with every placeholder; a module or exec tool's config file; `$HEIMDALL_CONTEXT` for every tool.
5. **Count check**, if the tool consumes events and reads a count, and its producer has a sidecar.

## Categories

Only when a tool runs and what it reads and writes matter to the runner; `category` is for reading.

| Category | Examples | Role |
|---|---|---|
| Providers | LHAPDF | plan-time checks; no process |
| Process generators | MadGraph, Whizard | per point, writes a file, with a prepare cache |
| Event generators | App_Pythia, Herwig, Sherpa | per point → HepMC; `produces_events` |
| Detector simulators | Delphes | reads a file. Geant4 has no command line: a module with `// requires: geant4` |
| Analysis applications | Rivet, modules | per point → YODA/ROOT, count-checked |
| Visualisation | `yd2rt`, `plotmerge` | and the plot stage |
| Statistics | pyhf, uproot | exec tools; no built-in fitter |
