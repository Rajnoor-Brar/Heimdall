# Phase 4: `[points] library`, `--rerun`

Status: done 2026-11-08. Blocked by: phase 3 (done).

### Step 4.1: `library = true` (Size: M)
- Acceptance: on `true`, planning looks up each generation point's key. A complete hit is linked and counted as skipped. A miss runs into the library and is linked. `--why` says "from the library (first by <R>)". `--rerun` reruns into the entry under its lock and names the other Runs that link it.
- Files: `framework/runner/config.py`, `framework/schema/run.toml`, `framework/runner/cli.py` (planning), `framework/runner/record.py`, `tests/runner/test_library.py`, plus a slow `tests/integration/test_library_share.py` (new): two Errands in the scratch work dir share a point and the second runs nothing.
- Check: `taskset -c 0-5 nice -n 10 python -m pytest -q tests/runner/test_library.py`, then alone `tests/integration/test_library_share.py`.

### Step 4.2: `library = "only"` (Size: S)
- Acceptance: points run into the library and the Run leaves no Run folder, manifest or plot stage. `heimdall runs` shows it as such, and the registry entry lists library keys as its records.
- Files: as 4.1.
- Live doc: `docs/live/points-library.md` (affects identity, provenance, outputs).
- Blocked by: 4.1.

## Log
- 2026-11-08, 4.1 and 4.2: `[errand] library` / `[cfgs.<k>] library` (`true | false | "only"`, schema `run.toml`, `Configuration.library`); `cli._planned_points` sets `plan.library`; `record.record_dir` of a library plan is its entry, so every read and write of a library point goes to the entry, links or not; `record.assign_seeds` gives a library hit its recorded seed; `cli.pool_points` (links, `used` notes, the library and `--rerun` messages); `execute.run_point` links again and `_run_point` appends `created` or `rerun` to the index; `print_plan` and `print_why` say `library <key16>, first by <R>`; `only` restricts the stages, writes no manifest or snapshot, removes its links at its end (`record.unlink_run`) and lists the entries as the registry's records (`run started` carries `library`); `house.clean_targets` and `house.remove` treat a link as a link; `entry_of` falls back to an id whose tail is digits.
- Tests: `tests/runner/test_library.py` 15 pass; `tests/integration/test_library_share.py` (slow, alone): two Errands share both points, the second runs nothing (attempts stay at 1), `--rerun` makes 2 and names `T/first/01_one`, an `only` run leaves no `points/` or manifest. `tests/runner -m 'not slow'`: 2128 passed, 3 failed (the known three; a fourth, a code cite of an issue id in the new slow test, fixed).
- Cluster (the plan's open question): `cluster` skips a library hit at submission because `is_complete` is the library's; the points job's `run_one` links as a Run does. Not run against Slurm.
