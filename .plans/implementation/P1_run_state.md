# Phase 1: run state as a value

Status: not started. Blocked by: phase 0. Closes G-1, D-6, G-3, O-6 and G-8.

**Today:**
- `runs.state()` (`runs.py:292`) returns display text, such as `done, resumed`, `paused, forgotten`, `running (not reachable from here)`, `on <host>` or `exit 3`.
- `house.state_word` (`house.py:614`) cuts that text back to a word.
- Logic decides on the word in four places:
  - `cli.wait_turn`'s turn rule (`cli.py:1210`);
  - `cli.offered` (`cli.py:2313`);
  - the listing's `--state` filter (`house.py:675`);
  - its colours (`house.py:715`).
- The states are listed in `runs.VERDICTS` (`runs.py:45`), `house.RUN_STATES` (`house.py:579`) and `house.STATE_STYLE`.
- Entries are dicts, read with `.get` at about 150 sites in `runs.py`, `house.py` and `cli.py`.

Test seams: `tests/runner/test_runs.py`, `test_queue.py` and `test_live.py`, which already drive the registry, the queue waiter and the listing.

### Step 1.1: `runs.RunState` (Size: M)
- Acceptance:
  - **The value.** `runs.STATES` is the one tuple of state words. It holds today's `RUN_STATES`, plus `forgotten`, `exit` and `unknown`. `runs.RunState` is a frozen dataclass with these fields:
    - `word` (one of `STATES`);
    - `detail` (the rest of a verdict: `3` of `exit 3`, the message of `not run: …`);
    - `resumed` and `forgotten`;
    - `reachable` (False for "not reachable from here");
    - `where` (a host, or "another PID namespace", whose word is `unknown`).
  - **The functions.** `runs.state_of(data, live=None) -> RunState` holds `state()`'s logic. `RunState.text` rebuilds exactly the text `state()` returns today. `state()` becomes `state_of(...).text`, so every printed line is unchanged.
  - **The word.** It comes from the entry's fields, never parsed out of display text, in this order:
    1. `state`, when set;
    2. else a verdict whose first part (up to `:` or a space and a digit) is a word of `STATES`;
    3. else `VERDICTS[code]`;
    4. else `exit`.
  - **The callers.**
    - `house.state_word` is deleted.
    - The `--state` filter and the colours read `.word`.
    - `check_states` checks against `runs.STATES`, and `RUN_STATES` goes.
    - `cli.offered` reads `.word`.
    - `cli.wait_turn` decides with two named sets in `runs`:
      - `GIVES_TURN`: done, failed, not run, lost, forgotten, exit, cancelled, ended;
      - `HOLDS`: stopped, and paused when `forgotten`.

      It keeps today's rule exactly. A finished predecessor in neither set also gives the turn.
- Files: `framework/runner/runs.py`, `house.py`, `cli.py`, and `tests/runner/test_runs.py`, `test_queue.py`, `test_live.py`.
- Tests:
  - every text `state()` gave before, for a table of entries (finished with state, verdict, code; resumed, forgotten; queued, held, lost; another host; unreachable), is byte-identical after;
  - a test that patches `RunState.text` to return nonsense, where the queue waiter still starts, holds and gives the turn as before;
  - `runs --state forgotten` lists a forgotten run (it failed before);
  - an entry whose verdict is `not run: <message>` is listed by `--state "not run"`.
- Check: `taskset -c 0-5 nice -n 10 python -m pytest -q tests/runner/test_runs.py tests/runner/test_queue.py tests/runner/test_live.py`. `grep -rn state_word framework` prints nothing.
- Live doc: `docs/live/run-state.md`, with id `live-run-state`, affecting `live-runs`.
- Blocked by: 0.

### Step 1.2: `runs.RunEntry`, the type and `runs.py` (Size: S)
- Acceptance:
  - **The type.** `runs.RunEntry` is a frozen dataclass parsed once, by `RunEntry.parse(dict)`, in `runs.entry()`, `runs._own()` and `runs.entries()`. It has typed fields for every key read today, and `queue: Queue | None`.
  - **The queue part.** `Queue` is a frozen dataclass of `queue`, `queued_to`, `queued`, `held`, `began`, `left_queue` and `dispatched_from`.
  - **Round trips.** `extra: dict` keeps every key it does not know, and `RunEntry.as_dict()` gives back the dict it was parsed from, equal key for key.
  - **Writers stay on dicts.** `update` and `finish` read the file through a private `_entry_dict(run_id)` and write dicts, as now. Everything inside `runs.py` that reads an entry takes a `RunEntry`: `state_of`, `alive`, `queue_of`, `paused`, `again` and `Recorder`'s readers.
  - **Fakes.** A test fake of an entry is a `RunEntry` (the invariant: a fake has the real type).
- Files: `framework/runner/runs.py`, `tests/runner/test_runs.py`, `test_queue.py`.
- Check: as 1.1, plus a round-trip test of `parse` and `as_dict` over every entry file the tests write.
- Blocked by: 1.1.

### Step 1.3: `house.py` and `cli.py` read attributes (Size: M)
- Acceptance: every read of a registry entry in `house.py` (the listing, `live_line`, `runs_here`) and in `cli.py` reads `RunEntry` attributes. Do `house.py` first, green, then `cli.py`, which covers `wait_turn`, the `runs` actions, `resume_snapshot`, `relaunch_entry`, `running_at` and `entry_of`. Dicts that are not registry entries, such as events, plans and `counts`, stay dicts. `cli.notify`'s verdict map is left as it is (see 00_Plan, Not yet specified).
- Files: `framework/runner/house.py`, `cli.py`, `tests/runner/test_live.py`, `test_queue.py`.
- Check:
  - `taskset -c 0-5 nice -n 10 python -m pytest -q tests/runner/test_runs.py tests/runner/test_queue.py tests/runner/test_live.py tests/runner/test_detach.py`, where `test_detach`'s known red may stay red;
  - then the fast suite, with only the known reds;
  - the log lists what `grep -nE '\.get\("(queued|held|queue|queued_to|began|pid|pstart|boot|finished|verdict|state|resumed_by|forgotten)' framework/runner/{house,cli}.py` still prints, with why each line is not an entry.
- Blocked by: 1.2.

### Step 1.4: `runs.VERSION = 2` (Size: S)
- Acceptance:
  - `begin` writes `"v": 2`, and `RunEntry.newer` is `v > VERSION`.
  - The listing shows a newer entry with ` (newer Heimdall)` after its state text.
  - These refuse a newer entry before they act, with `HeimdallError("this entry is from a newer Heimdall", hint="act on it from the checkout that started it")`:
    - stop and `stop -i`;
    - `--resume`, `--again`, `--dispatch`, `--forget` and `--jobs`;
    - `runs -i`'s actions;
    - P4's `--resume-queue`.
  - Entries with `v` 1, or with no `v`, read and act as before.
- Files: `framework/runner/runs.py`, `cli.py`, `house.py`, `tests/runner/test_runs.py`.
- Check: a test that writes a `v: 3` entry, sees it listed, and is refused at each action above; then 1.3's check.
- Live doc: `docs/live/run-state.md`.
- Blocked by: 1.3.

### Step 1.5: G-8, free-text states in records (Size: XS)
- Acceptance: read every reader of a point attempt's `verdict` and of a journal event's `state`: `record.state_of`, `house.show_data`, `status`, `watch` and `report`.
  - If any branch reads such a string beyond equality with a known word (a `startswith`, a split, an `in` on a substring), make it an equality on a named constant, with a test.
  - If none does, write "checked, fine" and the list of readers in the log.
  - Mark G-8.
- Check: the log's list. When code changed, the tests of the readers touched.
- Blocked by: 1.1.

## Log
