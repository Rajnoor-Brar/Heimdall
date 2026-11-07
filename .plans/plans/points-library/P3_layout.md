# Phase 3: layout, index, lock

Status: not started. Blocked by: phase 2.

### Step 3.1: library folders and the index (Size: S)
- Acceptance: `tools.RunFolders` gains `library_records` and `library_results` per Assignment. `points.jsonl` is appended under an flock, one line per entry or change (key, coordinates (every quantity, fixed ones too), events, threads, seed, created, first Run, Runs using it). A reader folds the lines into the current state.
- Files: `framework/runner/tools.py`, `framework/runner/record.py`, `tests/runner/test_library.py` (new).
- Check: `taskset -c 0-5 nice -n 10 python -m pytest -q tests/runner/test_library.py`

### Step 3.2: links and the lock (Size: M)
- Acceptance: a Run's `points/<name>` and `results/…/points/<name>` can be relative symlinks into the library. `PointLock` locks the library entry for a library point. `points.json` (format 2) names `library = "<key16>"` per point. Every reader in 00_Plan's blast radius passes its existing test through a linked point: plotdoc, plot.recorded, house status and log, reproduce, report, results.load, bifrost.
- Files: `framework/runner/record.py`, `framework/runner/execute.py`, `framework/runner/tools.py`, the readers only where a test shows they break, `tests/runner/test_library.py`.
- Check: `taskset -c 0-5 nice -n 10 python -m pytest -q tests/runner/test_library.py tests/runner/test_status.py tests/runner/test_plot.py tests/runner/test_provenance.py`
- Blocked by: 3.1.

## Log
