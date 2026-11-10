# Phase 9: the issues, the review, the close

Status: not started. Blocked by: phase 7. Source: the second gate (00_Plan), answers 4 and 5; `docs/rules/work.md` stages 4 and 5.

### Step 9.1: the open issues, each triaged (Size: XS)
- Acceptance: every open entry of Implementation_Issues says what exactly causes it (`file:line`), what a user sees (effect and side effect), how urgent it is, and how much work it is: a quick fix, light planning or a decision, or a proper plan. The two stable-docs reds say they wait for a crystallise, by the developer's word.
- Files: `Implementation_Issues.md`.

### Step 9.2: the review, by an agent that did not implement (Size: S)
- Acceptance: a review agent reads the Notes, the Issues and the phase logs, then the code commits' diffs (the riskiest first), runs the fast suite and the full suite each alone, and probes claims a test cannot show. It returns a verdict: proven defects with `file:line` or output, or clean. Each defect is fixed in its own commit with a test, or becomes an issue.
- Check: the review's verdict, in this log.

### Step 9.3: the close (Size: S)
- Acceptance, per `work.md` stage 5, in one commit:
  - every decision of Implementation_Notes is stated in `docs/live/grand-ranking.md`'s Decisions, or is added there; those not yet said yes to by the developer go to `.plans/Notes.md`, naming where docs state them;
  - the open issues, Postponed and the review's findings go to `.plans/Issues.md`, each with an `I-` id and the triage of 9.1;
  - the round's record is a `Notes.md` entry: its commits, what it built, the suite's counts at the review, the review's verdict;
  - `.plans/implementation/` and `.plans/plans/grand-ranking/` are deleted;
  - `test_docs` resolves both files' links.
- Check: `taskset -c 0-5 nice -n 10 python -m pytest -q tests/runner/test_docs.py`.

## Log
