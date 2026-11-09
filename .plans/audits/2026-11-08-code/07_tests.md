# Tests

100 test files with 1296 test functions: 78 files in `tests/runner/`, 25 in `tests/integration/`, plus `tests/cxx/` and the golden identity file `tests/golden/identity_parts.json`. 19 files are marked slow. The last full run (this session, at `21d8523`) was 2343 passed, 10 skipped and 6 failed, in 25 min.

## Findings

### T-1 Six failures that have become the background · Required · CONFIRMED · closed 6.1–6.3, 7.1
- The two legacy byte-for-byte gates (I-79, a digit at byte 323, waiting on the developer).
- `test_docs::test_the_code_a_page_names_exists[stable/internals/plot-backends.md]` and `test_docs::test_the_rank_table_is_the_runners`. Both are stable pages lagging the code, and need a crystallise (F-6, F-7).
- `test_stack_build::test_the_old_way_is_apt_and_a_venv` (I-77, a conda root).
- A sixth, cut off in this session's output. `Implementation_Issues.md` F-9 names `test_detach::test_the_first_signal_stops_cleanly_the_second_hard`.

Each has a reason, and none is the runner's fault. But a suite that is always red does not tell anyone that a new failure is new.
**Move:** make "known red" explicit. `xfail(strict=True, reason="I-79")` for the gates, with the developer's yes, since they are reference tests. A crystallise for the two docs tests. A `skipif` on a conda root for I-77. Then the suite is green, and a red is news. **Closes when:** a full run is green, or every red is a strict xfail naming its issue.

### T-2 The fixtures are all in the retired dialect · Required · CONFIRMED
See [R-7](01_dead-and-retired.md#r-7). The 11 fixture configs are v2, so v3 is proven only by `tests/runner/test_v3.py`'s own snippets. The translation is tested. The form users are told to write is not exercised end to end by the integration suite.
**Move:** the fixtures move to v3 as I-21's first step ([D-1](02_duplication.md#d-1)), together with the tests that read them (the fixture invariant). **Closes when:** the integration suite runs on v3 fixtures.

### T-3 Tests patch `cli.<name>`, so moving a function breaks them · Consider · CONFIRMED
14 `monkeypatch.setattr(cli, …)` sites. A patch on a module attribute fixes the function's module, so S-1's split must re-point each one. Patching at the seam (`runs.spawn`, `execute.run_points`), not at the CLI, survives refactors.
**Move:** with S-1, re-point the patches to the module that owns the function, and prefer the seam below the CLI. **Closes when:** no test patches `cli` for a function `cli` does not own.

### T-4 One shared scratch work dir · Consider · CONFIRMED (I-76)
The records accumulate across tests, so order matters and `pytest -n` cannot work. With the slow suite at about 25 min under `taskset -c 0-5`, parallel runs would pay for this.
**Closes when:** I-76's done-when holds.

### T-6 Comments that cite retired decisions · Nit · CONFIRMED · closed 2.6
`tests/integration/test_gates_run_sweep.py:127` cites V75 for "has not started all its points", pipelining this session retired. Its module docstring (`:1–4`) still describes the sweep in V38's terms. See [G-7](04_design.md#g-7).
**Closes when:** the test's comments say what it proves now.

## Sweeps still to run

- **Mutation.** For the queue and the library, flip one condition at a time in `wait_turn`, `library_key` and `link_library`, and confirm a test fails.
- **Loosened assertions.** `in stdout` substring checks where an exact line is known, and `>=` where `==` holds.
- **Fakes of the real type.** The invariant says a fake has the real type. Check fakes of `PointPlan`, `Errand`, `Configuration` and entries (dicts, by G-3, so the invariant cannot bite yet).
- **Time.** The ten slowest tests (`pytest --durations=10`), and which could use a smaller fixture. Event counts are capped at 5k (the developer's rule).
