# Phase 7: the benchmarks ⏸

Status: done 2026-11-11. Blocked by: phase 8. Ordered 2026-11-11 (the second gate, answer 3): the four Runs are a real study's, found by their shapes in its work dir and by the design session's probe line; they are read from their standard results and cache folders, and everything written goes to `forge/scratch/grand-ranking/`. The work dir is not written. Source: [05](../plans/grand-ranking/05_Benchmarks.md).

The four Runs are a real study's. Here and in every commit they are B1, B2, B3, B4, as 05 names them. Their addresses come from the developer with the order, are used on the command line only, and are written nowhere in this repo: not in a log, not in a test, not in a commit message.

### Step 7.1: the probe against the engine (Size: S)
- Acceptance:
  - The probe is ranked by `stats.ranking.rank` beside an independent computation of the same loss, side by side. `probe/bench.py` imports `stats.score` and today's old ids, which phase 1 renamed, so the comparison is a new `probe/engine.py` (see the log).
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
- **7.1 · done 2026-11-11.**
  - **The probe.** `bench.py` no longer runs: it imports `stats.score` and the old ids. `probe/engine.py` replaces it for this phase. It makes each Run's rows with Heimdall's own `table.statistics_of`, from measured bins, for every page of the Run's `totality`. It ranks them with `ranking.rank`, under the defaults and under `gates = true`. It computes the same loss independently by hand: the hinge, log₂(1 + z), RMS in a category, over categories and over pages.
  - **Inputs.**
    - B1 and B2 are read from their Runs' cache.
    - B3 and B4 are re-measured into `forge/scratch/grand-ranking/remeasure/`: 456 page documents copied with their output moved, then `Paint.exe --ranges-only`, two at a time, with 0 failures and 456 `stats.json` files.
    - The work dir was only read.
  - **05's items, under phase 8's defaults:**
    1. *Pathological points last, by loss, none vetoed:* B1 ranks 13–24 of 24 (ordinary losses up to 2.56, pathological 11.4–12.9); B2 ranks 19–24 of 24 (up to 2.22, then 11.3–12.8); B3 rank 16 of 16 (up to 2.08, then 11.6). **Holds.**
    2. *With `gates = true`, vetoed 12, 6, 1, 0:* exactly, every one pathological. The vetoed come after every passing point, the first passing point is rank 1, and the vetoed are last in every category ranking. **Holds.**
    3. *The largest category share of the ordinary loss is under 50 %:* B1 38 (compatibility), B2 42 (compatibility), B3 33 (trend), B4 31 (trend). Integrity is 0 on every ordinary point. **Holds.**
    4. *B4's rank correlation with today ≥ 0.9:* Spearman 0.961. Against 05's "today" (five metrics, linear, no gate), B1 is 0.594 and B2 0.255, which are 05's own numbers, independently reproduced. B4's marginals keep 05's order: lpdfon ×0.87 against lpdfoff; qedLoff ×0.97; p_T,ref 40 best, with 24–28 worst and distinguishable. **Holds.**
    5. *B1's jet radius, dr32 last and distinguishable:* with `gates = true`, dr32 is last at ×0.658 ± 0.100 against the best, distinguishable. **With the defaults, dr32 is last but "indistinguishable"** (×0.839 ± 0.193). The broken PDF's points now stay in the marginals: two of B1's four jet-radius strata are theirs, with losses of 11–13 that vary page to page, and their noise inflates the SE. B3's PDF marginal shows the same: by default the broken PDF reads "indistinguishable from the best" (×0.357 ± 1.018 on two strata). **Does not hold under the defaults.** It is an issue, not tuned away.
    6. *Largest loss difference between probe and engine ≤ 1e-9:* 1.8e-15 (B1–B3), 4.4e-16 (B4), with infinities agreeing. **Holds.**
  - **R17, each metric's share of the ordinary points' squared loss:**
    - `pull_autocorr`: B1 0.7 %, B2 0.2 %, B3 0.7 %, B4 1.1 %.
    - `log_ratio_roughness`: 3.2 %, 5.5 %, 4.1 %, 3.3 %.
    - Neither owns the loss, so neither is retuned. The largest single metric is `poisson_dev` (20–41 %), then `tilt` (26–31 %).
- **7.2 · done 2026-11-11.**
  - **Look first.** The four Runs' `statistics/` came to 43 files; their sizes and mtimes were listed to `forge/scratch/grand-ranking/before.txt`.
  - **Rescore.** `probe/engine.py --out` rebuilt each Run's `totality` through `statstable.write_set` into `forge/scratch/grand-ranking/after/<B>/results/<A>/<E>/<R>/statistics/totality/`, beside a copy of the Run's `plot.toml`, with `HEIMDALL_RESULTS` at that scratch root. It wrote `statistics.csv`, `.json`, `summary.pdf`, `summary.html` and the bars: B1 288 rows and 49 images, B2 288 and 73, B3 192 and 25, B4 3456 and 433. B3 and B4 come from 7.1's re-measured pages.
  - **Report.** `heimdall report` of B1 and B4, with every `HEIMDALL_*` root in `forge/scratch/grand-ranking/report/` (a scratch `heimdall.toml` marks its work folder). The output is `report/out/report.pdf`, 65 A4 pages: the statistics of both in HEADLINE's order and "How the numbers are made". Pages and tools are left out, since only the statistics were copied.
  - **Compare, before against after.** "Before" is the engine at `4d225a3` (a `git archive` in `forge/scratch/grand-ranking/old/`) on each Run's own table in the work dir, as its old summary showed it. "After" is today's engine on the rescored table. `probe/compare.py` gives:
    - **B1:** Spearman 0.894; 2 moved more than five places. An ordinary point fell from 1 to 10: 45 % of its loss is compatibility, its worst page d12. One pathological point rose from 19 to 13, still inside the pathological block.
    - **B2:** Spearman 0.685; 6 moved, all ordinary. The largest moves are 2 → 17 and 5 → 18 (compatibility 50–56 % of their loss, worst page d08) and 18 → 8 (trend and compatibility). This is the default set's weight on compatibility, as 05 §2 predicted (B2's Spearman against today 0.255 there).
    - **B3:** Spearman 0.853; none moved.
    - **B4:** Spearman 0.628; 268 of 288 moved. Its table in the work dir was measured before Paint wrote bins, so its old summary was ranked on χ²/ndf and the fixed columns alone. Against 05's "today" made from the full bins, it is 0.961 (7.1). The movers split by lepton PDF: lpdfon points rose (246 → 67, 225 → 52, …: most of their loss is compatibility), and lpdfoff points fell (45 → 216, 65 → 225, …: most is trend and accuracy). That is the lepton-PDF marginal's ×0.87.
    - Every moved point's reason is its record's category shares and worst page, as printed.
    - The marginals are in 7.1. Engine against probe agree to 1.8e-15.
  - **The work dir is unchanged by this phase.** The four Runs' `statistics/` listing after is identical to the one before: 43 files, the same sizes and mtimes. Files elsewhere in the work dir did change meanwhile (`.cache/<A>/sherpa`, `records/…/run.jsonl`, `results/…/points`), from the developer's own Sherpa and Rivet runs. Two of those are on B1's Run, so B1's rescored summary is its state at 00:39.
  - **Hand over:**
    - B1: `forge/scratch/grand-ranking/after/B1/…/statistics/totality/summary.pdf` and `.html`;
    - B4: `after/B4/…/summary.pdf` and `.html`;
    - the report: `forge/scratch/grand-ranking/report/out/report.pdf`.
    - R18 is replaced by the second gate's answer 3: nothing to keep or restore in the work dir.

