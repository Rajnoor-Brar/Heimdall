# Plan: run logging (I-106), steps L0–L6

Approved 2026-10-26. Issue [I-106](ISSUES.md); audit [run_logging_audit.md](run_logging_audit.md). This file is the
execution map: each step's row is ticked when it is committed.

## Execution map

| Step | State | Commit | V-row | Gates |
| --- | --- | --- | --- | --- |
| L0 housekeeping | done | (this commit) | — | docs links |
| L1 quick fixes | to do | | | F, identity guard |
| L2 attempts, causes, run constants | to do | | | F, S, guard, B |
| L3 digests and history | to do | | | F, S, guard, B |
| L4 the run's own log | to do | | | F, S, guard, B |
| L5 new kinds in filters.toml | to do | | | F, S, guard |
| L6 the plot stage | to do | | | F, S |

## Context

The debug of `eic/zeus_validation` 04–11 (2026-10-25) kept hitting the same wall: what a run said was
gone, or buried. The audit `.plans/run_logging_audit.md` found:
- a failure's cause is not in the record;
- a successful point's warnings vanish;
- the tools' own numbers (`summary`, final σ) and Pythia's error statistics are dropped;
- Sherpa's mid-line errors are not recognised;
- `--logs` is 90–99 % counters and carries Sherpa's escape codes (169 of 690 saved logs);
- attempts are appended with no boundary;
- the run's own account lives only in a 30-day registry log outside the work dir.

This plan builds the audit's six steps. The outcome:
- every record says why each point ended, what warned and what the tools reported;
- it keeps a small clean digest per tool and a history of earlier attempts, and has its own event
  log;
- nothing saved holds terminal control bytes;
- **no point identity changes**.

## Decisions (yours, 2026-10-26, and two of mine)

| # | Decision |
| --- | --- |
| Scope | All six steps now (L1–L6), plus L0's housekeeping |
| L-D1 | Causes, warnings, digests and the run's event log are written by default. Live progress stays off disk (only `keep journal` writes it) |
| L-D2, L-D3 | `<tag>.log` is the digest, always written; `<tag>.full.log` is the whole clean output, with `--logs`. Earlier attempts go to `logs/<point>/history/<n>/`: the **9** newest attempts' digests and the **3** newest full logs are kept |
| Pace | Step by step: build, test, commit by named paths with its V-row, report, wait for your word |
| L-D4 (mine) | A detached worker's registry log gets a progress line every 10 minutes (today one a minute); `[run] log` can change it |
| L-D5 | A warning never changes an exit code |
| L-D6 | Raw bytes are never kept: every saved text is cleaned |
| L-D7 (mine, changed) | `cards/`, `commands.sh` and `context.toml` **stay** in `logs/<point>/`. Moving `cards/` would change argv's `{out}/cards/…`, so every identity (`tools.py:1433`). The "safe to delete" wording is fixed instead, and `history/<n>/` keeps each attempt's cards |

## Rules for every step

- **No run from this checkout may be in progress** while runner code changes (`heimdall runs`): a
  worker imports modules lazily (the plot stage at its end). If one is running, wait or ask.
- **Identity guard** (standing in for gate I until Phase 2's golden file): before L1, save the `--plan`
  identity lines of every fixture config and of Brookhaven's configs into the scratchpad, with
  `HEP_RECORDS`/`RESULTS`/`CACHE`/`REPORTS`/`RUNS` pointed there (nothing written to Brookhaven).
  After each step they must match exactly. **Gate B:** Brookhaven's `heimdall status` counts are unchanged.
- **Gates:** F after each step. S, alone, after L2, L3, L4 and L5, against today's baseline of 42
  passed and 5 known failures (I-09 ×2, I-79 ×2, I-43): no new failure.
- **Each step carries:**
  - its tests;
  - the manual it changes (06 §10, §12, §22–23; 04 §14; 02; 05; framework/01 §4.2);
  - a V-row (from V195);
  - I-106 updated (deleted at the end);
  - this plan's execution map, `.plans/run_logging_plan.md`, ticked.
- **Never write into Brookhaven or High-Energy.** Old records keep working: no `attempts.jsonl`
  means the cause is unknown. A record's history begins with its next attempt.
- **Reuse:**
  - `status.ANSI` (the cleaner's start);
  - `record.write_atomic` and `PointLock` (one writer per point);
  - `events.Journal` (the pattern for `RunLog`);
  - `runs.Recorder` (a bus subscriber for counts);
  - `hepfiles.yoda_text` and `entries` (the YODA reads);
  - `paths.keep_words`/`work_meta`/`machine_settings` (the `[run] log` settings);
  - `sweep.totality` and `set_cells` (the page count);
  - `build_stack.py:1747-1756` (rotation, the model).

## L0 — Housekeeping (no code)

- Save this file's Appendix A, the 2026-10-25 restructure plan, as `.plans/restructure_plan.md`, and
  this plan as `.plans/run_logging_plan.md`: the execution map, ticked as steps finish. Link both
  from `.plans/ISSUES.md` (its Plan section and I-106).
- Commit them with what is pending: ISSUES.md → `.plans/ISSUES.md`, `.plans/run_logging_audit.md`,
  `CLAUDE.md`, `docs/README.md`.

## L1 — Quick fixes (no format change)

1. **Clean text (C9).** `status.clean(text)`:
   - CSI and OSC sequences removed;
   - C0 controls removed, tab kept;
   - a line rewritten by a bare `\r` kept at its last state;
   - invalid UTF-8 replaced.

   It is used by the `--logs` write (line by line through `Reader.output`, instead of the raw chunk,
   `status.py:141`), by `keep_tail`, by `prelim.log` (`execute.py:343`) and by the worker's text.
2. **Sherpa's missing rules (B1)**, in `framework/tools/sherpa/filters.toml`, before the generic rule:
   - `error`: `Error in initialising ISR … Ignoring process`, `Cross section is 'nan'`,
     `Could not find a definition for`, `Missing input thrown`, `No hard process found`,
     `Wrong ordering of initial-state particles`;
   - `warn`: `exceeded frequency limit`;
   - the generic rule matches `\b(?:Error|ERROR)\b` anywhere in a line (`Integration_Error` doesn't
     match: `_` is a word character).
3. **Stall context (B4)** (`execute.py:451`): `silent for 5200 s since 20:29 (integrating; last line:
   "Starting the calculation at 20:29:41")`, from `ToolState.phase`, `last_line` and `last_activity`.
4. **Markup (D1):** the live view escapes its `say`, title and note lines before rich prints them
   (`watch.py:374`, `rich.markup.escape`).
5. **`--card` sources (D2)** (`tools.card_view`, `:1617`): for a render-style card, a line's top-level
   key gets its origin from `step.card_origins` (matched by the name before `[` or `:`). The folder's
   `owned` keys say "the plan"; the rest say "the base card".
6. **`--plan`'s page count (D4)** (`cli.py:513`): count `totality`'s pages (`sweep.totality`,
   `set_cells`), not `sweep.pages`.
7. **An empty analysis (B7):** Rivet's `tool.toml` gets `[checks] filled = "yoda:/RAW/"`. After the
   count check (`execute._settle`), `hepfiles.filled(path, prefix)` counts the histograms with entries;
   none gives a block note, "rivet: no histogram filled (0 of 13)".

**Tests:**
- a transcript with `ESC[31m`, `ESC[?25h`, `\r` counters and `\x07` leaves no control byte on disk and
  keeps the last counter state;
- Sherpa transcripts from runs 05, 07 and 11 (new files under `tests/fixtures/`, with their test) give
  the expected levels;
- the stall message;
- `[quantities.pdf]` survives the live view;
- `--card` on a Sherpa fixture;
- an empty YODA's note.

**Gates:** F and the identity guard.

## L2 — Attempts and causes (T0, T1)

- **The reader keeps signals.** `status.Reader` keeps warnings and errors deduplicated (`{msg: [count,
  first line]}`, at most 50 distinct), every `summary` and the last `xsec`. `status.apply` keeps
  `summary` (`status.py:224`).
- **The tool results carry them.** `execute.ToolResult` gains `stall` (phase, last line, silent since),
  `warnings`, `errors` and `reported` (summary, final σ ± err), filled by `run_group` from its readers.
- **`attempts.jsonl`** (`record.attempts_file`, `append_attempt`): one JSON line per attempt (`v = 1`)
  in `records/<run>/points/<point>/`, appended under the point's lock by `execute._finished` at every
  end (ok, failed, stopped, a prelim failure), the pre, post and combined stages included. A line holds:
  - `n`, `started`, `finished`, `identity`, the cards' sha256s;
  - `verdict`, `cause`, `blamed`, `message`;
  - `tools[]`: exit, seconds, cause, stall, warnings, errors, reported;
  - a cache hit's entry.
- **`provenance.json`** gains `tools[].reported` and `tools[].warnings`. **`points.json`**
  (`record.points_manifest`) gains `state` and `cause` from the last attempt.
- **`heimdall status`** (`house.point_state`, `house.status`) says `failed` or `stopped` instead of
  `incomplete`, with when and why: `sh3_NNPDF23lo  failed  2026-10-25 21:56  sherpa:prepare stalled
  (silent 5200 s)`.
- **The view** (`watch.State`): a block lists its warnings, e.g. `warnings: 3 (sherpa 2, rivet 1): Error in
  initialising ISR … Ignoring process (×2)`, at most 3 distinct shown. The verdict says `16 done (5 with
  warnings), 0 failed`, then a table of the failed points and their causes (a bus subscriber in
  `cli.run_one`, built like `runs.Recorder`).
- L1's empty-analysis note becomes a recorded warning.
- **The run's constants** (your ask, 2026-10-26): `points.json` gains a `constants` block, the
  settings every point of the run shares:
  - events, threads, parallelism, the seed rule;
  - the chain's groups, the stages;
  - the fixed quantities' values (tag, label, value);
  - each tool's tag, folder, executable, version and packages, and the analyses;
  - the base cards' names and sha256s;
  - the data reference;
  - the Heimdall and work-dir revisions, host, stack and image;
  - the point counts by state.

  The `run started` event carries the same block, so `run.jsonl` (L4) keeps it per invocation.
  `heimdall status` prints its first lines over the points.

**Tests:**
- `test_status.py`: the signals and the summary;
- `tests/integration/test_failures.py`: a failed, a stalled and a stopped fake tool each leave an
  attempt with its cause, and the stalled one its context; a rerun appends attempt 2;
- `test_house.py`: the cause in `heimdall status`;
- a successful point's attempt carries its summary.

**Gates:** F, S, the identity guard, B.

## L3 — Digests and history (T2)

- **The digest.** The reader keeps:
  - the head (100 lines) and the tail (200);
  - every matched line with its number (at most 500);
  - the counts of lines and progress lines.

  `Reader.write_digest`, always at a tool's end, replaces `keep_tail` (`status.py:173`). Its layout:
  a header (tag, attempt, started, exit, lines, progress), the head, `… N lines (M progress) …`, the
  matched lines, the tail; or the whole output when it fits. `--logs` writes `<tag>.full.log`. The
  same rules apply to `<tag>.prepare.log` (and `.prepare.full.log`) and to `prelim.log`.
- **History.** At an attempt's start (`execute.prepare`), the previous attempt's `*.log`, `*.full.log`
  and a copy of `cards/` move into `logs/<point>/history/<n>/`:
  - `n` comes from `attempts.jsonl`, or for an old record without one, the next free number;
  - the 9 newest folders keep their digests and cards, the 3 newest their full logs; the rest are
    pruned;
  - `_tidy` keeps `history/`.
- **The prepare cache.** The `.prepared` stamp keeps its name, since renaming it would re-integrate
  every Sherpa point. It gains `seconds`, the card's sha256, and the record and point that filled it.
  The digest is copied into the entry as `prepare.log`, and a cache hit names it in its attempt.
- **Settings:** `[run] log = { head = 100, tail = 200, digests = 9, full = 3, worker_every = 600 }` in
  hep.toml or machine.toml (`paths.WORK_KEYS`, read like `paths.keep`), the defaults as constants.
- **Wording:** the "safe to delete" comment (`tools.py:617`) and 06 §14 say that `cards/`,
  `commands.sh` and `context.toml` are the record's.

**Tests:**
- the digest of a 10k-line transcript;
- 12 attempts leave 9 digests and 3 full logs;
- an old record's first rotation;
- an old-shape `.prepared` is still a hit.

**Gates:** F, S, the identity guard, B.

## L4 — The run's own log

- **`run.jsonl`** (`events.RunLog`): an always-on subscriber writing `records/<run>/run.jsonl`,
  appended: every event but `line`, and `progress` at most once per tool a minute. `cli.run_one`
  subscribes it beside the Journal (`cli.py:1076`). The Journal now appends instead of rewriting
  (`events.py:127`).
- **`heimdall log RECORD[/POINT[/TAG]] [--full] [--attempt N]`:**
  - a record prints its `run.jsonl` through the plain view (the run's text, as the registry log had it);
  - a point prints its attempts and digests;
  - a tool prints that file.

  `heimdall watch --file` takes `run.jsonl` too.
- **The worker's plain view** gives a progress line every `worker_every` seconds (`cli.py:887`, `:1070`).
  The registry entry gains its counts: done, failed, with warnings (`runs.Recorder`).

**Tests:** `RunLog`'s sampling (`test_status.py`); the counts (`test_runs.py`, `test_detach.py`);
`heimdall log` on a fixture record.

**Gates:** F, S, the identity guard, B.

## L5 — New kinds in `filters.toml`

- **`status._rule`** gains four kinds:
  - `reason`: the failure's quoted reason, which the point's message names;
  - `fact`: kept in the attempt, at most 20;
  - `stat`: rows of a counts table, into `{msg: count}`;
  - `integration`: σ ± err during a prepare step, as an `xsec` message plus the phase.

  A folder's `filters.toml` applies to a tool's output whatever its `status` (`tools.py:968`, today
  only `filters`).
- **Sherpa:**
  - `reason` for L1's reason lines; `fact` for `Hard process:` and `Building processes`; `stat` for
    "exceeded frequency limit"; `integration` for the integration lines;
  - `prepare.py`'s `REASONS` (`:27`) is removed, and its exit-3 message points at the reason above
    (`test_sherpa_prepare.py` follows).
- **Pythia:**
  - a new `framework/tools/pythia/filters.toml`: `stat` for the error-statistics rows, `fact` for the
    process table;
  - **`[diagnose]` in its `tool.toml`:** after exit 3 (Kit's `Init`), the runner runs the tool once
    more with an extra card (`Print:quiet = off`, `Main:numberOfEvents = 0`) into a scratch output. It
    keeps that run's digest as `<tag>.diagnose.log` and quotes its `PYTHIA Error`/`Abort` lines in the
    failure.
  - App_Pythia is not rebuilt, so identities are untouched.

**Tests:**
- transcripts: Sherpa's runs 02, 05, 09 and 11, Pythia's 02 statistics;
- a fake tool with a `[diagnose]`;
- `test_app_pythia.py` (slow): a direct-only card's real init failure, "all processes have vanishing
  cross sections".

**Gates:** F, S, the identity guard.

## L6 — The plot stage

- A failed Paint batch, converter or merge (`plot.py:327`, `:370`, `:1462-1481`): its clean output's
  digest goes to `records/<run>/logs/plot/<set>.<backend>.log` (a converter's or merge's,
  `convert-<point>.log`), and the `say` line names the file. `say` lines reach `run.jsonl`.

**Tests:** `test_plot_stage.py` with a failing fake Paint.

**Gates:** F, S.

## Verification (the end)

- **A scratch work dir** (the tests' fixture), with a failing, a stalling and a warning tool:
  - `heimdall status` shows the causes;
  - `heimdall log` prints the run and each point;
  - after 12 reruns, `history/` holds 9 digests and 3 full logs;
  - `grep -rlP '[\x00-\x08\x0b-\x1f\x7f]|\x1b'` over the record finds nothing;
  - the registry entry has its counts.
- **Brookhaven, read-only:** `heimdall status eic/zeus` gives the same counts as before L1, and the
  identity guard matches.
- I-106 is deleted from `.plans/ISSUES.md`; V195 onward are in `docs/07_Record.md`; the execution map
  is final.
