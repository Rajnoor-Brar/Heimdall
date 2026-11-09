# Implementation round 1: clean-up and core · done, ripe to clear after the developer's review

Status: planned 2026-11-09, approved at the gate the same day; not started. Implement on the developer's order to start the round.

The round works through `.plans/` one file at a time and one item at a time. Each item is built here (a step below), already closed, or written into [Postponed.md](Postponed.md) for a later round. The [ledger](#ledger-every-item-of-plans) maps every item to one of these. When a file's items are all homed, it is marked, then deleted at [P8](P8_clear.md).

The implementing agent cannot ask. Every decision is below. A surprise is handled by the [stop rule](#when-something-does-not-fit).

## The gate (developer, 2026-11-09)

| Question | Decided |
|---|---|
| Scope | Clean-up and core: `.plans/` housekeeping; R-1, R-2, R-3, R-9, D-3, T-6, O-7; G-1 run state as a value, with G-3 `RunEntry` and O-6's version (all in `runs.py`); S-3 one library module; tab-complete (I-73); O-3 one command that requeues a queue lost to a reboot |
| Stable docs | A crystallise at the round's end (work.md's protocol), with the rank-table rows the new modules need |
| Known reds | I-79's two gates are strict xfails, the conda-root test is skipped on a conda root, `test_detach` is investigated |
| Held items | stats-backend and points-library folders are deleted; their held items go to Postponed; the implementer's other off-plan decisions of 2026-11-07/08 are accepted as they stand |

**Assumptions shown before the gate and not corrected (they stand):**
1. The planning work is committed first, so git keeps every file before anything is cleared.
2. `work.md` gains a row for `.plans/implementation/`. The top-level `Implementation_Notes.md` and `Implementation_Issues.md` are folded, then deleted.
3. Tab-complete's D3 (dynamic names) and D5 (`gjallarhorn <title>` left out) are decided as proposed.
4. D-1 (one dialect) gets its own planning session. It is first in Postponed, with the snapshot question.
5. D-2, O-4, O-9, every expansion but E-1, and every audit sweep not yet run go to Postponed.
6. R-3 and R-9 are done as narrowed (below).
7. `ISSUES.md` closes I-120, I-121 and I-73, I-25 is corrected, and the order line is rewritten.
8. A source file is marked when it empties, and deleted once committed.

## Found while planning (verified at `57b62ef`)

- **R-3 is overstated.** One definition of a point's state exists, `record.state_of` (`record.py:551`), and `house.status` uses it. `house.point_state` (`house.py:1047`) is a one-line wrapper that only `tests/runner/test_lifecycle.py` calls.
- **R-9 is half wrong.** `runner/statstable.py` is not only a re-export: it holds the bar graphs and the summary. Its re-export of `stats.table` is also the runner's one sanctioned door into `stats` at module level (`test_imports.py`'s exception, `Implementation_Notes` 2026-11-07, phase 4). So only `plot.py`'s two re-export lines go, and statstable's stays by design.
- **D-1 has a cost the audit did not name.** A Run's snapshot (`records/…/<R>/config/`, `record.write_snapshot`) is the errand file as written: v2 for every older Run. `plot`, `status`, `runs --resume` and `--again` read it (`record.record_of`, `cli.resume_snapshot`). A loader that refuses v2 breaks every old record, unless a snapshot reader stays or the records are migrated, which writes into work dirs. This is why D-1 is a planning session of its own (Postponed, first).
- **G-1 has a latent miss.** `runs.finish(…, "forgotten")` gives the state `forgotten`, which is not in `house.RUN_STATES`, so `runs --state forgotten` is refused. A verdict such as `exit 3` or `not run: <message>` has a first word that is not a state either.
- **Code may not cite an issue.** `test_docs.py:275` refuses `I-<n>` and `.plans/` anywhere in code and tests. So an xfail reason says what it waits for in words, never `I-79`.
- **Plan headers lag.** `stats-backend/00_Plan.md` says "not started", though every phase is done. Its decisions and points-library's are already in `docs/live/scoring.md`, `score-*.md`, `stats-*.md` and `points-library.md`, so the folders can go without loss.

## Execution map

Test command, from the checkout with the stack loaded (`source gjallarhorn.sh`): `taskset -c 0-5 nice -n 10 python -m pytest -q <files>`. One pytest session at a time. The slow suite and the full suite run alone. The fast suite is `tests/runner -m 'not slow'`.

| # | Phase | Verified when | Blocked by | Size |
|---|---|---|---|---|
| 0 | [Commit, rules, fold the old files](P0_housekeeping.md) | planning work committed; `work.md` lists `.plans/implementation/`; the two old files deleted with every entry homed; docs tests pass | none | S |
| 1 | [Run state as a value](P1_run_state.md) | queue, runs and live tests green; a test rewords a state and the queue behaves the same; no `state_word`; a newer entry is refused | 0 | M, split 1.1–1.5 |
| 2 | [Small fixes](P2_small_fixes.md) | each step's grep and tests; then the fast suite has only the known reds | 0 | S, 7 steps |
| 3 | [One library module](P3_library.md) | `grep "def library_\|adopt_points"` finds one file; library, imports, migrate and golden tests green; the slow library test alone | 0 | M |
| 4 | [Requeue a lost queue](P4_requeue.md) | a test kills every worker of a three-run queue, and one command requeues the two not done | 1 | S |
| 5 | [Tab completion](P5_tab_complete.md) | the tab-complete plan's four phases verified by their own checks | 1 | M |
| 6 | [Known reds](P6_known_reds.md) | the two gates are strict xfails; the conda-root test is skipped there; `test_detach` fixed or a strict xfail with its cause | 0 | S |
| 7 | [Crystallise](P7_crystallise.md) | work.md's six steps done; `docs/live/` holds `README.md` only; the full suite green, alone | 1–6 | L (one commit, by protocol) |
| 8 | [ISSUES and clearing](P8_clear.md) | every source file in the ledger is deleted or carries its mark; `ISSUES.md` closes I-120, I-121, I-73; the order line names the next round | 7 | S |

Frontier at the start: 0. After 0: 1, 2, 3 and 6. Run them in the table's order, risk first: 1 changes when a queued run starts. After 1: 4 and 5. 7 waits on every code phase, because it crystallises their live docs.

**Milestones.** Pause once, at the round's end (after 8), with a short report: what holds now, the crystallise report, and the open Implementation_Issues. There is no other pause. A phase's state goes in its file's log and in Progress below, as each phase lands.

## How a step is done

- **One concern per commit, staged by path.** Never `git add -A` or `-a`, and never `.codex/`. Never push. Each message ends with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- **A behaviour change carries its live doc in the same commit**, in `docs/live/` with work.md's front matter. Prose never restates a flag or a default: it links to the generated reference.
- **A test that proves a fix fails on the old code first.** Say so in the step's log.
- **Mark the source.** When a step closes an audit finding, append ` · closed <step id>, <short commit>` to that finding's heading in its audit file, in the same commit. When every item of a source file is closed or in Postponed, append ` · ripe to clear` to the file's title.
- **Write the log.** Each phase file's log gets the step's state when it lands: commit, what holds, and the check that proved it. Record each off-plan decision in [Implementation_Notes.md](Implementation_Notes.md), and each open finding in [Implementation_Issues.md](Implementation_Issues.md).
- **5k events at most** in any run or test the round adds.

## When something does not fit

- A named check fails, and the fix is inside the step's files and scope: fix it, and note it.
- The fix is outside the step's scope, or it would change a decision above: do not build it. Write an Implementation_Issues entry (what failed, the output, what it blocks), mark the step `blocked` in Progress, and go on with the steps it does not block.
- A test run fails or is interrupted: restore nothing, record the state, go on as above (invariants).
- Never resolve one by touching what the Never list holds.

## Decision log

| # | Decision | Chosen | Why |
|---|---|---|---|
| R1 | Run state's shape | `runs.RunState`, a frozen dataclass: a `word` from `runs.STATES` plus qualifiers. `runs.state()` keeps returning the same text, made from it | Logic compares words, the screen prints text. The text stays byte-identical, so no listing test changes |
| R2 | Registry entries | `runs.RunEntry`, parsed on read. Writers keep writing dicts through `runs.update` | The read side has the 30 optional keys. Writing one field at a time is already safe (`_write` is atomic) |
| R3 | `runs.VERSION` | 2, written by `begin`. An entry of a newer version is listed, never acted on | O-6: an old reader must not act on a meaning it does not know. v1 entries read as before |
| R4 | `statstable`'s re-export | kept by design; only `plot.py`'s re-exports go | The import rule lets runner modules take `stats` only inside functions, and statstable is the sanctioned exception |
| R5 | Library module | `runner/library.py`, rank 3. It imports `record`, and `record` never imports it. The entry's path is `tools.RunFolders`' | No cycle (`test_imports`). What `record` keeps is the marker, lock and seed logic every point passes through |
| R6 | Requeue | `heimdall runs --resume-queue ID\|N` requeues the queue's `lost` runs, in order, each `--queued-to` the one before | Stopped, paused, done and failed runs were ended on purpose or have their own command |
| R7 | xfail reasons | words, no issue id | `test_docs.py:275` refuses `I-<n>` in code |
| R8 | The round's folder at its end | the plan's files are marked ripe for the developer's review. `Postponed.md` stays as the next planning's input | The developer reads the round's notes before they go. Postponed is what the next round starts from |

## Ledger: every item of `.plans/`

One file at a time, one item at a time. "→ Pn.m" is built in that step. "→ Postponed" is in [Postponed.md](Postponed.md). "closed" needs nothing more.

**`Implementation_Issues.md`** (top level): F-2 → Postponed · F-4 → Postponed (with O-9) · F-6, F-7 → P7 · F-9 → P6 · F-11 → Postponed · F-12 → Postponed. The file → deleted at P0.3.

**`Implementation_Notes.md`** (top level): every entry accepted (gate). A decision a reader relies on and no live doc states → that live doc's Decisions, at P0.4. O-10's scoring rules → Postponed. Process history (commits, the baseline run) → dropped, since git holds it. The file → deleted at P0.4.

**`ISSUES.md`:** I-25's text → P0.5 · I-29 (`layout.TILED`) → P2.2 · I-73 → P5 · I-79, I-77 → P6 (marks only, the issues stay open) · I-120, I-121 → closed at P8.1 · the order line → P8.1 · every other issue stays open there (it is ISSUES.md's to hold).

**`plans/prompt.md`:** every line maps to a shipped phase or a dropped row (the 2026-11-07 plan's filter table) → committed at P0.1, deleted at P8.2.

**`plans/stats-backend/`:** phases 1–8 done; decisions in `docs/live/scoring.md`, `score-engine.md`, `score-settings.md`, `stats-*.md` · ⏸ the developer's read of one summary → Postponed · `plot --style-sync` not syncing `[score]` → Postponed · retiring Paint's totals now that Python's equal them → Postponed · `notes/` → deleted with the folder at P8.2 (git keeps them).

**`plans/points-library/`:** phases 1–5 done; decisions in `docs/live/points-library.md` · ⏸ `adopt` on a real work dir → Postponed · `"only"` keeping `logs/` → Postponed · whether `results/` links are still needed → Postponed · `FORMAT` staying 1, and the adopted Run's plot document → Postponed · the folder → deleted at P8.2.

**`plans/tab-complete/`:** → P5, whose last phase deletes it.

**`audits/2026-11-08-code/00_Index.md`:** the leverage list → its items below · the folder (with `sweeps/defs.py`) → deleted at P8.2 once every finding is closed or Postponed.

**`01_dead-and-retired.md`:** R-1 → P2.1 · R-2 → P2.2 · R-3 → P2.3 · R-4 → Postponed · R-5 → Postponed · R-6 → P0.5 (I-25 corrected; plotmerge stays) · R-7 → Postponed (with D-1) · R-8 → Postponed (with D-1) · R-9 → P2.4 · Sweeps → Postponed.

**`02_duplication.md`:** D-1 → Postponed (first) · D-2 → Postponed (decision) · D-3 → P2.5 · D-4 → Postponed · D-5 → P2.3 · D-6 → P1.1 · D-7 → Postponed · D-8 → P3 · Sweeps → Postponed.

**`03_structure.md`:** S-1, S-2 → Postponed · S-3 → P3 · S-4 to S-8 → Postponed · Sweeps → Postponed (the stable rank table's drift goes at P7).

**`04_design.md`:** G-1 → P1.1 · G-2 → Postponed (with D-1) · G-3 → P1.2–1.4 · G-4, G-5, G-6, G-7 → Postponed · G-8 → P1.5 · Sweeps → Postponed.

**`05_oversights.md`:** O-3 → P4 · O-4 → Postponed (decision) · O-5 → Postponed · O-6 → P1.4 · O-7 → P2.7 · O-8 → Postponed (with R-5) · O-9 → Postponed (decision, ask-first) · O-10 → Postponed (decision) · Sweeps → Postponed.

**`06_expansions.md`:** E-1's requeue → P4; its `--queued-to` on a queued run → Postponed · E-2 to E-9 → Postponed.

**`07_tests.md`:** T-1 → P6 (gates, conda root, detach) and P7 (the two docs tests) · T-2, T-3, T-4 → Postponed · T-6 → P2.6 · Sweeps → Postponed.

**`08_process.md`:** P-1 → P8.1 (the order line) · P-2 → P7 · P-3 → P0.2–0.4 · P-4 → P0.5 · P-5, P-6 → P8.2 · Sweeps → Postponed (`docs --drift` is P7's step 1).

## Not yet specified

- P1.3: whether `cli.notify`'s verdict map should read `RunState`. It phrases verdicts for a desktop notice and decides nothing, so leave it unless a test shows a word read back from it.
- P6.3: why `test_detach` fails. This is fog, researched at the step, with the rule written there.
- P7: how long the crystallise takes. It may need a session of its own, and it is still one commit.

## Always / Never

- **Always:** the identity golden file green after every code step; old entries, CSVs and records still read; each phase's live doc in its commit; a test that fails first; the ledger's mark on each item closed.
- **Never:**
  - change `identity_parts`, `seed_basis` or a library key's rule;
  - touch `tests/reference/`;
  - rebuild an app or a plugin;
  - write into a real work dir, or run `adopt` or `migrate --apply` on one;
  - write Himinbjorg's live state outside the tests' shadow;
  - edit a stable page except in P7;
  - name a real study;
  - cite an issue id or `.plans/` in code;
  - push;
  - start anything in Postponed.

## Progress

| Phase | Status |
|---|---|
| Plan | approved 2026-11-09 |
| 0 | done 2026-11-09 (0.1–0.5) |
| 1 | done 2026-11-09 (1.1–1.5) |
| 2 | done 2026-11-09 (2.1–2.7) |
| 3 | done 2026-11-09 |
| 4 | done 2026-11-09 |
| 5 | done 2026-11-09 |
| 6 | done 2026-11-09 |
| 7 | done 2026-11-09 |
| 8 | done 2026-11-09 |
