# Phase 5: tab completion (I-73)

Status: not started. Blocked by: phase 1 (the run kind reads `RunEntry`).

The spec is [the tab-complete plan](../plans/tab-complete/00_Plan.md) and its four phase files. Its decisions D1–D7 are final: D3 and D5 were decided as proposed on 2026-11-09. Edit its header's status line to say so when this phase starts. Run its phases P1 → P4 in order, each by its own named check, and write each one's log in its own file.

**Additions to that plan, from this round:**
- **The run kind** (its P2, D4) reads the registry without pruning: `runs._own(sorted(runs.folder().glob("*.json")), mine=True)`, parsed as `RunEntry` (P1.2). It never calls `runs.entries()`, which prunes and so writes.
- **`complete.py` is a new module at rank 5.** Its row in `docs/stable/internals/runner.md` is written at P7, not here. The tab-complete plan's live doc (its P4) names it under **Stable pages need**.
- **Its P4 deletes the plan folder and I-73**, as written there. In this round's ledger that closes `plans/tab-complete/`.

Check: the tab-complete plan's P3 check (`bash -c` with `COMP_WORDS` set gets the expected `COMPREPLY` for each kind), then the fast suite.

## Log
