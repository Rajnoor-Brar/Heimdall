# Phase 2: small fixes

Status: not started. Blocked by: phase 0. One commit per step, and each step marks its finding. Phase check: the fast suite (`taskset -c 0-5 nice -n 10 python -m pytest -q tests/runner -m 'not slow'`) has only the known reds.

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
