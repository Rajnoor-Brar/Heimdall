# Phase 4: requeue a queue lost to a reboot

Status: not started. Blocked by: phase 1 (`RunState`, `RunEntry`). Closes O-3 and the first half of E-1. The second half, `--queued-to` on a run already queued, is in Postponed.

**Today:**
- After a reboot, every waiter of a queue is `lost` (`runs.alive`, a new boot id).
- `--resume` takes one entry, and `runs.again` drops `--queued-to`.
- `cli.relaunch_entry` (`cli.py:2197`) relaunches one entry from its record's snapshot (`resume_snapshot`). It picks the new run's id itself (`runs.ID_VAR`) and returns once the run has started.
- A waiter that never began has no record, so it has no snapshot either.
- `runs.queue_of(entries, queue)` gives a queue's runs in order.

### Step 4.1: `heimdall runs --resume-queue ID|N` (Size: S)
- Acceptance:
  - **What it takes.** `ID|N` names any run of a queue, as `--dispatch` does (`entry_of`). The queue is that entry's `queue.queue`, or its own id if it heads one.
  - **The runs it walks.** In `queue_of` order, it takes the members whose `RunState.word` is `lost` and relaunches each, detached:
    - a member that `began` comes from its record's snapshot, as `--again` does;
    - a member that never began comes from its own argv (`runs.again`), against today's `configs/`, and the command says so for that run.
  - **Where each one queues.** Each relaunched run is queued (`--queued-to <id>`) to the nearest earlier member that is live after this command: an earlier relaunched run, or an original still running, queued or held. If none is live, it starts at once.
  - **Left alone:** `done`, `failed`, `stopped`, `paused` and `forgotten` members. The command lists them with their state.
  - **Refusals:**
    - a queue with no `lost` member: "nothing in this queue was lost";
    - a cluster entry;
    - a newer entry (P1.4).
  - **Output.** It prints one line a run: `requeued [old tail] → <new id>, after <id or "at once">`.
  - **The code.** `relaunch_entry` gains two parameters: `after` (appends `--queued-to <id>`) and `from_snapshot` (False for a waiter that never began). The `runs` parser takes the option beside `--again` and `--dispatch`.
- Files: `framework/runner/cli.py`, `framework/runner/runs.py` if a helper belongs there, `tests/runner/test_queue.py`.
- Test: through the seams `test_queue.py`'s lost-predecessor test uses (O-1's fix).
  - **Setup:** a queue of three runs: the first done, the second begun and then killed (`lost`), the third waiting and killed (`lost`, never began).
  - **Then** `--resume-queue` with the third's tail.
  - **Expect:**
    - two new entries;
    - the second's relaunch from its snapshot, starting at once;
    - the third's from its argv, `queued_to` the second's new id;
    - the first untouched;
    - a second call refused with "nothing in this queue was lost".

  Every run in the test is 5k events at most.
- Check: `taskset -c 0-5 nice -n 10 python -m pytest -q tests/runner/test_queue.py tests/runner/test_runs.py`.
- Live doc: `docs/live/run-queue.md`, **Now holds**: `--resume-queue`, after the paragraph on dispatch and forget.
- Blocked by: 1.4.

## Log
