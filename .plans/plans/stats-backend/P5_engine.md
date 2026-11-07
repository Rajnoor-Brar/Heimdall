# Phase 5: settings and the scoring engine

Status: done 2026-11-07. Blocked by: phases 2 and 4.

### Step 5.1: schema (Size: S)
- Acceptance: `[stats].metrics` and `centres`; `[score]` with `metrics`, `normalise`, `thresholds`, `weights`, `mean`, `by`, `baseline`, `veto`, `aggregate`, `dominated`, `weights_by`; a set's `score`; a figure's `weight`. Unknown metric or mean names are refused with `did_you_mean`. Reference regenerated, not hand-written.
- Files: `framework/schema/run.toml`, `framework/runner/config.py`, `framework/runner/sweep.py` (`SET_KEYS`), `docs/reference/settings/plot.md` (generated).
- Check: `taskset -c 0-5 nice -n 10 python -m pytest -q tests/runner/test_config.py tests/runner/test_docs.py`, then `heimdall explain score`.
- Blocked by: none within the phase.

### Step 5.2: the engine (Size: M)
- Acceptance: `score.score(rows, settings)` → per point: score, worst page, veto, and per purpose the share. Loss is the RMS over purposes of the RMS within. Weights follow the precedence in 00_Plan. Head to head for one page returns pairwise differences. Rows in, scores out, no files.
- Files: `framework/stats/score.py`, `tests/runner/test_stats_score.py`.
- Check: `taskset -c 0-5 nice -n 10 python -m pytest -q tests/runner/test_stats_score.py`. One test turns on four shape metrics and checks shape still weighs one purpose; one checks that adding a curve leaves the others' threshold scores unchanged.
- Blocked by: 5.1.

## Log

2026-11-07: 5.1 done (schema, parse checks, explain; full fast suite: only the five known failures). 5.2 done: `stats/score.py`, 43 tests in `test_stats_score.py`; live doc `docs/live/score-engine.md`; one real point recomputed by hand. 3c done inside it.
