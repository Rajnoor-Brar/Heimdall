# P2 · Integrity gates

Verified when: `peak_bin_ratio` and `yield_sign` are metrics of the integrity category; a point failing a gate on any page is vetoed and ranks after every passing point; the summary and `rank` show the reason.

### 2.1 The gate metrics (S)
- Acceptance: `peak_bin_ratio` = log₁₀ max \|y\|/ref (03 §1.1); `yield_sign` on pages not normalised; `negative_share` (opt-in, MC quality); each with a built-spectrum test (a bin ×10⁴, a negative page, a clean curve).
- Files: `framework/stats/metrics.py`, `tests/runner/test_stats_metrics.py`.
- Check: `source gjallarhorn.sh; cd tests; taskset -c 0-5 nice -n 10 python -m pytest runner/test_stats_metrics.py -q`
- Seam: built spectra.
- Blocked by: P1.

### 2.2 The veto in the engine (S)
- Acceptance: `PointLoss` gains `vetoed`, `failed_pages`, `gate_reason`; the order of 03 §1.4; `[ranking].gates` and `veto_loss`; property 3 of 03 §3 holds for random losses.
- Files: `framework/stats/score.py`, `tests/runner/test_stats_score.py`.
- Check: `source gjallarhorn.sh; cd tests; taskset -c 0-5 nice -n 10 python -m pytest runner/test_stats_score.py -q`
- Seam: `score.rank(rows, settings)`, the engine's one entry.
- Blocked by: 2.1.

## Log
