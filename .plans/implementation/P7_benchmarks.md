# Phase 7: the benchmarks ⏸

Status: not started. Blocked by: phase 8. Ordered 2026-11-11 (the second gate, answer 3): the four Runs are a real study's, found by their shapes in its work dir and by the design session's probe line; they are read from their standard results and cache folders, and everything written goes to `forge/scratch/grand-ranking/`. The work dir is not written. Source: [05](../plans/grand-ranking/05_Benchmarks.md).

The four Runs are a real study's. Here and in every commit they are B1, B2, B3, B4, as 05 names them. Their addresses come from the developer with the order, are used on the command line only, and are written nowhere in this repo: not in a log, not in a test, not in a commit message.

### Step 7.1: the probe against the engine (Size: S)
- Acceptance:
  - `probe/bench.py` gains `--engine`: it scores with `stats.ranking.rank` and `ranking.marginals` in place of its own copy, and prints both side by side.
  - B3 and B4 have no measured bins in their records: they are re-measured into `forge/scratch/grand-ranking/remeasure/` as 05 says (Paint's `--ranges-only`, reading the work dir, writing scratch only).
  - 05's six acceptance items hold, read under phase 8's defaults. Each is a line of the log with its number: with the defaults, every pathological point ranks after every ordinary one by its loss, and none is vetoed; with `gates = true`, the vetoed counts (12, 6, 1, 0) and vetoed last in every category ranking; the largest category share per Run (under 50 %); B4's rank correlation with today (≥ 0.9) and its marginal order; B1's jet-radius marginal with dr32 last and distinguishable; the largest loss difference between probe and engine (≤ 1e-9).
  - R17: the share of the loss owned by `pull_autocorr` and by `log_ratio_roughness` on each Run is in the log.
  - An item that does not hold is an Implementation_Issues entry with the numbers. It is not tuned away: no threshold, gate level or default changes in this phase.
- Files: `.plans/plans/grand-ranking/probe/bench.py`; this log.
- Check: `python -I -W ignore .plans/plans/grand-ranking/probe/bench.py --engine B1=<results>:<pages> B2=… B3=… B4=… --bad B1=<glob> …`, the arguments as 05 gives them, with the stack loaded.
- Seam: the four Runs, read only.
- Blocked by: 6.2, the developer.

### Step 7.2: rescore the four Runs into scratch (Size: S)
Replaces the rescore in the work dir: the second gate's answer 3 has every output in a temporary folder, so nothing is snapshotted or restored.
- Acceptance:
  - **Look first.** Each Run's `statistics/totality/` is listed with sizes; `heimdall status` is not needed, since nothing is written there.
  - **Rescore.** For each Run, its `statistics.csv` and sidecar (B3 and B4: the re-measured table of 7.1) are ranked with today's defaults, and the set's summary (`summary.pdf`, `.html`, `statistics.json`) is written to `forge/scratch/grand-ranking/after/<B>/`, through `statstable.write_set`, under `taskset -c 0-5 nice -n 10`. A report of B1 and B4 (`heimdall report` with a recipe in scratch) is built into scratch too.
  - **Compare.** For each Run, the old summary's order against the new: the points whose rank moved by more than five places, each with its reason from the record; the marginals against 05's tables; the engine's losses against the probe's.
  - **Hand over.** The log says where B1's and B4's summaries and the report are, by B-name and scratch path.
  - The work dir is unchanged: a listing of the four Runs' `statistics/` by mtime, before and after.
  - If a command fails or is interrupted: restore nothing, report the state.
- Files: none in Heimdall but this log. In scratch: `forge/scratch/grand-ranking/`.
- Check: the comparison, written in this log without an address.
- Blocked by: 7.1.

## Log
