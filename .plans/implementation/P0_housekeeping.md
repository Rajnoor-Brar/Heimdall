# Phase 0: commit, rules, fold the old files

Status: not started. Blocked by: none. Closes P-3 (0.2–0.4) and P-4 (0.5).

### Step 0.1: commit the planning work (Size: XS)
- Acceptance: one commit holds `.plans/audits/2026-11-08-code/`, `.plans/plans/prompt.md`, `.plans/plans/tab-complete/`, `.plans/ISSUES.md` (the I-73 edit) and `.plans/implementation/`, staged by those paths. `.codex/` is not staged. Message: `plans: the 2026-11-08 audit, the tab-complete plan and implementation round 1, committed before the round clears them`.
- Check: `git status --short .plans` prints nothing, and `git show --stat HEAD` lists only those paths.

### Step 0.2: `work.md` lists the round's folder (Size: XS)
- Acceptance: `docs/rules/work.md`'s table under `.plans/` gains one row, the only change to the page (a rules page is the developer's, and this row is their word of 2026-11-09):
  `| .plans/implementation/ | a round of implementation: 00_Plan.md and a file per phase; Implementation_Notes.md (decisions the implementer made off-plan); Implementation_Issues.md (findings left open); Postponed.md (items read and left for a later round, the next planning's input) |`
- Check: `taskset -c 0-5 nice -n 10 python -m pytest -q tests/runner/test_docs.py`, where only the two known stable-page reds may fail.

### Step 0.3: fold `.plans/Implementation_Issues.md` (Size: XS)
- Acceptance: F-2, F-4, F-11 and F-12 are in [Postponed.md](Postponed.md) already, and F-6, F-7 and F-9 are named by P7 and P6. Check each against those files, then delete `.plans/Implementation_Issues.md`.
- Check: `grep -c "F-2\|F-4\|F-11\|F-12" .plans/implementation/Postponed.md` ≥ 4; the file is gone.

### Step 0.4: fold `.plans/Implementation_Notes.md` (Size: S)
- Acceptance: for each bullet, find a distinctive term of it in `docs/live/*.md` (`grep -l`).
  - When a live doc states it: nothing to do.
  - When none does, and it is a decision a user or developer relies on (a default, a refusal, a rule of the engine): add one bullet to the **Decisions** of the live doc whose subject it is. Keep it to at most 300 characters, as work.md's notes are.
  - Process history (commit 93ff3b3's rename, 05fc171, the baseline run, the session checklist): dropped, since git holds it.
  - The ten scoring rules O-10 lists stay unreviewed: they are in Postponed, and the live doc only says what holds.
  Delete the file at the end. The log lists each bullet that was added, and where.
- Check: `taskset -c 0-5 nice -n 10 python -m pytest -q tests/runner/test_docs.py` (the known two may fail); the file is gone.

### Step 0.5: correct I-25 (Size: XS)
- Acceptance: in `.plans/ISSUES.md`, I-25's delete list loses `framework/tools/plotmerge/` (live, and tested by `tests/integration/test_post.py`: it bundles every point in one file and merges nothing). Its `migrate.py` deletion gains "after `adopt_points` has moved to `runner/library.py` (round 1 P3)". Nothing else changes. Mark R-6 and P-4 in their audit files.
- Check: `grep -n plotmerge .plans/ISSUES.md` finds no delete of it.

## Log
