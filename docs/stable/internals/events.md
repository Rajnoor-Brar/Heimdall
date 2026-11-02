---
id: events
summary: how a tool's status reaches the views: pipes, filter rules, digests, the event stream and its listeners, the views
code: framework/runner/status.py, framework/runner/events.py, framework/runner/watch.py
---

# Status, events and views

## From tool to runner

| Tool | Channel | Read by |
|---|---|---|
| `status = "standard"`: our apps, module programs, `heimdallkit` tools | JSON lines on `$HEIMDALL_STATUS_FD` | `status.Reader`, a pipe per process |
| `status = "filters"`: every other tool | stdout and stderr | the same reader, each line matched against `filters.toml` |
| any tool with a `filters.toml` | stdout and stderr too | the same rules (Pythia's error statistics beside its protocol) |
| `status = "none"` | stdout and stderr | the last line only |

- **stdout is never the status channel:** it may carry HepMC, and always carries chatter.
- **One reader thread per tool** reads both pipes, so a tool that prints fast never waits on a full pipe.
- **A filter rule never fails a run.** The exit code does.
- **Clean text:** every line is cleaned before it is matched, shown or written (`status.clean`): escape sequences, then control characters but tabs. A line a bare carriage return rewrote is saved only at its last state.

## `filters.toml`

For a tool that only prints. Each line is matched against the rules in order, and the first match wins. A folder's rules, or a user's via `filters = "<file>"`.

```toml
[[rule]]
match = '^Event (?P<done>\d+) \('     # a Python regex
emit  = "progress"

[[rule]]
match = '^Reading events from'
emit  = "phase"
phase = "analysing"                   # a fixed name; else the (?P<phase>…) group, else the match
```

| `emit` | Needs | Makes |
|---|---|---|
| `progress` | `(?P<done>…)`; optionally `total`, `elapsed`, `xsec`, `xsec_err` | a progress message; a line with no total takes the events the tool makes or reads |
| `xsec` | `(?P<xsec>…)`, optionally `xsec_err`, in pb | a σ message |
| `phase` | `phase = "…"`, or a `phase` group | a phase message |
| `warn`, `error` | | a log message with the line |
| `ignore` | | nothing, and stops the lines below from matching |
| `reason` | optionally `level` | what a failure is put down to: the last 5 kept, and a failed tool's message quotes the last |
| `fact` | optionally `xsec`, `xsec_err` | the line, kept with the attempt (the first 20) |
| `stat` | `(?P<count>…)`, optionally `what`, `level` | a row of a counts table kept with the attempt: Pythia's error statistics |
| `integration` | `(?P<xsec>…)`, optionally `xsec_err`, `phase` | a prepare step's σ as it integrates |

Any rule may also name a `phase`. A rule matches anywhere in a line unless it anchors itself with `^`: Sherpa says what matters mid-line, so its folder lists its own errors and its warnings that say "Error" before its general rules. Lines split on `\n` and `\r`, so a counter rewritten in place is read. A rule that stops matching costs a progress bar, not a result.

## What is kept

**Runtime state stays off disk**, but for the [run registry](live-runs.md).

- **A digest of a tool's output** (`Reader.write_digest`): in memory its first 100 lines, last 200, and every line a rule matched (at most 500), written to `records/…/logs/<point>/<tag>.log` however it ended. `--logs` also writes `<tag>.full.log` as it comes. A prepare step's are `<tag>.prepare.log`, `[prelim]`'s `prelim.log`.
- **History:** an attempt's start moves the last attempt's logs and cards to `logs/<point>/history/<n>/`. `[run] log`'s `digests` newest (9) keep digests and cards, its `full` newest (3) whole logs.

## The event stream

`events.py`. The executor, stages and CLI emit versioned events onto one bus: `run`; `point` (started, done, failed, stopped, skipped); `tool`, `exit`; a tool's `phase`, `progress`, `xsec`, `log`, its latest `line`; `note`, `say`. Listeners:

- **The view.**
- **The watch socket:** abstract Unix socket `@heimdall-watch-<pid>`, found in `/proc/net/unix`; where there are none (macOS), a file `<tmp>/heimdall-watch/heimdall-watch-<pid>`. A greeting, the current run's events so far, then live. Only the same uid may connect (`SO_PEERCRED`; a 0700 folder on macOS). When the process ends each watcher gets what it has not been sent (for at most 2 s), so the verdict is never lost. A watcher 10,000 events behind gets `dropped` and the end of its stream. A name taken by another PID namespace gets a suffix.
- **The journal**, `records/…/<R>/status.jsonl`, only with `--journal`.
- **The run log**, `records/…/<R>/run.jsonl`, always: every event but `line`, and `progress` at most once a minute. A failed write is passed over. `heimdall log` prints it through the plain view.
- **The registry's counts and progress:** `runs.Recorder`, at most every 2 s.

## The views

One reducer (`watch.State`) and a renderer on its own thread, the same in the run, in `heimdall watch` and over a journal.

- **Live view** (`rich`, on a terminal): each running point below finished blocks, a line per tool with phase, progress, rate and ETA. A tool's last warning or error sits under its row (`↳ …`).
- **Plain view** (`--plain`, or no terminal): progress every few seconds.
- **A view never blocks the run.** All printing goes through one thread, so a terminal that stops reading stops the display, not the supervision (V32).

Both print one block per finished point: a heading saying when it ended, then its results path; a failed block names the tool, its exit and the message.
