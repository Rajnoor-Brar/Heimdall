# Phase 2: small fixes

Status: done 2026-11-09 (2.1–2.7). Phase check: fast suite 2197 passed, 10 skipped, 3 known reds. Blocked by: phase 0. One commit per step, and each step marks its finding. Phase check: the fast suite (`taskset -c 0-5 nice -n 10 python -m pytest -q tests/runner -m 'not slow'`) has only the known reds.

### Step 2.1: R-1, delete `cli.others_of` (Size: XS)
- Acceptance: `framework/runner/cli.py:543` `others_of` is deleted, together with any import that only it used.
- Check: `grep -rn others_of framework tests` prints nothing; `taskset -c 0-5 nice -n 10 python -m pytest -q tests/runner/test_one_cli.py tests/runner/test_flags.py tests/runner/test_plot.py`.

### Step 2.2: R-2, unused constants (Size: XS)
- Acceptance: these are deleted:
  - `plot.OUTSIDE` (`plot.py:55`);
  - `plotdoc.CHOSEN` (`plotdoc.py:43`);
  - `setup.REFRESHED` (`setup.py:373`);
  - `typeset.BAR_TRACK` (`plot/figures/typeset.py:34`);
  - `layout.TILED` (`plot/figures/layout.py:23`).

  `plotdoc.ATTRIBUTES` (`plotdoc.py:705`, `("@run", "@events", "@configuration", "@tag")`) is the list `load_across` adds. If `load_across` names those four literally, make it iterate `ATTRIBUTES`. If not, delete it. A comment that only described a deleted constant goes with it. In `ISSUES.md`, I-29 loses `layout.TILED`.
- Check:
  - `python .plans/audits/2026-11-08-code/sweeps/defs.py` lists none of the six;
  - `taskset -c 0-5 nice -n 10 python -m pytest -q tests/runner/test_plot.py tests/runner/test_across.py tests/runner/test_summary_layout.py tests/runner/test_setup.py`, with any of those files that do not exist left out.

### Step 2.3: R-3 and D-5, one point state (Size: XS)
- Acceptance:
  - `house.point_state` (`house.py:1047`) is deleted. `tests/runner/test_lifecycle.py:63,78` call `record.state_of(plan)[0]`.
  - `house.status`, `house.show_data` and `--plan`/`--why` (`cli.print_plan`, `print_why`) all take a point's state from `record.state_of`. If one of them works a state out its own way, point it at `state_of`, with a test of what it prints.
- Check:
  - `grep -n "def .*state" framework/runner/house.py framework/runner/record.py` finds one point-state function, `record.state_of`;
  - `taskset -c 0-5 nice -n 10 python -m pytest -q tests/runner/test_lifecycle.py tests/runner/test_status.py tests/runner/test_why.py tests/runner/test_attempts.py`.

### Step 2.4: R-9, `plot.py`'s re-exports (Size: XS)
- Acceptance:
  - The two `# noqa: F401 (… re-exported)` lines of `plot.py` (`:42`, `:46`) keep only the names `plot.py` itself uses.
  - Callers of the others import them from their owner: `labels` (`tlatex`, `lines_of`, `labels_of`, `root_text`, `macros`) or `statstable` (`statistics_of`, `heading_of`, `write_statistics`, `STATISTIC_COLUMNS`). These are `tests/runner/test_plot.py`, `tests/integration/test_plot_stage.py` and `tests/runner/test_statstable.py`.
  - `test_statstable.py:51–52`, which assert the re-export itself, are deleted with it.
  - `bars.py:15`'s docstring names `statstable.statistics_of`.
  - `statstable.py`'s own re-export of `stats.table` stays (00_Plan, R4).

  Mark R-9 closed, with "statstable's re-export kept: the import rule's door".
- Check:
  - `grep -rn "re-exported" framework` finds only `statstable.py`;
  - `taskset -c 0-5 nice -n 10 python -m pytest -q tests/runner/test_plot.py tests/runner/test_statstable.py tests/runner/test_imports.py`;
  - then alone, the slow `tests/integration/test_plot_stage.py`.

### Step 2.5: D-3, `log`'s options defined once (Size: XS)
- Acceptance: one helper in `cli.py` adds `target`, `--full` and `--attempt` to a parser, and `log` and `show` both call it. Each keeps its own help for `target`, passed in. `show` keeps `--parts`, `--json` and `--log`. The output of `log`, `show` and their `--help` is unchanged.
- Check: `taskset -c 0-5 nice -n 10 python -m pytest -q tests/runner/test_show.py tests/runner/test_docs.py`. Regenerate `docs/reference/` with the command `test_docs.py` names for it, and commit any change.

### Step 2.6: T-6, a sweep test's comments (Size: XS)
- Acceptance: in `tests/integration/test_gates_run_sweep.py`, the module docstring and the comment at `:125–127` say what the test proves now. Under `--plain`, a sweep runs its configurations one after another in its process (`docs/live/run-queue.md`), so the docstring holds. The added `twice` quantity makes the run take time. The `V75` cite (pipelining, retired) goes. Code is unchanged.
- Check: alone, `taskset -c 0-5 nice -n 10 python -m pytest -q tests/integration/test_gates_run_sweep.py`, and `tests/runner/test_docs.py`.

### Step 2.7: O-7, a pid's start time without `/proc` (Size: S)
- Acceptance: `runs.started_at(pid)` (`runs.py:78`) falls back, when `/proc/<pid>/stat` cannot be read, to the output of `ps -o lstart= -p <pid>`, stripped. That is `subprocess.run` with `capture_output`, `text`, a timeout of 2 s and `check=False`. It returns `""` when `ps` is missing, fails or prints nothing. `here()` and `alive()` are unchanged, since both go through `started_at`.
- Files: `framework/runner/runs.py`, `tests/runner/test_runs.py`.
- Tests:
  - with `runs._read` faked to `""` and `subprocess.run` faked by a real `CompletedProcess`, the fallback's text is returned;
  - a reused pid (another start text) is not alive;
  - a failed `ps` gives `""`.

  Mark O-7 closed, with "on Linux unchanged; proven on macOS only when I-82 runs there".
- Check: `taskset -c 0-5 nice -n 10 python -m pytest -q tests/runner/test_runs.py`.
- Live doc: one line in `docs/live/run-state.md`'s **Now holds**.

## Log
- 2.1 `git log --grep "others_of"`: `cli.others_of` deleted; `grep -rn others_of framework tests` prints nothing; `test_one_cli`, `test_flags`, `test_plot` green.
- 2.2 (same commit as 2.1, they share one test run): `plot.OUTSIDE`, `plotdoc.CHOSEN`, `setup.REFRESHED`, `typeset.BAR_TRACK`, `layout.TILED` deleted. `plotdoc.ATTRIBUTES` deleted too: `load_across` names `@run`, `@events`, `@configuration` and `@tag` literally, and `@tag` only when a run is tagged, so the tuple was not the list it added. Its comment shrank with it. I-29 lost `layout.TILED`. Check: `grep -rnw` of the six names prints nothing (the slow `defs.py` sweep was run in the background as well, result below); `test_plot`, `test_across`, `test_summary_layout`, `test_setup`, `test_imports`: 262 passed, 7 skipped.
- 2.3: `house.point_state` deleted; `test_lifecycle` calls `record.state_of(plan)[0]`. One point-state function remains (`grep "def .*state"` finds `record.state_of` and the run-state helpers of `house`). `house.status` already used it. Left as they are, on purpose: `show_data` reads the states a Run's `points.json` recorded (names P2: "the record alone", a decision), and `cli.print_plan`'s `(complete)`/`(to run)` is a two-word note of `is_complete`, not a point state; folding it into `state_of` would change what `--plan` prints. Check: `test_lifecycle`, `test_status`, `test_why`, `test_attempts`: 63 passed.
- 2.4: `plot.py` keeps only the names it uses (`canonical`, `labels_of`, `root_text`, `tlatex` from `labels`; `statistics_of` from `statstable`); `lines_of`, `macros`, `STATISTIC_COLUMNS`, `heading_of`, `write_statistics` are gone from it, with both `noqa` marks. `test_plot` imports `labels`'s, `test_statstable` and `test_plot_stage` use `statstable.…`; the test that asserted the re-export is deleted; `bars.py`'s docstring names `statstable.statistics_of`. `grep -rn re-exported framework` finds only `statstable.py`. Checks: `test_plot`, `test_statstable`, `test_imports` 177 passed; slow `test_plot_stage` alone 53 passed (3m47s). The `defs.py` sweep output holds none of the six names of 2.2.
- 2.5: `cli.record_options(parser, target_help, own=None)` adds `target`, then the command's own options, then `--full` and `--attempt`; `log` and `show` call it. One helper, with the `own` hook, so `show`'s `--help` keeps its option order. `log --help` and `show --help` are byte-identical before and after (captured from the old and the new parser); `make -s docs` changes nothing in `docs/reference/`. Checks: `test_show`, `test_docs` (two known reds), `test_runlog` green.
- 2.6: `test_gates_run_sweep.py`'s module docstring says a `--plain` sweep runs its configurations one after another in the command's own process, and the comment of `test_ctrl_c_starts_no_more_runs` says what the added `twice` quantity is for; the `V75` cite is gone. Code unchanged. Checks: the file alone, 6 passed (23 s); `test_docs` two known reds.
- 2.7: `runs.started_at` falls back to `ps -o lstart= -p PID` (2 s timeout, `check=False`) when `/proc/<pid>/stat` gives nothing, and returns `""` when `ps` is missing, fails or prints nothing. Test `test_a_pids_start_time_falls_back_to_ps_where_proc_cannot_be_read`: `_read` faked to `""` and `subprocess.run` faked by a real `CompletedProcess`; the text is returned, a reused pid (another text) is lost, a failed or missing `ps` gives `""`. `test_runs`: 58 passed. Live doc: a line in `run-state.md`. On Linux nothing changes.
- Off-plan: 2.1 and 2.2 are one commit (one test run proved both); every other step is its own commit.
