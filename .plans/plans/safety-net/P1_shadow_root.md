# Phase 1: I-10, a shadow machine root for the tests

Status: done 2026-11-07. Blocked by: none.

### Step 1.1: build `forge/scratch/machine/` (Size: M)
- Acceptance: `conftest` builds `<scratch>/machine/`. `stack/`, `base/`, `apps/` and `forge/downloads/` are symlinks to the real root's. `machine.toml`, `recipes.toml`, `runs/` and `workdirs.toml` are its own, made empty or minimal from `recipes/machine.template.toml` and `recipes.template.toml`. `HEIMDALL_MACHINE` points at it for the session. Scratch itself stays where it is (`<real root>/forge/scratch`).
- Files: `tests/conftest.py`, `tests/support.py` if helpers move.
- Check: `taskset -c 0-5 nice -n 10 python -m pytest -q tests/runner`, then alone `taskset -c 0-5 nice -n 10 python -m pytest -q tests/integration`. Results are as before (record the before counts first, from the same command).

### Step 1.2: the guard (Size: S)
- Acceptance: a session guard, beside the fixtures' hash guard, hashes `~/Himinbjorg`'s `machine.toml`, `recipes.toml`, `.stamps/` and `apps/` listing before and after, and fails the session on a change.
- Files: `tests/conftest.py`.
- Check: as 1.1.
- Blocked by: 1.1.

## Log

2026-11-07, at `cd6ceac` plus the tree's open work:
- Before (live root, no shadow): fast `-m "not slow"` 3 failed, 1769 passed, 10 skipped, 49 deselected. The failures: `test_detach::test_the_first_signal_stops_cleanly_the_second_hard`, `test_docs::test_the_generated_pages_are_current` (`docs/MAP.md` stale), `test_stack_build::test_the_old_way_is_apt_and_a_venv` (I-77).
- Shadow built (`conftest._shadow_machine`), guard added (`the_live_machine_root_is_left_alone`), `tests/runner/test_shadow_root.py` added.
- One test depended on the basetemp lying inside the live root: `test_lifecycle::test_the_provenance_is_portable` found its card path unportable. It now puts its records under the work dir.
- After, fast: the same 3 failures, the rest passed (1770 + the fix; `test_lifecycle.py` rerun alone, 9 passed).
- After, slow `-m slow`, alone: 3 failed, 46 passed. The failures are known: `test_gates_p1` MSTW and NNLO (I-79), `test_plot_stage` pixel test for yoda (I-43). No before count for slow; those three match the issues' own account. The guard did not fire.
