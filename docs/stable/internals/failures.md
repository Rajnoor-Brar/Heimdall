---
id: failures
summary: how a chain of processes fails and how each way is handled; attribution; exit codes
code: framework/runner/execute.py, src/Kit.hh, framework/heimdallkit.py
---

# Failures and exit codes

A FIFO chain fails in two ways a single process does not. Both are handled by construction.

**Deadlock at open** ([L8](connections.md)):

- Each tool runs in its own process group. The first nonzero exit is a failure; after 2 s the rest get SIGTERM, after 5 s more SIGKILL.
- A tool silent for `stall_after` seconds (no line, status message or heartbeat) fails as stalled; one past `timeout` as timed out.
- FIFOs are fresh per point, per attempt.

**A partial result that looks complete.** If the generator dies mid-stream, Rivet sees end of file, finalises and exits 0 with a plausible YODA. So every event producer writes a **sidecar** (written, σ, seeds), and every consumer's count is **checked** against it (Rivet: `/RAW/_EVTCOUNT`; a module: its report; Delphes: its tree). A mismatch fails the point with the product still `*.partial.*` and no `.complete`.

**Attribution.** When several processes die together, the cause is the first to exit nonzero before the runner sent a signal. A SIGPIPE death is never the cause: its reader went away first.

Stop and pause signals: [live-runs](live-runs.md).

## Exit codes of our apps

One table, `Kit::Exit` in `src/Kit.hh`, and `heimdallkit.Exit`:

| Code | Meaning |
|---|---|
| 0 | ok |
| 1 | config or card |
| 2 | usage |
| 3 | init |
| 4 | input |
| 5 | output |
| 6 | stopped, partials written |
| 70 | internal |

## Exit codes of `heimdall run`

| Code | Meaning |
|---|---|
| 0 | every point done or skipped |
| 1 | a point, stage or page failed |
| 2 | a config error before anything ran |
| 6 | stopped or paused |

`heimdall check` exits 2 when any config is not well.
