---
id: paths
summary: how a path in an errand file resolves, how a Run's folder is named, and every placeholder
code: framework/runner/paths.py, framework/runner/tools.py
---

# Paths and placeholders

## Paths

Every key that takes a path has one convention root. There is no search path and no fallback. Roots are the work dir's, found by walking up from here, never the working directory itself.

| Written as | Resolves to |
|---|---|
| `name`, `sub/name` | the key's root, below |
| `./sub/name` | the work dir + `sub/name` |
| `/abs/path` | as written |
| `../x`, `a/../b` | an error: write `./…` or an absolute path |

| Key | Root of a bare name | Example |
|---|---|---|
| `heimdall run <config>`, `heimdall plot <config>` | `configs/`, `.toml` optional | `Demo/jets` |
| `[file].master`, `.import`, `[tools.*].card`, `.filters`, `[plot].root_style` | the folder of the file naming it. An import's `<A>/<E>` is from `configs/` | `ep.cmnd` |
| `[tools.*].executable` | `build/<A>/`, which must exist; `path:<command>` asks for a command on `PATH` | `Decay.exe`; `path:python3` |
| `[tools.*].input` | a tool table's name, another tool's `output`, a pre product; else under the point's folder | `"pythia"` |
| `[tools.*].output` | a FIFO or scratch file: the point's working folder. Anything else: the point's results, a product | `jets.yoda` |
| `[plot.data].file` | `datasets/`, or `rivet:<Analysis>` for Rivet's own | `rivet:ZEUS_2012_I1116258` |

**The one judgement:** what a tool writes is a product unless it is technical, a FIFO or a scratch file (`keep = false`). So a HepMC file kept for another configuration is a product: leave `keep` out.

## A Run's folder

`<E>` is `[errand].name`, or the configuration's `name`. `<R>` is `NN_<folder>`, `<folder>` being the configuration's `folder`, or its table key. `<point>` is the varied tags joined by `_` in `vary` order, or `point`.

**The serial `NN`** is where results go, never part of an identity:

- **Left out**, the runner numbers it: the newest folder whose points were made from the configuration as it stands, or an older one when a change was undone; when nothing there was made yet, the newest; otherwise a new number. So a changed configuration never overwrites what it made. `--plan` says which and why.
- **Set** (`serial = 3`), the folder is yours. A run that would overwrite points made there from other inputs is refused, with the bump as the hint. `--rerun` overwrites them, and `--why` says what changed.

Two configurations of a file may not write one folder. Deleting a configuration's `logs/` or `.cache/` reruns nothing; deleting its `points/` makes every point "to run". A point another session is running is skipped, naming who, unless `--wait`.

## In argv, cards and `arguments`

`{{` and `}}` are literal braces. An argument that is exactly one list-valued placeholder is spliced. An unknown placeholder is an error with the nearest name.

| Placeholder | Is |
|---|---|
| `{work}`, `{heimdall}`, `{apps}` | the work dir; Heimdall; the compiled apps |
| `{exe}`, `{config}`, `{arguments}` | the tool's executable; its config file; its `arguments`, expanded |
| `{out}`, `{res}` | the point's working folder and results |
| `{input}`, `{inputs}`, `{named_inputs}`, `{in:<name>}` | the first input; every input (post: that product of every point); post's `<point>=<path>`; an input by name |
| `{file:<name>}` | a FIFO or scratch file of the point |
| `{input_sidecar}` | the first input's sidecar, only when its producer ran in an earlier group |
| `{output}`, `{outputs}`, `{partial:output}`, `{output_name}` | the first output's final path; every output's; its partial name, renamed after the checks; its file name |
| `{q:<quantity>}` | the point's value of an active quantity |
| `{threads}`, `{events}`, `{seed}` | the configuration's; the point's seed, filled in last |
| `{display_every}` | events between progress lines: a thousandth of the count, at least 100 |
| `{cards}`, `{card}` | the base cards then the point card; the combined card |
| `{analyses}` | rivet: `-a <analysis[:options]>` for each |
| `{prepared}`, `{prepare_card}` | the prepare cache entry; the card its step reads |
| `{context}`, `{context:<tag>.<key>}` | the point's context file; one value of it |
| `{points}` | pre and post: `points.json` |
| `{<option>}` | every key of the folder's `[options]` |

`{var:name}` is a `[file.vars]` value, replaced when the file is read, before any of these.

## In page texts

Titles, `legend_header`, axis labels, `[plot.data].legend`, a figure's `labels`, quantities' `labels` and the `.plot`'s own may cite the points. A page text's placeholder must have one value across the page's curves; a curve label's is its own point's. A name the points lack is refused at plan time.

| Placeholder | Is |
|---|---|
| `{cell}` | the page's `plot_points` values, joined |
| `{q:<quantity>}` | the label of the quantity's value at the point |
| `{opt:NAME}`, `{opt:<analysis>:NAME}` | Rivet's: the analysis option at the point |
