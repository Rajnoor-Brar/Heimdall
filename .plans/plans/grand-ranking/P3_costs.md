# P3 · Compressed costs and the default set

Verified when: costs are oriented and compressed as 03 §1.2; the nine defaults of 02 are on; each category's ranking applies the gate; the summary fixtures are rewritten with the tests that need them.

### 3.1 Orientation and compression (S)
- Acceptance: `Metric.cost(value)` = log₂(1 + z) with q by polarity and scale; `higher` on a log scale (`n_eff`); properties 2 and 5 of 03 §3.
- Files: `framework/stats/metrics.py`, `framework/stats/score.py`, tests.
- Check: `source gjallarhorn.sh; cd tests; taskset -c 0-5 nice -n 10 python -m pytest runner/test_stats_metrics.py runner/test_stats_score.py -q`
- Seam: `Metric.cost`.
- Blocked by: P2.

### 3.2 The curated defaults (M)
- Acceptance: `default` on the nine of 02; `n_eff` shown, not scored; `test_exactly_the_five_are_on_by_default` becomes the nine; `test_stats_score.py:80`'s single-default assumption goes; `[stats].metrics`'s generated default follows the registry.
- Files: `framework/stats/metrics.py`, `framework/schema/run.toml`, `tests/runner/test_stats_registry.py`, `tests/runner/test_stats_score.py`, `tests/runner/test_summary_layout.py`, the fixtures those read.
- Check: `source gjallarhorn.sh; cd tests; taskset -c 0-5 nice -n 10 python -m pytest runner/test_stats_registry.py runner/test_stats_score.py runner/test_summary_layout.py -q`
- Seam: the registry and the summary model.
- Blocked by: 3.1.

## Log
