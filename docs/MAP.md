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

- [plots](stable/guide/plots.md): how a run's pages get made, and how to get the ones you want; objects, figures, pages and sets (4 KB)

## stable/internals

- [docs-system](stable/internals/docs-system.md): how the docs are generated and checked; the page model, the map, the drift report, the site (2 KB)
- [identity](stable/internals/identity.md): what a point's identity hashes, how seeds follow from it, what skips a point and what reruns it (4 KB)

## stable/design/decisions

- [decisions-identity](stable/design/decisions/identity.md): why identity, seeds and skipping work as they do (1 KB)
