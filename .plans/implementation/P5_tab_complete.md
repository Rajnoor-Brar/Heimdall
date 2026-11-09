# Phase 5: tab completion (I-73)

Status: done 2026-11-09 (the tab-complete plan's P1–P4). Blocked by: phase 1 (the run kind reads `RunEntry`).

The spec is [the tab-complete plan](../plans/tab-complete/00_Plan.md) and its four phase files. Its decisions D1–D7 are final: D3 and D5 were decided as proposed on 2026-11-09. Edit its header's status line to say so when this phase starts. Run its phases P1 → P4 in order, each by its own named check, and write each one's log in its own file.

**Additions to that plan, from this round:**
- **The run kind** (its P2, D4) reads the registry without pruning: `runs._own(sorted(runs.folder().glob("*.json")), mine=True)`, parsed as `RunEntry` (P1.2). It never calls `runs.entries()`, which prunes and so writes.
- **`complete.py` is a new module at rank 5.** Its row in `docs/stable/internals/runner.md` is written at P7, not here. The tab-complete plan's live doc (its P4) names it under **Stable pages need**.
- **Its P4 deletes the plan folder and I-73**, as written there. In this round's ledger that closes `plans/tab-complete/`.

Check: the tab-complete plan's P3 check (`bash -c` with `COMP_WORDS` set gets the expected `COMPREPLY` for each kind), then the fast suite.

## Log

- **P1–P3 (one commit, the plan's P4 live doc with them).** `framework/runner/complete.py` (rank 5; its row added to `RANKS`), the hook at the head of `cli.main`, `env/complete.bash`, and the wiring in `env/heimdall_env.sh` (sourced beside the functions, before the early return; `quit` runs `complete -r heimdall`). The walk reads `cli.parser()`; the kinds are `KINDS`, the free text `FREE`; the retired stubs `stats` and `deck` are left out. The run kind globs the registry through `runs._own` and never calls `runs.entries()`. Tests: `tests/runner/test_complete.py`, 22: the walk, the coverage of every positional and value-taking option, each kind on the scratch work dir (errand and its Runs, drawing taking `results/` too, configuration, check/migrate/clean, deep, record, result, scope, report, files, schema keys, tools, help, run ids and pids, states), a broken errand giving nothing, no work dir giving no path kinds, nothing written (the work dir, `records/`, `results/` and the registry's mtimes the same before and after twenty completions as a program, stderr empty), each kind within 150 ms in-process, a reader failing giving `:plain`, and bash: `bash --noprofile --norc -c` with `COMP_WORDS` set gets the expected `COMPREPLY` and `compopt` calls for a command, an errand, a `/` level (`nospace`), `./` files and folders (`.toml` only), `heimdall cd`, `quit`/`refresh`, and the environment file wiring the spec in and `quit` removing it. Checks: the test file 22 passed; fast suite 2224 passed, 10 skipped, 3 known reds. Live doc: `docs/live/tab-complete.md` (`affects: environment`; the Decisions hold D1–D7 and the three off-plan ones).
- **Close-out.** `.plans/plans/tab-complete/` is deleted (`git rm`; it stays in the history) and I-73 is gone from `ISSUES.md`; the plan's own P1–P4 logs went with it, and this entry is their record. The plan's header status line was not edited: the folder went in the same change.
- **Timing.** `heimdall __complete` as a program takes about 100 ms with Python's start (measured on the scratch work dir); the in-process answer is a few ms. The test bounds the program loosely (2 s) and each kind at 150 ms in-process, so a loaded machine does not make it flaky.
- **By hand, not done:** `heimdall run <TAB><TAB>` in an interactive shell on a real work dir. That needs the developer's own work dir, and the agent does not cd into one unasked. `compopt` is checked for (`type compopt`): a bash before 4 gets no `nospace`; the lab PC's is bash 5.3, and the cluster login node's was not checked.
