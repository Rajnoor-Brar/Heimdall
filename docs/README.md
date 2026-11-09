# Heimdall's docs

| You want to | Start at |
|---|---|
| **use** Heimdall on a project | [the model](stable/start/model.md), [a first run](stable/start/first-run.md), [every day](stable/start/everyday.md), then [`guide/`](stable/guide/errand-file.md) |
| **find a setting**: its effect and accepted values | `heimdall explain <key>`, `heimdall docs`, or [`reference/settings/`](reference/settings/plot.md) |
| **set up** a machine, the stack, a toolkit | [a fresh machine](stable/setup/fresh-machine.md), [the stack](stable/setup/stack.md), [toolkits](stable/setup/toolkits.md) |
| **develop** Heimdall | [layout](stable/internals/layout.md), [the runner](stable/internals/runner.md), [`internals/`](stable/internals/run-flow.md), [why: decisions](stable/design/principles.md) |
| **work as an AI in a work dir** | `heimdall context` |
| **work as an AI on Heimdall** | [AGENTS.md](../AGENTS.md), [rules](rules/invariants.md), then [MAP.md](MAP.md) |

`heimdall docs` opens all of this as one searchable page: settings, pages by reader, and a graph of pages, code and decisions.

## How the docs work

| Folder | Holds | Changes |
|---|---|---|
| `rules/` | what binds: invariants, how to write, how work and live docs go | on the developer's word |
| `reference/`, `client/`, `MAP.md` | generated from the code | never by hand: `heimdall make --framework docs` |
| `stable/` | crystallised knowledge, by subject | only when crystallising |
| `live/` | what changed since the last crystallise; it wins over `stable/` | as work lands |

On a conflict: code, then generated, then live, then stable, then plans. One fact has one owner, and `tests/runner/test_docs.py` holds what it can. Rules: [writing](rules/writing.md), [work](rules/work.md).

The old manual is at git tag `docs/pre-rebuild`. Pending work: [.plans/Issues.md](../.plans/Issues.md); what the developer has still to read: [.plans/Notes.md](../.plans/Notes.md).
