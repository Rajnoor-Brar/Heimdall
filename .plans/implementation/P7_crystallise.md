# Phase 7: crystallise (the developer's order, 2026-11-09)

Status: not started. Blocked by: phases 1–6, whose live docs it merges. Closes P-2, F-6, F-7 and the two docs tests of T-1.

Follow `docs/rules/work.md`'s **Crystallising**, all six steps, over every live doc in `docs/live/`: the 23 of 2026-11-08 and this round's (`run-state`, the tab-complete doc, and the changes to `points-library` and `run-queue`).

### Step 7.1: the crystallise (Size: L, one commit by the protocol)
- Acceptance:
  1. Run `heimdall docs --drift` and read every live doc.
  2. Verify each claim against the code, then merge it into the stable page that owns it, rewriting, not appending. Drop what the code no longer bears out, and say so in the report.
  3. Move each **Decisions** note into its area file in `docs/stable/design/decisions/`, with a new id where it has none (writing.md: a bullet of at most 300 characters, `Gave up:` and `Superseded by`).
  4. Check each page that `--drift` names against its code.
  5. Delete the live docs, keeping `live/README.md`. Set `commit` in `docs/stable/CRYSTAL.toml` to the commit crystallised against.
  6. Regenerate, run the docs tests, and commit as one.
- Musts:
  - `docs/stable/internals/runner.md`'s rank table gains `scorecmd.py` (4), `diffcmd.py` (5), `library.py` (3) and `complete.py` (5). Each row's text says what the module owns, taken from its docstring. `house.py`'s row loses the library.
  - `docs/stable/guide/plots-statistics.md` and `guide/reports.md` describe the standings, the purposes, `head-to-head` and `heimdall score`. They lose the top five, the scoreboards and the five old columns as the scoring (F-7).
  - `stable/internals/plot-backends.md` names only code that exists (`test_the_code_a_page_names_exists`).
  - `live/stats-rms.md` is dropped as superseded (`live/scoring.md` says so).
- Report: in [Implementation_Notes.md](Implementation_Notes.md), a section "Crystallise" lists what merged where, what was dropped and why, and the decision ids given.
- Check:
  - `taskset -c 0-5 nice -n 10 python -m pytest -q tests/runner/test_docs.py`, all green;
  - `ls docs/live` shows `README.md` only;
  - then, alone, the full suite, `taskset -c 0-5 nice -n 10 python -m pytest -q tests` (about 25 min). It is green except the strict xfails and skips of P6. Record its counts in the log.
- Blocked by: 1.5, 2.7, 3.1, 4.1, 5 (its P4), 6.3.

## Log
