---
id: data-model
summary: the runner's types, which module owns each, and what each holds
code: framework/runner/config.py, framework/runner/tools.py, framework/runner/sweep.py, framework/runner/plot.py, framework/runner/plotdoc.py
---

# The data model

| Type | Module | Holds |
|---|---|---|
| `Errand` | `config` | the parsed errand file: `path`, `assignment`, `name`, `serial`, `default_configuration`, `configurations`, `prelim`, `static`, `tools`, `quantities`, `plot`, `master_toml`, `raw`, `sweep_runs`, `sweep_list`, `sets`, `included`, `imported`, `meta`, `form` (2 or 3), `stats`, `report` |
| `Configuration` | `config` | one configuration: `key`, `label`, `run_folder`, `serial`, `title`, `description`, `event_count`, `threads`, `parallelism`, `sweeps`, `plot_points`, `combine`, `tools`, `pre`, `post`, `static`, `generate_cards`, `cluster`, `tag`, `serial_auto`, `origins` (where each value came from) |
| `Tool`, `Quantity` | `config` | a table each; a tool's folder-specific keys are in `Tool.extra`; a quantity's `values`, `tags`, `labels`, `styles`, `shape`, `exclude` |
| `Point` | `sweep` | `index` (1-based; −1 pre, 0 post), `name`, `choice` (quantity → value index), `page`, `stage` |
| `Mapping` | `quantities` | how one quantity reaches one tool: `tag`, `form` (`key`, `keys`, `flag`, `option`, `config`, `seed`), `key`, `format`, `analysis`, `check` |
| `Override` | `quantities` | `(key, value, origin)`: what a `render.py` receives |
| `Folder` | `tools` | a tool folder: `name`, `dir`, `spec` (its `tool.toml`), `origin` (`work`, `machine`, `shipped`), `chain` (it, then what it extends) |
| `Interface` | `tools` | `name`, `path`, `kind` (`fifo`, `file`, `product`, `pre`, `points`), `producer`, `readers`, `group`, `shard`; `paths` and `names` for `points` |
| `Step` | `tools` | one tool of one point: folder, group, exe, argv, env, cwd, log, status mode, filters, inputs, outputs, products, sidecar, count check, card lines and paths, config, prepare entry, `identity_parts`, `texts` |
| `PointPlan` | `tools` | one point or stage: `point`, `values`, `out`, `res`, `groups`, `rendered`, `context_tools`, `interfaces`, `consumers`, `identity`, `seed`, `writes`, `context`, `upstream`, `deal` |
| `ToolState`, `Reader` | `status` | what views show per tool; one process's status and output pipes, on a thread |
| `Bus`, `RunBus`, `Hub`, `Journal`, `RunLog` | `events` | the event stream; a run's view of it in a sweep; the watch socket; `status.jsonl`; `run.jsonl` |
| `State`, `PlainView`, `LiveView` | `watch` | the reducer of events, and the views that render it |
| `ToolResult`, `PointResult`, `Stopper`, `Budget` | `execute` | exits, causes, messages; the stop and pause flags; the cores runs share |
| `Figure` | `plot` | one `[plot.figures.<key>]`: `kind`, `type`, `name`, `objects`, `labels`, `table`, and each class's own |
| `Compared` | `plot` | one configuration of a compare figure |
| `Page` | `plot` | one page: name, config path, output, cell, object, document, sources, variants, data, overrides, ranges, merged style, `overlay`, `bands`, `set`, `rel`, `root`, `numbers` |
| `Doc`, `DocConfiguration` | `plotdoc` | a run and its configuration as a drawing reads them from `plot.toml` |
