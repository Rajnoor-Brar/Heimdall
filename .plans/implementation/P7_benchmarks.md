# Phase 7: the benchmarks ⏸

Status: not started. Blocked by: phase 6, and the developer's order with the four Runs' addresses. Source: [05](../plans/grand-ranking/05_Benchmarks.md).

The four Runs are a real study's. Here and in every commit they are B1, B2, B3, B4, as 05 names them. Their addresses come from the developer with the order, are used on the command line only, and are written nowhere in this repo: not in a log, not in a test, not in a commit message.

### Step 7.1: the probe against the engine (Size: S)
- Acceptance:
  - `probe/bench.py` gains `--engine`: it scores with `stats.ranking.rank` and `ranking.marginals` in place of its own copy, and prints both side by side.
  - B3 and B4 have no measured bins in their records: they are re-measured into `forge/scratch/grand-ranking/remeasure/` as 05 says (Paint's `--ranges-only`, reading the work dir, writing scratch only).
  - 05's six acceptance items hold. Each is a line of the log with its number: the vetoed counts (12, 6, 1, 0); vetoed last in every category ranking; the largest category share per Run (under 50 %); B4's rank correlation with today (≥ 0.9) and its marginal order; B1's jet-radius marginal with dr32 last and distinguishable; the largest loss difference between probe and engine (≤ 1e-9).
  - R17: the share of the loss owned by `pull_autocorr` and by `log_ratio_roughness` on each Run is in the log.
  - An item that does not hold is an Implementation_Issues entry with the numbers. It is not tuned away: no threshold, gate level or default changes in this phase.
- Files: `.plans/plans/grand-ranking/probe/bench.py`; this log.
- Check: `python -I -W ignore .plans/plans/grand-ranking/probe/bench.py --engine B1=<results>:<pages> B2=… B3=… B4=… --bad B1=<glob> …`, the arguments as 05 gives them, with the stack loaded.
- Seam: the four Runs, read only.
- Blocked by: 6.2, the developer.

### Step 7.2: rescore the four Runs (Size: S)
The gate's yes to question 10 covers this step. It writes into a work dir, so it still goes in this order, and stops at the first surprise.
- Acceptance:
  - **Look first.** For each Run: `heimdall status` says nothing is running on it; its `statistics/` is listed with sizes.
  - **Snapshot.** Each Run's `results/…/statistics/` is copied to `forge/scratch/grand-ranking/before/<B>/`, and the copy is compared file by file (`diff -r`) before anything is rewritten.
  - **Rescore.** `heimdall plot <A>/<E>/<R> --stats-only` on each, one at a time, under `taskset -c 0-5 nice -n 10`. It rewrites the Run's `statistics/` and `.cache/…/plots/`, and nothing else: `git status` of the work dir, or a listing by mtime, shows that.
  - **Compare.** For each Run, before against after: the points whose rank moved by more than five places, each with its reason from the record; the marginals against 05's tables; the engine's losses against the probe's.
  - **Hand over.** The log says where B1's and B4's `summary.pdf` and `.html` are, by B-name. The developer reads them. R18 says what is kept.
  - If a command fails or is interrupted: restore nothing, report the state.
- Files: none in Heimdall. In the work dir: the four Runs' `statistics/` and `.cache/…/plots/`.
- Check: the comparison, written in this log without an address.
- Blocked by: 7.1.

## Log
