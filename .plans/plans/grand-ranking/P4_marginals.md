# P4 · Quantity marginals

Verified when: marginals are gated, trimmed (α = 0.2) and matched; each row carries n, g, vetoed, unmatched, e^E ± SE, e^M and the comparison with the best; the small-n rules hold; the old "mean" that was an RMS is gone with its note.

### 4.1 The trimmed mean and its SE (XS)
- Acceptance: `stats/means.py` gains `trimmed(values, alpha) → (mean, se, n, g)`, 03 §2.3; property 8.
- Files: `framework/stats/means.py`, `tests/runner/test_stats_means.py`.
- Check: `source gjallarhorn.sh; cd tests; taskset -c 0-5 nice -n 10 python -m pytest runner/test_stats_means.py -q`
- Seam: a hand-computed sample.
- Blocked by: P3.

### 4.2 Matched marginals (M)
- Acceptance: `score.marginals` returns rows of 03 §2.4; strata over every other varied quantity; vetoed points out and counted; paired against the best; properties 6 and 7; the method record's marginal rows; the confounding sentences kept for a quantity with no matched effect.
- Files: `framework/stats/score.py`, `tests/runner/test_stats_score.py`.
- Check: `source gjallarhorn.sh; cd tests; taskset -c 0-5 nice -n 10 python -m pytest runner/test_stats_score.py -q -k marginal`
- Seam: built designs: balanced; a stratum shifted by a constant; a slice half vetoed; n = 0, 1, 2, 3.
- Blocked by: 4.1.

## Log
