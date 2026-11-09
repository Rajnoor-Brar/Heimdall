# Implementation notes, round 1

Written by the implementing agent. Every decision made off the plan, newest last, one bullet each: the date and step id, what was decided, why, and where in the code. The phase files' logs hold each step's state. This file is the list a reader checks first. P7's crystallise report goes under its own heading.

The developer reviews this file at the round's end, and then it leaves `.plans/`: a decision kept goes to a decision note.

## Decisions

- **2026-11-09, all steps: the commit trailer names the model that wrote it** (`Co-Authored-By: Claude Sonnet 5.5`), not the plan's `Claude Opus 5.5`, which would credit a model that did not do the work. The session's own attribution rule says so.
- **2026-11-09, all steps: an audit mark carries the step id, not the short commit** (` · closed 0.5`): a commit cannot hold its own hash, and a second commit per step would cost more than it shows. `git log --grep` on the step finds the commit.

- **2026-11-09, 5 (tab-complete P1–P3): the directive line starts with a colon** (`:plain`, `:nospace`, `:files:<glob>`, `:dirs`), where the plan said the line is `nospace`, `files:…` or `dirs`. A configuration or a Run could be named `dirs`, and bash would take the last candidate for the directive; a colon cannot begin a name. In `complete.answer` and `env/complete.bash`.
- **2026-11-09, 5 (tab-complete P2.4): no live number `[N]` is offered, only ids and pids.** The plan's "Not yet specified" asked whether the registry alone numbers the runs as `heimdall runs` does. It does not: `house.live_entries` numbers a cluster submission by Slurm's `squeue` and counts a run with no entry that only its socket shows. A completion must neither ask a socket nor run `squeue`. So `runs --resume N`, `watch|stop -i N` and `runs --jobs M` complete nothing (they are in `complete.FREE`), and the options that take `ID|N` complete the ids.
- **2026-11-09, 5 (tab-complete P2): `complete.py` never imports `cli`.** `cli.main` passes it the parser (`complete.answer(parser(), argv)`), so a rank-5 module does not cycle with a rank-5 module. The command names the `help` kind offers are set from that parser (`complete.NAMES`). Its rank row is in `runner/__init__.py` now; the stable page's row waits for P7.
- **2026-11-09, 1.1: `RunState` also holds `shown` and `ended`.** `shown` is the verdict or state the entry wrote, so a free-text verdict (`the runner failed: …`) prints byte-for-byte; `ended` lets the turn rule treat "a finished run in no set" as the plan says. `GIVES_TURN` and `HOLDS` are the plan's sets; `gives_turn` and `holds` apply them. `framework/runner/runs.py`.
- **2026-11-09, 1.1: `--state forgotten` matches the word only.** A paused run that was forgotten is `paused`, `forgotten` is a flag on it (as its text `paused, forgotten` says); only a queued run that left its queue has the word.

## Crystallise

Done 2026-11-09 against `docs/stable/CRYSTAL.toml`'s commit; `heimdall docs --drift` names no page after it. Every live doc was read, its claims checked against the code where the page's own tests or a grep could, and merged by rewriting. The 25 live docs are deleted; `README.md` stays.

**Merged where**
- `stats-core`, `stats-catalogue`, `stats-measured-bins`, `statistics-format`, `score-engine`, `score-settings`, `scoring`, `stats-rms`: `guide/plots-statistics.md` rewritten whole (the table and its sidecar, the metrics, `[stats]`, `[score]`, the score's three steps, the summary's sections, `heimdall score`), `guide/reports.md` (the `stats` names), `internals/plot-stage.md` (`measured`), `internals/layout.md` and `internals/extending.md` (`framework/stats/`, registries).
- `set-merge`: `guide/plots-sets.md` (a section on `merge`). `across-axes`, `run-labels`: `guide/plots-across.md` (`@key` axes, `unset`, the serial); `heimdall diff`: `guide/housekeeping.md`. `plot-doc-tags`: `guide/plots.md`. `no-yoda-backend`: `internals/plot-backends.md`, `guide/plots-style.md`, `internals/extending.md`, `internals/layout.md`.
- `run-state`, `runs-listing`, `live-parallelism`, `resume-record-config`, `run-queue`: `internals/live-runs.md` (rewritten), the new `internals/run-queue.md`, `internals/run-flow.md`, `guide/sweeps.md`, `guide/watching.md`. `show`: `guide/failures.md`. `record-formats`: `internals/provenance.md`, `guide/housekeeping.md`. `points-library`: `internals/identity.md`, `internals/provenance.md`, `guide/outputs.md`, `guide/scale.md`. `tab-complete`: `setup/environment.md`. `identity-golden`, `shadow-root`: `internals/testing.md`, `internals/identity.md`. `himinbjorg`: the glossary and 24 stable pages, "machine root" becoming Himinbjorg.
- `internals/runner.md`'s rank table gained `library` 3, `scorecmd` 4, `complete` 5 and `diffcmd` 5.

**Dropped, and why**
- `stats-rms`: superseded by `scoring` (its `rms` rows are `[score].mean`). The top five, the scoreboards, places and points, the win rate and the six fixed panels left `plots-statistics.md`: the code no longer has them (F-7).
- The yoda backend's section of `plot-backends.md`, and "frozen" in `extending.md`: the code is gone.
- `score-settings`'s "the summary, the report and the CLI do not use it yet": `scoring` says they do.
- From `plots-statistics.md`, the formula-level wording of the old five columns beyond the column table: the metrics' own notes (`heimdall explain score.<name>`) are the owner.

**Not checked.** Step 4 (each `--drift` page against its code) was done for the pages this round touched: `--drift` is clean, and the docs tests hold the cited paths, links, ranks and sizes. A page this round did not touch was not re-read against its code.

**Decision ids given:** V235 resume from the snapshot; V236–V243 run (queue, waiter, entry and state values, free-text verdict, listing, `--jobs`, `show`, record format); V244–V246 identity (golden mask, library key and settings); V247–V250 architecture (`HEIMDALL_MACHINE`, shadow Himinbjorg, TAB); V251–V262 plots (scoring and statistics, merge, across, plot document, backends, labels, `stats` retired). V28, V75, V176, V177, V10 and V220 carry a pointer to their replacement.

One edit outside docs: `framework/stats/means.py`'s `rms` note cited `docs/live/stats-rms.md`, which crystallising removes; the note's text lost that parenthesis (own commit).

## Checklist: every item of `.plans/` that is implemented

Written at the round's end, 2026-11-09. `[x]` is built and verified by the check its step names (the full suite's counts are in P7's log); a hash is the commit. The deleted files are in git at `7bed373` (`.plans/plans/…`, `.plans/audits/2026-11-08-code/`). What the round left is in [Postponed.md](Postponed.md), and the three findings it made are I-129 to I-131.

**This round's steps**
- [x] 0.1 planning committed (`7bed373`) · 0.2 `work.md` row (`f1b33d3`) · 0.3–0.4 the old Implementation files folded (`08d1863`) · 0.5 I-25 corrected (`08d1863`)
- [x] 1.1 `runs.RunState` (`4ee46cb`) · 1.2 and 1.3 `runs.RunEntry`, the readers' attributes (`bb86f34`) · 1.4 `runs.VERSION = 2` (`c45a555`) · 1.5 free-text states, checked, fine
- [x] 2.1 `cli.others_of` (`a8a2a31`) · 2.2 unused constants (`a8a2a31`) · 2.3 one point state (`60974d0`) · 2.4 `plot.py` re-exports (`40ab3de`) · 2.5 `log` and `show` options once (`39eef9b`) · 2.6 a sweep test's comments (`f45dfbe`) · 2.7 a pid's start time without `/proc` (`4c85f1c`)
- [x] 3.1 the points library is one module, `runner/library.py` (`e782866`)
- [x] 4.1 `heimdall runs --resume-queue` (`7b4ad72`)
- [x] 5 TAB completion, the tab-complete plan's P1–P4 (`31e2f2e`)
- [x] 6.1 and 6.2 the known reds named (`06d4e80`) · 6.3 `test_detach` fixed at its cause (`c664872`)
- [x] 7.1 crystallise (`794bd12`; with `6f27bbe` and `8ac8035`, the two edits it found outside docs)
- [x] 8.1 `ISSUES.md` (`8f0965e`) · 8.2 what is homed, deleted · 8.3 the round closed

**Plans folders, built before this round and now deleted with their decisions in `docs/stable/design/decisions/`**
- [x] `stats-backend` phases 1–8: Paint's measured bins, the stats core, the catalogue (27 metrics, 22 means), the table and sidecar, the engine, the summary, marginals and baselines, `heimdall score` (V251–V256, V262)
- [x] `points-library` phases 1–5: the probe, the key, the layout, the setting, the commands (V245, V246)
- [x] `tab-complete`: all four phases (V249, V250)
- [x] The plans of 2026-11-07 named by the old order line: safety net, retire the yoda backend (V260), set-merge (V257), across-axes (V258), run labels (V261), live-runs UI (V238–V243), names

**Audit findings closed:** R-1, R-2, R-3, R-6, R-9 · D-3, D-5, D-6, D-8 · S-3 · G-1, G-3, G-8 · O-3, O-6, O-7 · E-1 (the requeue) · T-1, T-6 · P-1 to P-6. Every other finding is in Postponed.md.

**Not implemented, by decision:** one dialect (D-1, I-20, I-21) and what rides with it; the retirement dates (R-4, R-5, O-8); D-2, D-4, D-7; S-1, S-2, S-4 to S-8; G-2, G-4 to G-7; O-4, O-5, O-9, O-10; E-2 to E-9; T-2 to T-4; every audit sweep. The held items of stats-backend and points-library.

