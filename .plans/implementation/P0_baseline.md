# Phase 0: the baseline

Status: done 2026-11-10. Blocked by: none.

Every loss changes in this round, on purpose. This phase writes down what holds before, so a later red is told from an old one, and "what changed" at phase 7 has a before.

### Step 0.1: the suite and the engine, as they are (Size: XS)
- Acceptance:
  - The fast suite is run once, and its result is in the log: the counts, and each failing test's id with its first line. These are the known reds; no step of the round is held to them.
  - `tests/integration/test_plot_stage.py` and `tests/integration/test_report_draw.py` are run, each alone, and their results are in the log.
  - `git status --short` is in the log. A file another session left in the tree is named there, and is never staged by this round.
- Files: this file's log only.
- Check: `taskset -c 0-5 nice -n 10 python -m pytest -q tests/runner -m 'not slow'`, then each of the two integration files alone with the same prefix.
- Seam: none; nothing changes.
- Blocked by: none.

## Log

- **0.1 · done 2026-11-10 at `4d225a3`.** Fast suite (`tests/runner -m 'not slow'`): 2182 passed, 11 skipped, 0 failed, in 1 min 42 s. No known reds. `tests/integration/test_plot_stage.py` alone: 53 passed (3 min 48 s). `tests/integration/test_report_draw.py` alone: 2 passed. `git status --short`: only `?? .codex/`, another session's, never staged.
