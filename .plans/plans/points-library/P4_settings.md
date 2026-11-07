# Phase 4: `[points] library`, `--rerun`

Status: not started. Blocked by: phase 3.

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
