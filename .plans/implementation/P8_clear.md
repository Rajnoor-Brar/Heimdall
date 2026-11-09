# Phase 8: ISSUES and clearing

Status: done 2026-11-09. Blocked by: phase 7. Closes P-1 (8.1), P-5 and P-6 (8.2).

### Step 8.1: `ISSUES.md` (Size: S)
- Acceptance:
  - **Issues closed:**
    - I-120 and I-121 are deleted: their done-whens hold, and their decisions are now in `docs/stable/design/decisions/` (P7). The held items are in Postponed.
    - I-73 is gone (P5).
    - I-29 has lost `layout.TILED` (P2.2), and I-79 and I-77 carry P6's notes.
  - **The order line.** "Plans of 2026-11-07" is deleted. The order line now opens with "**Next:** plan one dialect (I-20, I-21) with the snapshot question in `implementation/Postponed.md`", then the phases as they stand.
  - **New issues.** Each open entry of this round's [Implementation_Issues.md](Implementation_Issues.md) becomes an issue with the next free `I-` id (what, why, done when, at most ten lines), or is marked closed there with why.
- Check: every link in `ISSUES.md` resolves (`taskset -c 0-5 nice -n 10 python -m pytest -q tests/runner/test_docs.py`, which reads it); `grep -n "I-120\|I-121\|I-73" .plans/ISSUES.md` prints nothing.

### Step 8.2: delete what is homed (Size: XS)
- Acceptance: walk the [ledger](00_Plan.md#ledger-every-item-of-plans) file by file. For each source file, check that every item is closed (its mark in the file) or in [Postponed.md](Postponed.md). Then `git rm` it:
  - `.plans/plans/prompt.md`;
  - `.plans/plans/stats-backend/` (with `notes/`);
  - `.plans/plans/points-library/`;
  - `.plans/audits/2026-11-08-code/` (every file, `sweeps/` too).

  `plans/tab-complete/` has gone at P5. A file with an item neither closed nor postponed is not deleted: it keeps ` · ripe to clear` off its title, and the log says which item holds it.
- Check: `ls .plans .plans/plans .plans/audits` shows only `ISSUES.md`, `implementation/` and folders still holding an item; `git status --short .plans` shows the deletions staged in this step's commit.

### Step 8.3: close the round (Size: XS)
- Acceptance:
  - [00_Plan.md](00_Plan.md)'s Progress is complete, and its title gains ` · done, ripe to clear after the developer's review`.
  - The phase files keep their logs.
  - Implementation_Notes and Implementation_Issues stay for the developer's review.
  - Postponed.md stays: it is the next planning's input.

  Then stop with the round's one report:
  - what holds now;
  - the crystallise report's summary;
  - the full suite's counts;
  - the open issues added in 8.1;
  - the commits, local and not pushed.
- Check: the report's numbers equal the logs'.

## Log

- 8.1: I-120 and I-121 deleted from `ISSUES.md` (I-73 went at P5); the order line opens with **Next:** and lost "Plans of 2026-11-07"; its phases list I-129 and I-131 and no longer I-73. `Implementation_Issues.md` had no open entry; the round's three findings are entered there and became I-129 (tests that list live runs see the machine's own), I-130 (the points library on a real work dir, held) and I-131 (TAB by hand). The ids start at 129, not 125: I-125 to I-128 were closed issues of the earlier cycle. Audit marks added: T-1 (6.1–6.3, 7.1), P-1 (8.1), P-2 (7.1). Check: `test_docs.py` all green; the grep for I-120, I-121, I-73 prints nothing.
- 8.2: walked the ledger: every item of `plans/prompt.md`, `plans/stats-backend/`, `plans/points-library/` and the 2026-11-08 audit (nine files and `sweeps/`) is closed (its mark in the file) or named in `Postponed.md`; P-1, P-2, P-5, P-6 and T-1 were the last unmarked and got their marks. All four were `git rm`'d. `ls .plans` shows `ISSUES.md` and `implementation/`; nothing outside `.plans/` links into the deleted files. Check: `test_docs.py` green.
- 8.3: `00_Plan.md`'s Progress is complete and its title says it is done; the round's report is the pause below.

