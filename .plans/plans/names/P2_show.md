# Phase 2: `heimdall show`

Status: done 2026-11-08. Blocked by: none.

### Step 2.1: Run and point (Size: M)
- Acceptance: `heimdall show <A>/<E>/<R>[/<point>[/<tag>]] [--parts] [--json]` prints 00_Plan's views, read-only, from `points.json`, `provenance.json`, `identity.json`, `attempts.jsonl` and the logs. σ comes from the products where a reader exists, and is otherwise "–" with the reason.
- Files: `framework/runner/cli.py` (parser and thin handler), `framework/runner/house.py` (the views, beside `log_target`), `tests/runner/test_show.py` (new).
- Check: `taskset -c 0-5 nice -n 10 python -m pytest -q tests/runner/test_show.py`

### Step 2.2: `log` as `show --log` (Size: S)
- Acceptance: `show --log`, `--full` and `--attempt N` give exactly today's `log` output. `heimdall log …` is the same command. `docs/reference/commands.md` is regenerated.
- Files: `framework/runner/cli.py`, `tests/runner/test_logging.py`, `tests/runner/test_show.py`.
- Check: `taskset -c 0-5 nice -n 10 python -m pytest -q tests/runner/test_logging.py tests/runner/test_show.py`
- Live doc: `docs/live/show.md`.
- Blocked by: 2.1.

## Log
- 2026-11-08: `show` (Run, point, tool, `--parts`, `--json`) and `show --log/--full/--attempt` as `log`'s output; `log` unchanged. `tests/runner/test_show.py` 5 pass with test_logging and test_runlog; docs regenerated; `docs/live/show.md`.
