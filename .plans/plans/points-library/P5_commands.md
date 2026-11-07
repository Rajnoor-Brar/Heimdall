# Phase 5 ⏸: `heimdall library`

Status: done 2026-11-08, stopped at the ⏸: `adopt` has not been run on any real work dir. Blocked by: phase 4 (done). Stop before any `adopt` outside the scratch work dir.

### Step 5.1: list, verify, prune (Size: S)
- Acceptance: `list [<A>]` shows entries with coordinates and the Runs linking them. `verify` checks complete-for-key and that each link resolves, and reports, never fixes. `prune` removes unlinked entries: a dry run by default, deletion with `--yes`. `clean` and `migrate` never follow a link into the library.
- Files: `framework/runner/cli.py`, `framework/runner/house.py`, `framework/runner/migrate.py`, `tests/runner/test_library.py`.
- Check: `taskset -c 0-5 nice -n 10 python -m pytest -q tests/runner/test_library.py tests/runner/test_migrate.py`

### Step 5.2: adopt (Size: M)
- Acceptance: `adopt <A>/<E>/<R> [--dry-run]` moves each complete generation point (recorded identity = planned identity) into the library under its key and links it back. A second point with the same key is linked, and its own folder is kept beside it as `<name>.adopted-duplicate` until `prune --duplicates`. Tested on the scratch work dir only.
- Check: as 5.1. Then ⏸: the developer decides whether and where to run it on a real work dir, dry run first.
- Blocked by: 5.1.

## Log
- 2026-11-08, 5.1 and 5.2: `house.library_list`, `library_verify`, `library_prune`; `migrate.adopt_points`; `cli.cmd_library`; `record.library_key_of_recorded` (the key of a recorded `identity.json`, one rule with `library_key`), `link_into`, `index_append`, `library_links`, and `pruned` in the index fold. `clean` removes a Run's link and never an entry (phase 4); `migrate`'s moves are the layouts before the library, so it is unchanged.
- Tests: `tests/runner/test_library.py` 20 pass, `test_migrate.py` too (48): adopt dry run changes nothing; adopt files four points under the keys a library plan gives, links them back, and the same physics planned as a library point is then complete; a second Run's points are linked and its own folders kept as duplicates, `list` names both Runs, `verify` is clean, `prune` has nothing, `prune --duplicates` removes 8 folders; a broken `.complete` and a dangling link are reported by `verify` (exit 1); `prune` after the Run's links go removes 3 entries and tells the index; an incomplete point is left.
- Decision taken off-plan: `adopt` and `prune` need `--yes` (the plan: `adopt [--dry-run]`), so that the move is a dry run first by default; `--dry-run` is accepted.
- ⏸: the developer decides whether and where to run `adopt` on a real work dir, with its dry run first.
