# P7 · Benchmarks ⏸

Verified when: 05's acceptance list holds on the implemented engine for B1–B4, and the developer has read one summary (I-136).

### 7.1 The probe against the engine (S)
- Acceptance: `probe/bench.py` gains `--engine`, scoring with `stats.score.rank` instead of its own copy; every point's loss agrees to 1e-9; 05's six acceptance items hold.
- Files: `.plans/plans/grand-ranking/probe/bench.py`.
- Check: `source gjallarhorn.sh; python -I -W ignore .plans/plans/grand-ranking/probe/bench.py --engine B1=… B2=… B3=… B4=… --bad …` (the arguments as in 05; B3 and B4 from a scratch re-measure).
- Seam: the four Runs, read only.
- Blocked by: P6.

### 7.2 ⏸ Rescore the four Runs (only on the gate's yes to question 10) (S)
- Acceptance: a snapshot of each Run's `statistics/` first; `heimdall plot <A>/<E>/<R> --stats-only` on each; the leaderboard and marginals compared with the probe's; the developer reads B1's and B4's summaries.
- Files: none in Heimdall; the work dir's `statistics/` and `.cache/…/plots/`.
- Check: the comparison's output, written to the round's log.
- Blocked by: 7.1, and the developer.

## Log
