# Safety net before records and identity change

Issues: I-10, I-11, I-12, I-28. Status: planned 2026-11-07, not started. Blocks: points-library (all of it) and across-axes 4. stats-backend 4's sidecar follows I-28's `format` convention.

## Context

Verified at `cd6ceac`:

- **No shadow machine root (I-10).**
  - `tests/conftest.py:31` takes `HEIMDALL_MACHINE` or `~/Himinbjorg` as it is. Scratch is `<machine>/forge/scratch`.
  - It points `HEIMDALL_WORK`, `RESULTS`, `RECORDS`, `CACHE`, `REPORTS`, `WORKDIRS` and `RUNS` into scratch (:62-68).
  - So the tests read the live `machine.toml` and `recipes.toml`, and those decide what tests keep and see.
- **No golden identity file (I-11).** `tests/golden/` does not exist. Identity behaviour is tested in `test_why.py` and `test_seeds.py`, but nothing compares every fixture point's parts against a kept file.
- **No baselines (I-12).** The tags are `archive/pre-squash-2026-10-26` and `docs/pre-rebuild`; there is no `pre-restructure`.
- **No `format` in any record file (I-28).**
  - `points.json` (`record.points_manifest`, `record.py:535`), `provenance.json` (`record.provenance`, :485), `identity.json` (:79) and `plot.toml` carry none.
  - The only version field is `attempts.jsonl`'s `"v": 1` (`record.ATTEMPT_VERSION`).
  - `points.json` stores absolute paths for products, results and output.
- **A contradiction to settle (step 2.1 ⏸).** `.plans/ISSUES.md` marks I-11 `held`, while its standing-decisions line says "identity golden file approved" (2026-10-25).

## Phases

Test command, stack loaded: `taskset -c 0-5 nice -n 10 python -m pytest -q <files>`. One pytest session at a time; the slow suite alone.

| # | Phase | Verified when | Blocked by | Size |
|---|---|---|---|---|
| 1 | [I-10 shadow machine root](P1_shadow_root.md) | fast and slow suites as before; a guard proves `~/Himinbjorg`'s own files untouched | none | M |
| 2 | [I-11 golden identity file](P2_golden.md) | the developer's word on the contradiction, then a test compares every fixture point's parts | 1 | S |
| 3 | [I-12 baselines](P3_baselines.md) | the suites' results recorded; `heimdall status` of a real study's configs recorded read-only; local tag `pre-restructure` | 2 | S |
| 4 | [I-28 record formats](P4_formats.md) | `format = 1` written; old files read; `heimdall records upgrade --dry-run` lists what it would do | 1 | M |

## Decision log

| Decision | Chosen | Why |
|---|---|---|
| Scope of ISSUES planned now | the safety net (developer, 2026-11-07) | The library and the stats format change records; the net comes first (ISSUES' order) |
| Shadow root | real `stack/`, `base/`, `apps/`, `forge/downloads/` linked; own `machine.toml`, `recipes.toml`, `runs/`, `workdirs.toml` | Tests keep the built stack without reading the live settings |
| Golden file | binaries' sha256 masked | A rebuilt app must not fail the gate; a changed card must |

## Not yet specified

- Phase 2: the developer settles I-11's held vs approved.
- Phase 3: which real study's configs `status` is run against. The developer names it at the step. It is read-only, and its name never enters the repo.

## Always / Never

- Always: back up a live file before changing it (never needed here: nothing live is changed); restore nothing after a failed run, report.
- Never: rewrite `~/Himinbjorg`'s `machine.toml`, `recipes.toml`, `toolkits/`, `tools/`; touch `tests/reference/`; name a real study.

## Progress

| Phase | Status |
|---|---|
| Plan | approved 2026-11-07 |
| 1 | done 2026-11-07 |
| 2 | done 2026-11-07 |
| 3 | done 2026-11-08 (baselines recorded; tag `pre-restructure` local) |
| 4 | done 2026-11-07 |
