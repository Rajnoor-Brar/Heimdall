# Phase 6: known reds

Status: done 2026-11-09 (6.1–6.3). Blocked by: phase 0. Closes T-1 and F-9 together with P7, which fixes the two docs tests by the crystallise.

No reason text may name an issue id or `.plans/`, because `test_docs.py:275` refuses both in code. Say what the mark waits for in words.

### Step 6.1: the two legacy gates (Size: XS)
- Acceptance: `tests/integration/test_gates_p1.py::test_the_legacy_reference_is_reproduced_byte_for_byte`'s two cases (`MSTW`, `NNLO`) carry `pytest.mark.xfail(strict=True, reason="the conda base's stack writes byte 323 of the YODA differently; the reference stands, and whether to accept the digit is the developer's open decision")`. Put the mark on the parameters (`pytest.param(..., marks=...)`) so any other case stays a plain test. `tests/reference/` is untouched (by the developer's word of 2026-11-09: marks only). Mark I-79 in `ISSUES.md` with "(the gates are strict xfails until decided)".
- Check: alone, `taskset -c 0-5 nice -n 10 python -m pytest -q tests/integration/test_gates_p1.py -rxX` shows them `XFAIL`. `git diff --stat tests/reference` is empty.

### Step 6.2: the conda-root test (Size: XS)
- Acceptance: `tests/runner/test_stack_build.py::test_the_old_way_is_apt_and_a_venv` is skipped when Himinbjorg's base is a conda base. Detect this with the helper the stack code already uses to tell the base (`grep -rn "conda" framework/runner/paths.py framework/runner/bifrost.py recipes/settings.toml` finds it), not with a new probe. Reason: "asserts no pixi on the path, which a conda base has". Add a note to I-77 in `ISSUES.md`: "skipped on a conda root until the base is decided".
- Check: `taskset -c 0-5 nice -n 10 python -m pytest -q tests/runner/test_stack_build.py -rs` shows it skipped here.

### Step 6.3: `test_detach::test_the_first_signal_stops_cleanly_the_second_hard` (Size: S)
- Acceptance: run it alone three times (`-x -q`) and read the failures. Then:
  - **The test's timing** (a wait or deadline that `taskset` or `nice` makes too short): make the test wait for the state it needs, by polling the registry or the log as other `test_detach` tests do, never by a longer sleep, and never by loosening an assertion.
  - **A real defect in signal handling** (`cli.catch_signals` and kin): fix it, with the test failing first and passing after. If the fix is outside `cli.py`'s signal code, use the stop rule.
  - **Neither, within the step:** a strict xfail whose reason says the cause seen, plus an Implementation_Issues entry with the output.

  The log holds the three runs' outcomes.
- Check: alone, five runs in a row pass, or the xfail shows `XFAIL`.

## Log

- 6.1: the two cases `MSTW` and `NNLO` of `test_the_legacy_reference_is_reproduced_byte_for_byte` are `pytest.param(…, marks=LEGACY_DIGIT)`, a strict xfail with the plan's reason. Check: `test_gates_p1.py -rxX` alone: `1 passed, 2 xfailed` (30 s); `git diff --stat tests/reference` empty. `ISSUES.md` I-79 says "(the gates are strict xfails until decided)".
- 6.2: `test_the_old_way_is_apt_and_a_venv` has `skipif(paths.base_dir() is not None, …)`: `paths.base_dir()` is the helper that says whether a conda base is loaded (`$HEIMDALL_BASE`); the grep the plan named found no other. Check: `test_stack_build.py -rs`: `83 passed, 1 skipped`, the skip with the plan's reason. I-77 has the note.
- Off-plan: 6.1 and 6.2 are one commit (both only name a known red by a mark, and ISSUES.md holds both notes).
- 6.3: alone, three runs in a row passed (0.22 s each), so the flake needed a cause that a plain run does not have. The test asserts `catch_signals` replaced all three handlers, and `catch_signals` leaves SIGHUP alone when it was ignored at the start (nohup). A pytest started by `setsid nohup …` or from a detached shell ignores SIGHUP, so the assertion's `SIGHUP` item was missing. Reproduced: `bash -c 'trap "" HUP; pytest …test_the_first_signal_stops_cleanly_the_second_hard'` failed first on the old test (`Extra items in the right set: SIGHUP`), the full `test_detach.py` passes under the same trap now (22 passed), and five plain runs in a row pass. Not a defect in `catch_signals` (leaving an ignored SIGHUP alone is its stated rule, and `test_an_ignored_sighup_stays_ignored` proves it); the test now sets SIGHUP to the default first, as that sibling test sets it to ignored. The assertion is as it was.
