# Phase 5 ⏸: `heimdall library`

Status: not started. Blocked by: phase 4. Stop before any `adopt` outside the scratch work dir.

### Step 5.1: list, verify, prune (Size: S)
- Acceptance: `list [<A>]` shows entries with coordinates and the Runs linking them. `verify` checks complete-for-key and that each link resolves, and reports, never fixes. `prune` removes unlinked entries: a dry run by default, deletion with `--yes`. `clean` and `migrate` never follow a link into the library.
- Files: `framework/runner/cli.py`, `framework/runner/house.py`, `framework/runner/migrate.py`, `tests/runner/test_library.py`.
- Check: `taskset -c 0-5 nice -n 10 python -m pytest -q tests/runner/test_library.py tests/runner/test_migrate.py`

### Step 5.2: adopt (Size: M)
- Acceptance: `adopt <A>/<E>/<R> [--dry-run]` moves each complete generation point (recorded identity = planned identity) into the library under its key and links it back. A second point with the same key is linked, and its own folder is kept beside it as `<name>.adopted-duplicate` until `prune --duplicates`. Tested on the scratch work dir only.
- Check: as 5.1. Then ⏸: the developer decides whether and where to run it on a real work dir, dry run first.
- Blocked by: 5.1.

## Log
