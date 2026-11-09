# Phase 3: one library module

Status: not started. Blocked by: phase 0. Closes S-3 and D-8. It is the precondition of I-25's deletion of `migrate.py`.

**Today:** the library is in three modules:
- **`record.py`:** `_without_comments` (`:89`), `library_parts`, `library_key`, `library_key_of_recorded`, `LIBRARY`, `LIBRARY_INDEX`, `library_entry`, `library_products`, `link_library`, `link_into`, `unlink_run`, `library_first`, `library_index_file`, `index_note`, `index_append`, `library_links`, `library_entries` (`:101–296`), and `_library_seed` (`:455`);
- **`house.py`:** `library_assignments`, `library_list`, `library_verify`, `library_prune` (`:1192–1313`);
- **`migrate.py`:** `DUPLICATE` and `adopt_points` (`:1471–1520`).

`cli.pool_points` (`:1521`) and `cli.cmd_library` (`:2700`) call them.

### Step 3.1: `runner/library.py` (Size: M)
- Acceptance:
  - **Path.** A library entry's path belongs to `tools.RunFolders`: `library_entry(key)` and `library_product(key)` (rank 2). `record` and `library` both use them.
  - **The new module.** `framework/runner/library.py` sits at rank 3 in `runner/__init__.py` `RANKS`, beside `record`. Its docstring cites the doc id the library's code cites today.
  - **What moves in.** Everything listed above except `_library_seed`, under shorter names where the module now says "library" (`library.key`, `library.parts`, `library.key_of_recorded`, `library.link`, `library.entries`, `library.links`, `library.list_lines`, `library.verify`, `library.prune`, `library.adopt`, …).
  - **What `record` keeps.** `marker_text`, `recorded_identity`, `lock_file`, `record_dir` and `_library_seed`: the marker, lock, folder and seed logic every point passes through. It reaches the entry by `plan.folders.library_entry(plan.library)`.
  - **Imports.** `library` imports `record`, and `record` never imports `library`. `library` never imports `house` or `cli`. The refusal while a job of the work dir runs (`house.runs_here`) stays in `cli.cmd_library`, which checks it before `prune` or `adopt` with `--yes`.
  - **Callers.** `cli.pool_points` stays in `cli` (it drives the bus) and calls `library`. Every caller (`cli`, `execute`, `plotdoc` and any other `grep` finds) and every test imports from `library`. Nothing re-exports.
- Files:
  - `framework/runner/library.py` (new), `record.py`, `house.py`, `migrate.py`, `cli.py`, `execute.py`, `tools.py`, `__init__.py`;
  - `tests/runner/test_library.py`, `test_library_key.py`, `test_migrate.py`, `tests/integration/test_library_share.py`.
- Check:
  - `grep -rn "def library_\|adopt_points" framework/runner` finds only `library.py`;
  - `taskset -c 0-5 nice -n 10 python -m pytest -q tests/runner/test_library.py tests/runner/test_library_key.py tests/runner/test_migrate.py tests/runner/test_imports.py tests/runner/test_identity_golden.py`;
  - then alone, `tests/integration/test_library_share.py`;
  - then the fast suite.
- Live doc: in `docs/live/points-library.md`, the Decisions' "The library code is in `record.py`" becomes "in `runner/library.py`, rank 3, which imports `record`". **Stable pages need** gains `internals/runner.md`, the rank row (written at P7).
- Blocked by: 0.

## Log
