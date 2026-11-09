# Implementation notes, round 1

Written by the implementing agent. Every decision made off the plan, newest last, one bullet each: the date and step id, what was decided, why, and where in the code. The phase files' logs hold each step's state. This file is the list a reader checks first. P7's crystallise report goes under its own heading.

The developer reviews this file at the round's end, and then it leaves `.plans/`: a decision kept goes to a decision note.

## Decisions

- **2026-11-09, all steps: the commit trailer names the model that wrote it** (`Co-Authored-By: Claude Sonnet 5.5`), not the plan's `Claude Opus 5.5`, which would credit a model that did not do the work. The session's own attribution rule says so.
- **2026-11-09, all steps: an audit mark carries the step id, not the short commit** (` · closed 0.5`): a commit cannot hold its own hash, and a second commit per step would cost more than it shows. `git log --grep` on the step finds the commit.

## Crystallise
- **2026-11-09, 1.1: `RunState` also holds `shown` and `ended`.** `shown` is the verdict or state the entry wrote, so a free-text verdict (`the runner failed: …`) prints byte-for-byte; `ended` lets the turn rule treat "a finished run in no set" as the plan says. `GIVES_TURN` and `HOLDS` are the plan's sets; `gives_turn` and `holds` apply them. `framework/runner/runs.py`.
- **2026-11-09, 1.1: `--state forgotten` matches the word only.** A paused run that was forgotten is `paused`, `forgotten` is a flag on it (as its text `paused, forgotten` says); only a queued run that left its queue has the word.
