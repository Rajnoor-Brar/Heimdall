# Phase 2 ⏸: I-11, the golden identity file

Status: done 2026-11-07. The developer confirmed 2026-11-07: approved.

### Step 2.1: write and compare (Size: S)
- Acceptance: `tests/golden/identity_parts.json` holds every fixture config's points' `identity_parts`, with `exe_sha256` (and any binary hash) masked. It is written once, under the shadow root. A test plans every fixture config and compares, and its message names the point and the first differing key.
- Files: `tests/golden/identity_parts.json` (new), `tests/runner/test_identity_golden.py` (new).
- Check: `taskset -c 0-5 nice -n 10 python -m pytest -q tests/runner/test_identity_golden.py`
- Rule from then on: a change to the golden file is an identity change and is asked first (invariants).

## Log

2026-11-07: `tests/golden/identity_parts.json` (193 points, 606 KB, a point a line) written once by `test_identity_golden.write()` under the shadow root; `tests/runner/test_identity_golden.py` compares (names the point and the first differing key). Masks: `exe_sha256`, `files_sha256` entries under `/build/`; `{scratch}` for the scratch folder. Two runs of the collector were identical before it was written. Mutation check (a changed `seed_rule`, temporary test, removed): fails with `Decay/decay|single|point: seeds: kept 'generator', now 'CHANGED'`. 5 passed. **Finding:** Herwig, MadGraph and Sherpa fixture points hash an absolute `<scratch>/cache/…` path, so those identities are not portable across a moved cache; not changed (it is an identity change, ask first).
