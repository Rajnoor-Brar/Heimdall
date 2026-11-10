# Phase 9: the issues, the review, the close

Status: 9.1 and 9.2 done; 9.3 is the close. Blocked by: phase 7. Source: the second gate (00_Plan), answers 4 and 5; `docs/rules/work.md` stages 4 and 5.

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
- **9.1 · done 2026-11-11.** Every open issue is triaged in Implementation_Issues with its cause, what a user sees, its urgency and its size, and 7.1's marginals issue is added. The two stable-docs reds wait for a crystallise.
- **9.2 · done 2026-11-11.**
  - **The review:** by an agent that did not implement, over `4d225a3..173ba4e`.
  - **Suites at `173ba4e`:**
    - fast: 2315 passed, 11 skipped, 2 failed (the named reds);
    - full: 2496 passed, 11 skipped, 2 xfailed, 2 failed (the same), in 47 min.
    - The developer's Sherpa jobs ran throughout (load 32–34).
  - **Five proven defects, each fixed with a test that fails on the old code:**
    1. `rank --json` crashed on any non-finite number (`ca51d43`).
    2. `rank` crashed on a terminal that is not UTF-8, and its test faked the stream (`f3da8c7`).
    3. The record said "no gate is applied" above `veto_loss`'s vetoes, and a category ranking said "the vetoed last" with none vetoed (`9edf4b3`).
    4. `migrate` missed a dotted key, a quoted header and a set's own table of `[score]` (`58eb099`).
    5. A test cited a plan id (`5ee952f`).
  - **For a decision:** reversed thresholds are accepted (an issue).
  - **Probes that held:** `--trim 0.6` refused; gates on against off; old names refused and migrated; nothing defaults to vetoing.
  - **After the fixes:** fast 2320 passed, 11 skipped, the named reds; `test_plot_stage` 53; `test_report_draw` 2.
  - **Verdict:** sound after the fixes.

