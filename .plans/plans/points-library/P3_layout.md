# Phase 3: layout, index, lock

Status: done 2026-11-08. Blocked by: phase 2 (done).

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
- 2026-11-08, 3.1 and 3.2 together (they share the code): `tools.RunFolders.library_records` / `library_results`; `PointPlan.library` (the full key, empty for an unpooled point); in `record.py` `library_entry`, `library_products`, `link_library`, `lock_file`, `index_note`, `library_entries`, `library_index_file`, `marker_text`; `is_complete` is `recorded_identity(plan) == plan.identity`, and `recorded_identity` turns a marker holding the plan's library key into the plan's identity, so every comparer works unchanged; `execute` writes `marker_text(plan)`; `PointLock` and `holder` use `lock_file`; `points_manifest` names `library = "<key16>"` and its `identity` is the marker's text (the key for a library point), so the three readers that compare `.complete` with the manifest's identity (`plot.recorded`, `plotdoc.load`, `plotdoc.load` of a document) agree; `plotdoc._member` gives a planned library point's entry the key; `why` says "not in the library yet" for a library point.
- Readers shown through a linked point in `tests/runner/test_library.py` (8 tests): `house.status`, `show_data`, `point_log` (log), `results.load`, `plot.recorded`, `plotdoc._member`, the manifest. Not exercised through a link, by reading only: `cmd_reproduce`, `report.configured`, `bifrost`, `cluster` (they read `points/<name>` files by path, which a link resolves; `cluster`'s skip uses `is_complete`, which is changed here). Phase 4's integration test runs a real point through the link.
- Check: `test_library.py test_status.py test_plot.py test_provenance.py test_lifecycle.py test_why.py test_identity_golden.py` 228 passed; `tests/runner -m 'not slow'`: 2122 passed, 3 failed (the known three).
