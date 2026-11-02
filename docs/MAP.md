# Map

Generated: `heimdall make --framework docs`. One line a page: what it holds, its size.
`⟵ live:` a live doc changes that page, and wins until crystallised (see `work`).

## rules

- [code](rules/code.md): how code here is written; rules that hold across modules and are not visible from one file (2 KB)
- [invariants](rules/invariants.md): what must never happen in this repo and on this machine, and why; read before acting (2 KB)
- [work](rules/work.md): where work in progress lives; the live-doc format; the crystallise protocol (2 KB)
- [writing](rules/writing.md): how a page is written, where a fact belongs, how anything cites anything (3 KB)

## reference

- [commands](reference/commands.md): every heimdall command and its arguments (18 KB)
- [keys](reference/keys.md): every setting in one line each, for grep: key, type, default (10 KB)
- [legacy](reference/legacy.md): the errand file's older (v2) names and today's (2 KB)

## reference/settings

- [settings-cluster](reference/settings/cluster.md): every key of [cluster], for running a job on Slurm (4 KB)
- [settings-errand](reference/settings/errand.md): every key of an errand file's [file], [errand], [cfgs.*] and [quantities.*]: type, default, values, effect (20 KB)
- [settings-plot](reference/settings/plot.md): every key of [plot], its figures, data and runs together, and [stats]: type, default, values, effect (28 KB)
- [settings-report](reference/settings/report.md): every key of a report's recipe: [report] and [[report.section]] (9 KB)
- [settings-stack](reference/settings/stack.md): every setting of the stack's build: what is built, with what, how many cores, nested as the file nests them (6 KB)
- [settings-style](reference/settings/style.md): every style key a page may set in [plot.style] or a style file, nested as the file nests them (6 KB)
- [settings-tools](reference/settings/tools.md): every key of a [tools.<name>] table, and each standard tool's own options (5 KB)

## stable/guide

- [outputs](stable/guide/outputs.md): what a run writes and where: records, results, reports, cache; what is kept; what may be deleted (3 KB)
- [plots](stable/guide/plots.md): how a run's pages get made, and how to get the ones you want; objects, figures, pages and sets (4 KB)

## stable/internals

- [build](stable/internals/build.md): make, heimdall build, the rules, // requires:, the flag cache, and what rebuilds what (4 KB)
- [caches](stable/internals/caches.md): the prepare cache: what it keeps, its key, what counts as a hit (2 KB)
- [connections](stable/internals/connections.md): how tools connect: FIFOs, files, products, the rules checked at plan time, the context file, sharding (3 KB)
- [cxx-kits](stable/internals/cxx-kits.md): writing C++ here: Module.hh, integrated programs, Status.hh and the status protocol, heimdallkit (6 KB)
- [data-model](stable/internals/data-model.md): the runner's types, which module owns each, and what each holds (3 KB)
- [docs-system](stable/internals/docs-system.md): how the docs are generated and checked; the page model, the map, the drift report, the site (2 KB)
- [events](stable/internals/events.md): how a tool's status reaches the views: pipes, filter rules, digests, the event stream and its listeners, the views (6 KB)
- [extending](stable/internals/extending.md): how to add a standard tool, a plot backend or a figure class, and what each must touch (3 KB)
- [failures](stable/internals/failures.md): how a chain of processes fails and how each way is handled; attribution; exit codes (2 KB)
- [identity](stable/internals/identity.md): what a point's identity hashes, how seeds follow from it, what skips a point and what reruns it (4 KB)
- [layout](stable/internals/layout.md): Heimdall's folders, the machine root's and a work dir's; what is in git; how the roots are found; where a run's files go (5 KB)
- [live-runs](stable/internals/live-runs.md): a run as a worker and a client; the run registry; signals, pausing, resuming, heimdall watch and stop (4 KB)
- [paint](stable/internals/paint.md): Paint inside: the order of a page's arithmetic, drawing, heat maps, dumps; what is load-bearing (4 KB)
- [plot-backends](stable/internals/plot-backends.md): how the backends beside Paint draw the same pages, what they honour and refuse (2 KB)
- [plot-stage](stable/internals/plot-stage.md): the plot stage inside: members and stand-in plans, the merged sweep, page documents, drawing, what a record gives a drawing (5 KB)
- [provenance](stable/internals/provenance.md): what a run records and where: provenance.json, attempts.jsonl, points.json, tag, identity.json (2 KB)
- [run-flow](stable/internals/run-flow.md): a run from command to pages: planning, one point, scopes, points at once, several runs, combine, and where each check lives (5 KB)
- [runner](stable/internals/runner.md): the runner's modules and ranks, what each owns, what plugins may import; the C++ files and what each links (8 KB)
- [testing](stable/internals/testing.md): the test suites, how they isolate themselves, the gates, and what holds the docs (3 KB)
- [tool-contract](stable/internals/tool-contract.md): what a tool folder holds, the search path, every tool.toml section and key, render.py, providers, and what the runner does per point (10 KB)

## stable/design/decisions

- [decisions-architecture](stable/design/decisions/architecture.md): why Heimdall is shaped as it is: processes, one flat runner, no libraries, where things live (3 KB)
- [decisions-chain](stable/design/decisions/chain.md): why tools connect and run as they do: FIFOs, stages, shards, context files, tool folders (2 KB)
- [decisions-errand-file](stable/design/decisions/errand-file.md): why an errand file is read as it is: forms, imports, vars, defaults, paths (3 KB)
- [decisions-identity](stable/design/decisions/identity.md): why identity, seeds and skipping work as they do (1 KB)
- [decisions-plots](stable/design/decisions/plots.md): why plots and figures work as they do: backends, labels, sets, plot documents, statistics (5 KB)
- [decisions-quantities](stable/design/decisions/quantities.md): why sweeps, quantities and points work as they do (2 KB)
- [decisions-reports](stable/design/decisions/reports.md): why heimdall report works as it does (1 KB)
- [decisions-run](stable/design/decisions/run.md): why a run behaves and records as it does: views, records, logging, pausing, the registry (3 KB)
- [decisions-stack](stable/design/decisions/stack.md): why the stack is built as it is: recipes, toolkits, the conda base, the machine root, images, the cluster (3 KB)

## stable/design

- [glossary](stable/design/glossary.md): Heimdall's words beyond the model's core vocabulary; the core ones are in the model page (2 KB)
- [history](stable/design/history.md): where Heimdall came from, in a dozen lines (1 KB)
- [principles](stable/design/principles.md): the principles behind Heimdall's shape, each with what it buys and what it costs (4 KB)
- [refused](stable/design/refused.md): what Heimdall deliberately does not do, and why (1 KB)
