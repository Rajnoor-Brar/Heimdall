# Phase 3: I-12, baselines before the restructure

Status: done 2026-11-08.

### Step 3.1: record and tag (Size: S)
- Acceptance: the fast and slow suites' results (pass, fail and skip counts, failing ids) are written in this file's log. `heimdall status` of a real study's configs, read-only and from its own work dir, is kept outside the repo with its path written here as "a real study's work dir". The local tag `pre-restructure` is on the commit. Nothing is pushed.
- Check: `git tag -l pre-restructure`
- The study is named by the developer at this step, and never in the repo.

## Log
- 2026-11-08, at `99d92fb`, stack loaded, `taskset -c 0-5 nice -n 10 python -m pytest -q tests` (the slow tests are in it, no deselection): **2288 passed, 10 skipped, 6 failed in 16 min 33 s.** Failing ids, all known (see Implementation_Issues): `tests/integration/test_gates_p1.py::test_the_legacy_reference_is_reproduced_byte_for_byte[MSTW]` and `[NNLO]`; `tests/runner/test_detach.py::test_the_first_signal_stops_cleanly_the_second_hard` (flaky); `tests/runner/test_docs.py::test_the_code_a_page_names_exists[stable/internals/plot-backends.md]` and `::test_the_rank_table_is_the_runners` (stable pages; F-6); `tests/runner/test_stack_build.py::test_the_old_way_is_apt_and_a_venv`.
- The real study: a real study's work dir, a new small errand run by the developer's order (four PDFs, Pythia only, 10k events): 4 done, 0 failed. Its `status`, `score --json` and `runs` outputs are kept outside the repo, in `~/heimdall-baselines/pre-restructure/`.
- Tag: `pre-restructure` is local, on the commit that carries this log. Nothing is pushed.
