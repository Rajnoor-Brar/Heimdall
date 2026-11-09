# Implementation notes, round 1

Written by the implementing agent. Every decision made off the plan, newest last, one bullet each: the date and step id, what was decided, why, and where in the code. The phase files' logs hold each step's state. This file is the list a reader checks first. P7's crystallise report goes under its own heading.

The developer reviews this file at the round's end, and then it leaves `.plans/`: a decision kept goes to a decision note.

## Decisions

- **2026-11-09, all steps: the commit trailer names the model that wrote it** (`Co-Authored-By: Claude Sonnet 5.5`), not the plan's `Claude Opus 5.5`, which would credit a model that did not do the work. The session's own attribution rule says so.
- **2026-11-09, all steps: an audit mark carries the step id, not the short commit** (` · closed 0.5`): a commit cannot hold its own hash, and a second commit per step would cost more than it shows. `git log --grep` on the step finds the commit.

- **2026-11-09, 5 (tab-complete P1–P3): the directive line starts with a colon** (`:plain`, `:nospace`, `:files:<glob>`, `:dirs`), where the plan said the line is `nospace`, `files:…` or `dirs`. A configuration or a Run could be named `dirs`, and bash would take the last candidate for the directive; a colon cannot begin a name. In `complete.answer` and `env/complete.bash`.
- **2026-11-09, 5 (tab-complete P2.4): no live number `[N]` is offered, only ids and pids.** The plan's "Not yet specified" asked whether the registry alone numbers the runs as `heimdall runs` does. It does not: `house.live_entries` numbers a cluster submission by Slurm's `squeue` and counts a run with no entry that only its socket shows. A completion must neither ask a socket nor run `squeue`. So `runs --resume N`, `watch|stop -i N` and `runs --jobs M` complete nothing (they are in `complete.FREE`), and the options that take `ID|N` complete the ids.
- **2026-11-09, 5 (tab-complete P2): `complete.py` never imports `cli`.** `cli.main` passes it the parser (`complete.answer(parser(), argv)`), so a rank-5 module does not cycle with a rank-5 module. The command names the `help` kind offers are set from that parser (`complete.NAMES`). Its rank row is in `runner/__init__.py` now; the stable page's row waits for P7.

## Crystallise
- **2026-11-09, 1.1: `RunState` also holds `shown` and `ended`.** `shown` is the verdict or state the entry wrote, so a free-text verdict (`the runner failed: …`) prints byte-for-byte; `ended` lets the turn rule treat "a finished run in no set" as the plan says. `GIVES_TURN` and `HOLDS` are the plan's sets; `gives_turn` and `holds` apply them. `framework/runner/runs.py`.
- **2026-11-09, 1.1: `--state forgotten` matches the word only.** A paused run that was forgotten is `paused`, `forgotten` is a flag on it (as its text `paused, forgotten` says); only a queued run that left its queue has the word.
