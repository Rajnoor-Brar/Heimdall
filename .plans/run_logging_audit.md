# Audit: run logging (2026-10-25)

What a `heimdall run` records and shows: what a tool prints, how the runner reads and keeps it, and
where it ends up (the view, the record, the run registry). Checked against the code at `64a472e` (was `0577eca`) and
against Brookhaven's `eic/zeus_validation` runs 01–11, whose Sherpa failures (the debug of the same
day) are the worked example throughout. Nothing is built yet.

Out of scope: the stack build's logs (`forge/logs/`, used once below as the model to follow) and
the editor tooling.

---

## 1. What exists

### 1.1 The channels

| # | Source | Read by | Kept where | For how long | Default |
| --- | --- | --- | --- | --- | --- |
| 1 | A tool's stdout and stderr (one pipe) | `status.Reader`, one thread per tool | the last 200 lines in memory (`status.py:28`); `records/<run>/logs/<point>/<tag>.log` | that run's record | **written only when the tool fails** (`execute.py:485-487`, the tail overwritten) |
| 1b | the same, with the `logs` keep word | the same | `<tag>.log`, every byte as it came (`status.py:91`, `:141`), **appended** | that run's record | opt-in (`--logs`) |
| 2 | The status pipe `$HEP_STATUS_FD` (`src/Status.hh`): `phase`, `progress`, `xsec`, `log`, `summary`, `heartbeat` | the same reader | **nowhere**: onto the event bus only | the process | always (apps, modules, hepkit) |
| 3 | `filters.toml` rules over channel 1: `progress`, `xsec`, `phase`, `warn`, `error`, `ignore` | the reader | the bus; a `ToolState` in memory | the process | per tool folder |
| 4 | Prepare steps (Sherpa's integration, Herwig's read) | the reader | `<tag>.prepare.log` in the point that filled the cache entry; the entry's `.prepared` (`{argv, finished}`, `execute.py:617`) | the record; the cache | as channel 1 |
| 5 | `[prelim]` commands | `subprocess.run`, captured | `prelim.log`, appended (`execute.py:341-343`) | the record | on failure, or with `logs` |
| 6 | The event bus (`events.py`): `run`, `point`, `tool`, `exit`, `phase`, `progress`, `xsec`, `log`, `line`, `note`, `say` | the view; the Hub socket; the Journal; the registry's `Recorder` | the Journal: `records/<run>/status.jsonl`, **rewritten** per run (`events.py:127`) | the record | the Journal is opt-in (`--journal`) |
| 7 | The view (`watch.py`): live (rich) or plain | the terminal; a worker's stdout | a detached worker's stdout is the registry log `~/Himinbjorg/runs/<id>.log`, **appended** (`runs.py:273`), a progress line a minute (`cli.py:1070`) | **30 days** (`runs.py:40`), outside the work dir | always for a terminal run, which is a worker (V183) |
| 8 | The registry entry `runs/<id>.json` | `heimdall runs`, `watch`, `stop` | who, where, when, exit code, verdict, record folders | 30 days | always |
| 9 | The record (`record.py`): `provenance.json`, `identity.json`, `.complete`, `points.json`, `config/` snapshot, `commands.sh`, `context.toml`, `cards/` | `--why`, `status`, plot, post | `records/<run>/` | for ever | **provenance only for a point that succeeded** (`execute.py:565-567`) |
| 10 | The plot stage: Paint, the converters, the merge | `subprocess.run`, captured | the last stderr line, at most 300 characters, in a `say` (`plot.py:327-329`, `:370-372`, `:1462-1481`) | the view | always |
| 11 | Cluster jobs | Slurm `--output` | `records/<run>/cluster/…/logs/{pre,points,finish}-<id>.log`, named by `heimdall cluster --status` when a job failed | the record | always |

### 1.2 The configuration surface

| Knob | Where | What it scopes |
| --- | --- | --- |
| `keep = ["logs", "journal", "work", "cache"]` (`paths.py:85`) | `--keep`, `--logs`, `--journal`, `[heimdall] keep`, hep.toml and machine.toml `[run] keep`, unioned (`paths.py:141`) | channels 1b, 5 and 6's Journal; the scratch files |
| `--plain` | global and per command | channel 7's renderer |
| `stall_after`, `timeout` | `[tools.<tag>]`; default 300 s (`tools.py:971`), a prepare step at least 3600 s (`execute.py:610`) | when silence fails a tool |
| `status = standard \| filters \| none` | each `tool.toml` | which channel a tool's status comes from |
| `filters.toml` | each tool folder (`delphes`, `herwig`, `madgraph`, `rivet`, `sherpa`, `whizard`) | channel 3 |
| Constants: `TAIL = 200`, `LINE_EVERY = 0.5` s, the worker's 60 s, `KEEP_DAYS = 30` | code | not configurable |
| The tools' own verbosity: `Print:quiet = on` (App_Pythia, `src/App_Pythia.cc:194`), Sherpa's `BATCH_MODE`/`EVENT_DISPLAY_INTERVAL` (`[command] display`), Rivet's line per 100 events | the apps, tool folders | what channel 1 carries at all |

### 1.3 What already works, and should stay

- One reader thread per tool, so a fast printer never blocks on a full pipe (V72). The status
  protocol never blocks a generator: non-blocking, drop and count, heartbeat (`Status.hh`).
- **A view never blocks the run** (V32). One reducer (`watch.State`) serves the run, `heimdall watch`
  and a journal replay alike.
- A filter rule never fails a run; the exit code does.
- The supervision: the first real failure is blamed and a SIGPIPE death never is (`execute.py:439-446`);
  a count check against the producer's sidecar; `.partial` names until every check has passed.
- The record's reproduction data: `commands.sh` (V187), `context.toml`, the cards, the identity parts,
  the git state of both repos, `exe_sha256`, package states.
- The registry's ownership rules (V191).
- The stack build's logs rotate, `<name>.log` → `.log.1`, … (`recipes/build_stack.py:1747-1756`), and
  a failure prints an excerpt plus the log's path. This is the model for section 4.

---

## 2. What it costs (measured on Brookhaven)

| Log | Size | Of which progress lines |
| --- | --- | --- |
| `02_generator_pdf/logs/` (38 points, 1M events, `--logs`) | 16 MB | — |
| `rivet.log` of a 1M-event point | 310 KB, 10,026 lines | **99.7 %** (`Event N (…)`, one per 100 events) |
| `sherpa.log` of a 1M-event point | 137 KB, 1,208 lines | 83 % |
| `pythia.log` of a 1M-event point | 7 KB, 73 lines | 0 (`Print:quiet`). It still holds Pythia's error-statistics table (51,243,763 `BeamRemnants::setKinematics` errors, 486,209 aborts), which nothing reads |
| A registry worker log (`20261024-071215-…-8f77.log`) | 341 KB, 2,951 lines | **91 %** (2,692 progress lines) |
| Terminal control sequences in saved logs | **169 of 690** logs (every one a `sherpa.log` or `sherpa.prepare.log`), 177 KB of `ESC[0m`, `ESC[31m`…`ESC[36m`, `ESC[1m`, `ESC[?25h` | — |

So `--logs` keeps almost nothing but counters, while the default keeps nothing of a tool that
succeeded.

---

## 3. Findings

Ordered by how much they cost a diagnosis. **Evidence** cites the 2026-10-25 runs.

### A. Lost when the run ends (critical)

**A1. A failure's cause is not in the record.**
- `_finished` only emits it (`execute.py:655`). `provenance.json` is written only on success
  (`:565-567`). `points.json` has `complete: true|false` (`record.py:449`). `heimdall status` can say
  only "incomplete (begun, not done: failed or stopped)" (`house.py:426`).
- The cause, the blamed tool and the message exist only in the registry log (text, 30 days, in the
  machine root), or in the Journal if `--journal` was given.
- *Evidence:* run 09's eight "sherpa:prepare was silent for 5200 s" are in
  `~/Himinbjorg/runs/20261025-202855-….log` and nowhere in Brookhaven.

**A2. A successful point's warnings vanish.**
- `ToolState.warning` holds the last warning only, and is shown only live, under the running tool.
- An `ok` block is its notes plus "done →" (`watch.py:156`). A failed block adds `(tool.error)`
  (`:180`). No warning reaches the record, the block or the verdict.
- *Evidence:* runs 05 and 07 reported "ok" while Sherpa had dropped half the card's processes.

**A3. The tools' own numbers are thrown away.**
- `summary` is sent by App_Pythia (`written`/`attempted`/`accepted`, `App_Pythia.cc:349`), by a module
  (`events`, `sum_w`, `Module.hh:371`) and by yd2rt (`written`, `skipped`, `App_yd2rt.cc:302`, `:336`).
  `status.apply` ignores it (`status.py:224`).
- The final cross section (`xsec`) lives in `ToolState` only.
- Neither reaches `provenance.json`.

**A4. The generators' error statistics are never read.** Pythia's "Error and Warning Messages
Statistics" table and Sherpa's "Error messages from 'X' exceeded frequency limit" are kept only with
`--logs`, and nothing parses them. A run with 51M remnant errors per 1M events looks the same as a
clean one.

**A5. The status pipe is never on disk** without `--journal`, so an app's own `log` messages are gone
when the run ends. One example is App_Pythia's "Pythia initialisation failed (see the log)", whose
"log" has nothing in it (B6).

### B. Misread or unseen (critical for diagnosis)

**B1. Sherpa's filters only recognise an error at the start of a line**: `^(?:Error|ERROR)\b`
(`tools/sherpa/filters.toml:30`). Sherpa says what matters mid-line:
- `Matrix_Element_Handler::BuildSingleProcessList(): Error in initialising ISR … Ignoring process.`
  (runs 05, 07, 09);
- `Process_Group::Differential(): Cross section is 'nan'.` (07);
- ``Could not find a definition for `$(LOOPGEN)'. This is an input error`` (run 11: the actual reason
  for exit 1);
- `Missing input thrown`, `No hard process found`.

**B2. Two places know Sherpa's error phrases**: `prepare.py`'s `REASONS` (`prepare.py:27`) and
`filters.toml`. They disagree; neither has the full list.

**B3. Structural facts printed at initialisation are not kept.** The line that diagnosed runs 05–09
was `Hard process: e+ (Intact) + P (Photon)`. Others like it: Sherpa's "Building processes (…, 2
process blocks)" and Pythia's process table. They are at the head of a log, which the default never
keeps: it keeps the failure's tail.

**B4. A stall says nothing about what stalled.** The message "was silent for 5200 s" (`execute.py:451`)
leaves out the phase, the last line and the time it went quiet. In run 09 those were "integrating",
`Starting the calculation at 20:29:41`, 87 minutes earlier.

**B5. The integration's progress isn't parsed.** Sherpa's lines like `38551.4 pb +- ( 2957.3 pb = 7.67 % )
5000 ( 10007 -> 49.9 % )` give σ, its error and the points so far. With no rule for them, an hour-long
hang looks like a long "integrating".

**B6. App_Pythia silences Pythia before reading the cards** (`App_Pythia.cc:194`). On a failed init
(`:220`) the reason is never printed: "all processes have vanishing cross sections" only appeared
from a plain-Pythia check outside Heimdall.

**B7. "count ok" doesn't mean the analysis kept anything.** The count check reads `/RAW/_EVTCOUNT`,
the events Rivet saw, not the histograms' entries. Runs 04, 05 and 08 passed with every ZEUS
histogram empty.

### C. Lifecycle and organisation

**C1. Each file follows its own write rule:**
- `--logs` appends (`status.py:91`);
- a failure's tail overwrites (`keep_tail`);
- the Journal rewrites (`events.py:127`);
- `prelim.log` and the worker log append (`execute.py:343`, `runs.py:273`).

A record's attempts can't be told apart. Run 06's `sherpa.prepare.log` holds three Sherpa starts
with different cards (19:34, 19:36, 19:48), with nothing between them.

**C2. Verbosity is all or nothing.** By default only a failed tool's tail is kept; `logs` keeps every
byte, 99 % of it counters. A diagnosis needs the head (beams, processes, PDFs), the tail, and every
warning or error line in between.

**C3. `logs/` is called "safe to delete" (`tools.py:617`), but it holds part of the durable record:**
`commands.sh`, `context.toml` and `cards/`, which `provenance.json` points at (its `card` key names
`logs/<point>/cards/<tag>.yaml`).

**C4. A run leaves no run-level account in its work dir.** Its notes ("parallelism 19 × ~2 cores…"),
warnings (`meta_notes`, `cli.py:1091`), verdict and plot-stage lines are only in the registry log
(30 days, machine root) or the opt-in Journal.

**C5. A run has two logs, and neither is complete.** The registry log is the plain view's text, 91 %
progress. The structured events exist only with `--journal`, and a rerun into the same record
rewrites that file.

**C6. A prepare cache entry has no account of its own.** The integration's log lives in the point
that happened to fill the entry; every other point says "cached". The entry keeps `{argv, finished}`
and nothing more: no σ per process, no time taken, no card hash, no link to that log.

**C7. The plot stage keeps one line.** A failed Paint batch, converter or merge is reduced to its last
stderr line, and no log file is written.

**C8. Timestamps don't line up.**
- Tool logs carry none, so you can't see from a log when a tool went quiet.
- Blocks give local time to the minute; events use epoch seconds; provenance uses UTC ISO.

**C9. Saved logs carry terminal control sequences.**
- The full write copies bytes "as they came" (`status.py:31`, `:141`). The in-memory tail and the
  bus are cleaned (`status.py:153`), but the file isn't.
- That is 169 of the 690 saved logs, every one of them Sherpa's: colours and cursor commands, 177 KB.
- No bare `\r` counters were found today (Sherpa runs with `BATCH_MODE 23`), but nothing would
  collapse them if a tool printed them.

### D. Display

**D1. The live view swallows square brackets.** It prints through rich with markup on
(`watch.py:374`), and `say` and error lines aren't escaped, so `where: [quantities.pdf] = NNPDF23lo`
showed as `where:  = NNPDF23lo` on the terminal. The registry log has it whole.

**D2. `--plan --card` misattributes rendered cards.** For a render-style card such as Sherpa's, every
line says "← the base card" (`tools.card_view`, `tools.py:1593`), including the quantity's PDF and
the plan's `EVENTS`, `BEAMS` and `RANDOM_SEED`.

**D3. Only the last warning is shown**, overwritten by the next one, even live.

### E. The configuration surface

**E1.** Five spellings of "keep" (already I-70).

**E2.** The tail length, the worker's progress cadence, the registry's age and the line rate are
constants.

**E3.** What a tool prints is decided in three places: the app's source (App_Pythia), the tool folder
(Sherpa's `display`), and nowhere at all (Rivet's line per 100 events).

---

## 4. Proposal

### 4.1 Principles

1. **Tiers by criticality, each with its default:**

   | Tier | What | Default | Form |
   | --- | --- | --- | --- |
   | T0 verdict | exit codes, blamed tool, cause, message, stall context, durations | always | structured |
   | T1 signals | warnings and errors (deduplicated, with counts and first line number), facts (B3), the tools' numbers (A3), error statistics (A4), sanity checks (B7) | always | structured |
   | T2 digest | per tool and attempt: the head, the tail, every matched line, and "… N lines (M progress) …" in place of the rest | always (a few KB a tool) | clean text |
   | T3 full | every line a tool printed | `keep logs` | clean text |
   | T4 live | progress, latest lines | never on disk; `keep journal` writes them | events |

2. **One place per scope:** a tool's attempt, a point, a run, a cache entry, the machine. Records are
   data; views are renderings of them.
3. **Every saved text is clean** (C9, the user's ask): escape sequences (CSI and OSC) removed, a
   `\r`-rewritten line kept at its final state, other control characters dropped (tab kept), invalid
   UTF-8 replaced, one `\n` per line. The same cleaner (`status.ANSI`, extended) serves the bus, the
   tail, the digest and the full log. Raw bytes are never kept.
4. **What Heimdall knows about a tool stays in its folder** (CLAUDE.md): every phrase it matches is in
   `filters.toml`. Nothing like `prepare.py`'s `REASONS` lives beside it.
5. **A warning never fails a run** (the existing rule), but it is never silent: it reaches the block,
   the verdict and the record.

### 4.2 The layout

```
records/<run>/
  run.jsonl                      NEW, always: the run's events except progress and line (progress at most one per
                                 tool a minute): run, point, tool, exit, phase, log, xsec (final), summary,
                                 fact, note, say, plot; appended, an `attempt` marker per run start
  status.jsonl                   keep journal: the whole stream, as today (appended, not rewritten)
  points.json                    + state (complete | failed | stopped | stale | to run), cause, attempts
  points/<point>/
    provenance.json              + tools[].reported (summary, final σ ± err), tools[].warnings (digest),
                                   facts
    attempts.jsonl               NEW, always: one object per attempt, success or not (fields below)
    identity.json, .complete     as today
  logs/<point>/                  the working folder, as today (cards/, commands.sh, context.toml: see C3)
    <tag>.log                    NEW meaning: the digest (T2) of this attempt, always
    <tag>.log.1                  the previous attempt's (one generation; build_stack's scheme)
    <tag>.full.log               keep logs: the whole clean output (T3), rotated the same way
    <tag>.prepare.log            the same three rules
  logs/plot/<set>.<backend>.log  NEW: a failed batch's digest (C7)
.cache/<P>/<tool>/<hash>/
  prepared.json                  replaces .prepared: argv, card sha, seconds, σ per process ± err (B5), the
                                 point and record that filled it, its log's digest copied in
~/Himinbjorg/runs/<id>.{json,log} the entry + warning and failure counts; the log a worker's stdout for crash
                                 output (tracebacks), its progress at most every 10 minutes
```

**An attempt (one line of `attempts.jsonl`):**
- `n`, `started`, `finished`, `identity`, the cards' sha256s, `verdict` (ok | failed | stopped), `cause`,
  `blamed`, `message`;
- `tools`: for each, `tag`, `exit`, `seconds`, `cause`, `stall` (`phase`, `last_line`, `silent_since`),
  `warnings` (count, distinct, the first five), `errors`, `reported`, `stats` (A4), `facts` (B3);
- the paths of its digests.

`heimdall status` reads its last line. `heimdall show` reads them all.

**C3:** `commands.sh`, `context.toml` and `cards/` move to `records/<run>/points/<point>/`, beside the
provenance that names them. `logs/<point>/` then holds only what is safe to delete.

### 4.3 Tool folders: what a rule can say

`filters.toml` keeps its rules and gains kinds and options:

| Kind or option | What it records | First uses |
| --- | --- | --- |
| `reason` | the line to quote when the tool fails (replaces `prepare.py`'s `REASONS`) | Sherpa: `Could not find a definition for`, `No hard process found`, `Missing input thrown`, `Wrong ordering of initial-state particles` |
| `fact` | a line kept as a fact of the attempt (T1) | Sherpa: `Hard process:`, `Building processes`; Pythia: the process table, via the app's output |
| `stat` | a counts table, parsed into `{message: count}` | Pythia's error statistics; Sherpa's "exceeded frequency limit" |
| `integration` | a prepare step's progress: σ, error %, points | Sherpa's integration lines (B5) |
| `escalate = "warn" \| "error"` | a rule's level, whatever the line starts with | Sherpa: `Error in initialising ISR … Ignoring process` (warn), `Cross section is 'nan'` (error) |
| `[checks]` sanity (tool.toml) | a warning computed after the tool | Rivet: no histogram filled (the `/RAW` entries, B7); yd2rt: `skipped > 0` |

A rule matches anywhere in a line unless it anchors itself.

### 4.4 What the user sees

- **A block** names its warnings, for example `warnings: 3 (sherpa 2, rivet 1): Error in initialising ISR …
  Ignoring process (×2)`, and its facts on request.
- **The verdict** says `16 done (5 with warnings), 0 failed`, followed by a table of the failed
  points with their causes.
- **A stall** says `sherpa:prepare silent for 5200 s since 20:29 (integrating; last line: "Starting the
  calculation at 20:29:41")`.
- The live view escapes what it prints (D1). `--plan --card` names each line's source: the base card,
  `[quantities.pdf] = MSTW08lo`, the plan (D2).
- **New commands:**
  - `heimdall show RECORD[/POINT]` (I-72), from attempts, provenance, facts and digests;
  - `heimdall log RECORD/POINT[/TAG] [--full] [--attempt N]`, which prints the right file;
  - `heimdall status` gains a cause column; `heimdall runs` shows warning and failure counts;
  - `--json` (I-37), from the same files.
- **App_Pythia's init failure** (B6) has two fixes:
  - (a) print Pythia's messages when `init()` fails. That needs App_Pythia rebuilt, which changes
    every Pythia point's identity: ask first.
  - (b) no rebuild: on an init failure, the runner reruns the init alone through I-100's preflight
    with messages on, and records what it says. (b) is the recommendation.

### 4.5 Configuration

- `keep logs` now means the full text (T3). The digest is always written.
- `keep journal` means the full event stream. `run.jsonl` is always written.
- One optional table, `[run.log]` in hep.toml or machine.toml: `head` (100), `tail` (200),
  `attempts` (1), `progress_every` (60 s), `worker_every` (600 s). It replaces the constants (E2).
- I-70's single `--keep` flag still applies.

---

## 5. Decisions for you

| # | Question | Recommendation |
| --- | --- | --- |
| L-D1 | Your rule "runtime state stays off disk" (2026-10-03; the registry, 2026-10-23, was its exception) would gain `run.jsonl`, `attempts.jsonl` and the digests, written by default. Live progress stays off disk. | **Allow T0–T2 by default**: they are what a failed or suspicious run needs afterwards, and they are small |
| L-D2 | `<tag>.log` becomes the digest, always; the whole output goes to `<tag>.full.log` with `keep logs` | yes |
| L-D3 | Attempts kept per tool log | 1 previous (`.log.1`); `attempts.jsonl` keeps them all |
| L-D4 | The registry worker log: thinned to crash output and sparse progress, its run text rendered from `run.jsonl` | yes |
| L-D5 | Warnings in the exit code | never (a filter rule never fails a run); `--strict` only if you ask for it |
| L-D6 | Raw bytes (escape sequences) kept anywhere | never: every saved text is cleaned |
| L-D7 | `commands.sh`, `context.toml`, `cards/` move from `logs/<point>/` to `points/<point>/` (C3) | yes, with I-28's record-format bump |

---

## 6. Plan sketch (to become phases on your word)

| Step | Content | Fits the approved plan at | Size |
| --- | --- | --- | --- |
| **L1** quick fixes, no format change | the cleaner on every saved text (C9); Sherpa's missing rules (B1); an attempt header line in appended logs (C1 interim); markup escaped (D1); the stall context (B4); `--card` origins (D2); Rivet's empty-analysis warning (B7) | any time; before Phase 2 is cheapest | S |
| **L2** attempts and causes | `attempts.jsonl`; `points.json` state and cause; `heimdall status`'s cause; warnings in blocks and the verdict; `summary` and final σ into provenance (A1–A3, A5, D3) | Phase 4 (record formats, I-28) | M |
| **L3** digests and rotation | `<tag>.log` digest, `.full.log`, `.log.1`; the prepare cache's `prepared.json` (C2, C6); the C3 move | Phase 4 | M |
| **L4** the run's account | `run.jsonl` always; the Journal appended; the worker log thinned; `watch --file` and `show`/`log` on it (C4, C5; I-72, I-37) | Phase 5 (session layer, CLI) | M |
| **L5** tool-folder kinds | `reason`, `fact`, `stat`, `integration`, `escalate`, `[checks]`; `prepare.py`'s `REASONS` removed; Pythia's statistics and init reason via preflight (A4, B2, B3, B5, B6; I-100) | Phase 5 or 8 | M |
| **L6** the plot stage | `plot` events into `run.jsonl`; a failed batch's digest (C7) | Phase 6 (plot model) | S |

**Tests (each step adds its own):**
- A Sherpa transcript fixture, from run 11's log and run 07's, gives the expected reasons, warnings and
  facts.
- The digest of a 10k-line log keeps its head, tail and matched lines.
- An attempt survives a rerun into the same record.
- A stalled fake tool's attempt names its phase and last line.
- No saved file holds a byte in `\x00-\x08\x0b-\x1f\x7f` or `ESC`.
- `heimdall status` shows the cause of a failed fixture point.
- The size of `run.jsonl` stays within a budget for a 38-point fixture sweep.

**Related issues:** I-28 (record formats), I-35 (session layer), I-37 (`--json`), I-70 (one keep flag),
I-72 (`heimdall show`), I-100 (preflight), I-102 (an index over provenance: `attempts.jsonl` feeds it).
