# Map

Generated: `heimdall make --framework docs`. One line a page: what it holds, who it is for, its size.
`⟵ live:` a live doc changes that page, and wins until crystallised (see `work`).

## rules

- [code](rules/code.md): how code here is written; rules that hold across modules and are not visible from one file (dev agent; 2 KB)
- [invariants](rules/invariants.md): what must never happen in this repo and on this machine, and why; read before acting (dev agent; 2 KB)
- [work](rules/work.md): where work in progress lives; the live-doc format; the crystallise protocol (dev agent; 2 KB)
- [writing](rules/writing.md): how a page is written, where a fact belongs, how anything cites anything (dev agent; 3 KB)

## reference/settings

- [settings-plot](reference/settings/plot.md): every key of [plot], [plot.figures.*], [plot.data], [plot.across_from], [stats]: type, default, accepted values, effect (driver client dev agent; 34 KB)

## stable/guide

- [plots](stable/guide/plots.md): how a run's pages get made, and how to get the ones you want; objects, figures, pages and sets (driver client dev agent; 4 KB)

## stable/internals

- [docs-system](stable/internals/docs-system.md): how the docs are generated and checked; the page model, the map, the drift report, the site (dev agent; 1 KB) ⟵ live: live-reference-format
- [identity](stable/internals/identity.md): what a point's identity hashes, how seeds follow from it, what skips a point and what reruns it (dev agent; 4 KB)

## stable/design/decisions

- [decisions-identity](stable/design/decisions/identity.md): why identity, seeds and skipping work as they do (dev agent; 1 KB)

## live

- [live-reference-format](live/reference-format.md): the settings reference is per-key blocks, plot first; the rest follows in phase 2 (dev agent; 0 KB)
