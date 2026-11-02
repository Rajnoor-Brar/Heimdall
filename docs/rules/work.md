---
id: work
summary: where work in progress lives; the live-doc format; the crystallise protocol
for: dev agent
---

# Work

## `.plans/`

Only what is open. Finished work leaves: its decisions and live doc stay in `docs/`, and git keeps the rest.

| Path | Holds |
|---|---|
| `.plans/ISSUES.md` | pending work, one issue a task, at most about ten lines each: what, why, done when; a plan's link if it has one; `idea` labels an idea |
| `.plans/plans/<slug>/` | a plan in progress: `00_Plan.md` with an execution map, and a file per phase with its tasks, checks and log |
| `.plans/audits/<slug>.md` | an audit with findings still open |

## Live docs

`docs/live/<slug>.md`, one per feature or change, in the same commit as the code or at the phase's commit:

```
---
id: live-<slug>
summary: one line
for: dev agent
affects: identity, plots
issue: I-123
---
```

Then only these, each short: **Now holds** · **No longer holds** · **Decisions** (notes with new ids) · **Stable pages need**. State, not steps. A fact code owns goes in code, not here.

A live doc wins over the stable pages it `affects` until crystallised, and `MAP.md` shows the overlay.

## Crystallising

Only on the developer's explicit order.

1. Run `heimdall docs --drift`, and read every live doc.
2. For each claim, verify it against the code, then merge it into the page that owns it, rewriting rather than appending. Drop what the code no longer bears out, and say so in the report.
3. Move decision notes into their area files.
4. For each page `--drift` names, check it against the code it describes.
5. Delete the live docs, keeping `live/README.md`. Set `commit` in `stable/CRYSTAL.toml` to the commit crystallised against.
6. Regenerate, run the docs tests, commit as one. Report what merged, what was dropped and why.

## Auditing

An audit reads the code, not the docs, and repeats its sweeps from the checkout: definitions against references, CLI options against what reads them, schema keys against the runner, markers such as "retired" or "for now". Its findings go in `.plans/audits/`, each open one with a check that would close it.
