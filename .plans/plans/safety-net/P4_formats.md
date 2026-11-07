# Phase 4: I-28, record files with a format version

Status: done 2026-11-07. Blocked by: phase 1.

### Step 4.1: write `format = 1` (Size: S)
- Acceptance: `points.json`, `provenance.json` and `identity.json` gain `"format": 1` at top level, and `plot.toml` gains `format = 1` in its first table. Readers accept a missing key as format 0 (today's) and refuse a format newer than they know, with a hint to update Heimdall. Identity does not change: `identity.json` is the parts written out, and the key is added outside the hashed parts (golden file green).
- Files: `framework/runner/record.py`, `framework/runner/plotdoc.py`, `tests/runner/test_provenance.py`, `tests/runner/test_identity_golden.py`.
- Check: `taskset -c 0-5 nice -n 10 python -m pytest -q tests/runner/test_provenance.py tests/runner/test_identity_golden.py tests/runner/test_plot.py`

### Step 4.2: `heimdall records upgrade` (Size: M)
- Acceptance: `heimdall records upgrade [--dry-run] [<A>[/<E>[/<R>]]]` lists the record files below format 1 and what it would do (add the key; the layout moves `migrate --layout` does today). Without `--dry-run`, each file is backed up beside itself first. Tests use the scratch work dir only. Running it on a real work dir is the developer's call, never a test's.
- Files: `framework/runner/cli.py`, `framework/runner/migrate.py`, `tests/runner/test_migrate.py`.
- Check: `taskset -c 0-5 nice -n 10 python -m pytest -q tests/runner/test_migrate.py`
- Live doc: `docs/live/record-formats.md` (affects provenance).
- Blocked by: 4.1.

## Log

2026-11-07:
- 4.1 (`d5bf2a7`): `record.FORMAT = 1`, `record.check_format`; `format` first in `points.json`, `provenance.json`, `identity.json` (outside the hashed parts; `why` drops it before comparing) and in `plot.toml`'s `[source]` (three writers in `plotdoc`). Readers checking it: `results.load`, `plot` (manifest), `plotdoc.load`/`from_manifest`/the events read, `record.why`. Absent is format 0; newer is refused ("this record is format N; this Heimdall reads up to 1", hint: update Heimdall). The golden identity file passes unchanged. One test changed with it: `test_the_identity_is_the_hash_of_its_recorded_parts` drops `format` before hashing (identity.json is the parts plus the key). Not every reader checks: the ones in `cli.py` (reproduce, migrate --plot-docs, --snapshot) do not yet.
- 4.2 (`d845b44`): `heimdall records upgrade [--dry-run] [A[/E[/R]]]` (`migrate.format_files`, `migrate.upgrade_file`, `cli.cmd_records`): lists files below format 1; without `--dry-run` stamps each after a `<name>.bak` copy (`.bak2`, …); refused while a job of the work dir is going; plot.toml edited by line so comments stay. The layout moves are only counted ("layout: N move(s) pending, which heimdall migrate --layout shows"): they are staged and a work dir's own, so I did not duplicate them. Test: one end-to-end in `test_migrate.py` on the scratch trees only. Not run on any real work dir.
- Fast suite after both: 3 failed (baseline `test_detach`, `test_stack_build`; the stable-page `code:` test, settled), 1800 passed, 10 skipped, 47 deselected. The slow suite is run after the commits.
- `cli.py` held another session's uncommitted resume work: 4.2's commit takes only my hunks (built on HEAD with `patch`); their hunks stay in the tree, uncommitted.
