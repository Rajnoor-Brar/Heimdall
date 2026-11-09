# Phase 4: live doc

Plan: [00_Plan](00_Plan.md). Blocked by: phase 3. Size: XS.

## Steps

1. **`docs/live/tab-complete.md`** (`affects: environment`), in phase 3's commit:
   - **Now holds:** TAB completes every command, from the kinds table; bash only; read-only.
   - **Stable pages need:** `stable/setup/environment.md` gets one line.
2. **Close out.** Delete this plan folder and I-73. The decisions D1–D7 go into the live doc's **Decisions**.

## Checks

- `taskset -c 0-5 nice -n 10 python -m pytest -q runner/test_docs.py`: no new failures beyond the known ones.

## Log
