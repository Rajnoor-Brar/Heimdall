---
id: work
summary: where work in progress lives; the pipeline from audit or spec to a closed round; the live-doc format; the crystallise protocol
---

# Work

## `.plans/`

Only what is open. Finished work leaves: its decisions go to `docs/`, what is still to do to `Issues.md`, what the developer has still to read to `Notes.md`, and git keeps the rest.

| Path | Holds | Lives |
|---|---|---|
| `.plans/Issues.md` | pending work, one issue a task, at most about ten lines each: what, why, done when; a plan's link if it has one; `idea` labels an idea | always |
| `.plans/Notes.md` | what the developer has still to read and is not a task: decisions an implementer made alone, waiting for a yes; facts about the developer's own files; one entry per closed round | always |
| `.plans/audits/<slug>/` | an audit: `00_Index.md` and a file per category, each finding with a check that closes it | until stage 5 |
| `.plans/plans/<slug>/` | a design plan for the developer (stage 2) | until stage 5 |
| `.plans/implementation/` | the one implementation round in progress (stage 3) | until stage 5 |

## The pipeline

Work moves through five stages, in order. Each stage has one output and an exit, and no stage starts before the one before it has exited. Small work (a fix in one commit, with its test) may skip stages 2–3, but still ends in stage 5's state: nothing about it is left in `.plans/` but an issue or a note.

**1. Source.** An audit (§ Auditing) or a spec: an issue, a request of the developer, a prompt file. Exit: each item says what is wrong or wanted, where, and how it would be checked.

**2. Design plan, for the developer.** `.plans/plans/<slug>/00_Plan.md`, with a file per phase.
- **Context:** read from the code with `file:line`, and each inherited claim re-verified. A claim that turns out wrong is said, not dropped.
- **Options** with a recommendation, a **decision log**, **not yet specified** (a precise question, or fog to research at the phase), **Always / Never**, and **Progress**.
- **Gate:** every decision is asked at once, batched, each with a recommendation, with at most one more gate for the questions that depend on its answers. Assumptions are listed beside the questions, so the developer can correct them.
- Exit: the developer's approval, recorded in the plan's header with the date.
- When the source is an audit and the work needs no design of its own, stages 2 and 3 are one session: the gate is asked while writing the round, and its answers head the round's `00_Plan.md`.

**3. Implementation round, for an agent that cannot ask.** `.plans/implementation/`, one round at a time.
- `00_Plan.md` holds:
  - **The gate:** the answers, and the assumptions that stand.
  - **Found while planning:** what the code showed against the sources.
  - **The execution map:** phase, verified when, blocked by, size.
  - **How a step is done**, the **stop rule** (what to do when a check fails outside the step's scope: an Implementation_Issues entry, the step `blocked`, the work going on), a **decision log**, **Always / Never** and **Progress**.
  - **The ledger:** every item of every source file, one file at a time, mapped to a step, to `Postponed.md`, or to closed.
- `P<n>_<name>.md`: steps sized XS–M, each with its acceptance, its files, its named check (an exact command), the seam it is tested at, `Blocked by:` and a log.
- `Implementation_Notes.md`: each decision made off the plan, with its date, step, why and where. `Implementation_Issues.md`: each finding left open, with its output and what it blocks. `Postponed.md`: each item read and not built, and why.
- **Decision-complete:** nothing in the round may need the developer mid-run. A step's ask-first item is settled at stage 2's gate or is not in the round.
- **While it runs:** the source files are marked as their items close (` · closed <step>` beside a finding's heading, ` · ripe to clear` beside the title of a file whose every item is homed). One concern a commit, its live doc in the same commit, a test that fails on the old code first.
- Exit: every step done or `blocked`, Progress current, the round's one report given.

**4. Review, by a session that did not implement.**
- Read `Implementation_Notes.md`, `Implementation_Issues.md` and the phase logs, then every code commit's diff, the riskiest first.
- Run the fast suite and then the full suite, each alone, at this commit, whatever the round's logs say.
- Probe each claim a test cannot show: a command against the fixture work dir, an input the round's tests did not try.
- A test that fakes the very thing it claims (a relaunch, the shell's own word splitting, a live socket) leaves that thing unproven: say so.
- Say what else ran on the machine while the suite did (a user's run, a watch): tests that list live runs see it.
- A finding is kept only when the code or a run proves it, with its `file:line` or the output.
- Exit: a verdict, either a defect list with each defect proven, or clean.

**5. Close: consolidate and clear.** One commit, after the review.
- **A decision of `Implementation_Notes.md`** is already stated in docs: in a live doc's **Decisions**, or as a decision note once crystallised. If it is not, the close writes it in its live doc first. One the developer has not yet said yes to also goes to `Notes.md`, naming where docs state it.
- **`Implementation_Issues.md`, `Postponed.md` and the review's findings** go to `Issues.md`. An item that overlaps an issue is a line in it, and each other item is an issue of its own, with an id. Sweeps not yet run make one issue between them.
- **Issue ids:** an id cited by an issue that has closed is corrected.
- **The round's record:** a `Notes.md` entry holding its commits, what it built, the suite's counts at the review, and the review's verdict.
- **Deleted:** the round's folder, and every source plan and audit the ledger homed. A file that still holds an unhomed item stays, with its mark.
- Exit: `.plans/` holds `Issues.md`, `Notes.md` and only what is still open; `test_docs` resolves both files' links.

## Live docs

`docs/live/<slug>.md`, one per feature or change, in the same commit as the code or at the phase's commit:

```
---
id: live-<slug>
summary: one line
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

An audit reads the code, not the docs, and repeats its sweeps from the checkout: definitions against references, CLI options against what reads them, schema keys against the runner, markers such as "retired" or "for now". Its findings go in `.plans/audits/<slug>/`, each open one with a severity, a verdict (confirmed by reading or running, or plausible), the issue it overlaps and a check that would close it. An audit is stage 1: it changes no code.
