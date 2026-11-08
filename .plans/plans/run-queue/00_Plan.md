# Run queues: a run queued to another, sweeps as chains

Issue: none yet (asked by the developer 2026-11-08). Status: approved by the developer's answers 2026-11-08; in progress.

## Context

Verified at `888a021`:

- **Registry:** `runs/<id>.json`, one writer, the run (`runs.begin`, `update`, `finish`). `runs.state` reads an entry: a verdict once `finished`, else running/lost from its pid. `house.live_entries` lists the going and the paused, oldest first; `[N]` is the place there.
- **A detached run** is a worker (`runs.spawn`: the command again with `--worker <id>`, its own session, its log `runs/<id>.log`). `background` starts it, and follows it (`attach`) or leaves it (`--detach`).
- **A sweep** (`[errand].sweep_runs`) runs its configurations in one process: `_runs` plans all, then `_pipelined` (V75, B8: the next starts once the one before has started all its points, one core budget shared) or, with no bus, one after another.
- **Control:** `runs/<id>.control.json` and SIGUSR2 (`--jobs`). `runs.again` strips `--worker`/`--detach` from argv.

## Design (the developer's answers, 2026-11-08)

- **Entry fields:** `queued_to` (the predecessor's id), `queue` (the queue's id: its first run's), `queued` (true while it waits), `began` (when it left the queue). A queued run is a worker that waits before planning.
- **States:** `queued` (blue) while it waits; `held` when its predecessor was stopped. Both are live: in the list with `[N]`.
- **Waiting** (`cli.wait_turn`, polled every `runs.QUEUE_POLL` s): the predecessor done, failed, not run or lost → start; stopped → held until dispatched; paused → wait, and a resume (`resumed_by`) is followed to the new run; forgotten in the queue (`left_queue`) → relink to its own `queued_to`. The waiter takes its predecessor's `queue`, so a split propagates down. It says each step in its log and `run.jsonl` (queued, held, relinked, dispatched, starting).
- **Dispatch:** `heimdall runs --dispatch ID|N`, and `d` at `runs -i` (the word `dispatch`): the control file says `dispatch`; the run starts now, its `queued_to` kept as `dispatched_from`, and it heads a queue of its own (`queue` = its id); the runs after it follow it (C keeps B).
- **Forget:** `runs --forget N` on a queued or held run: it leaves the queue (verdict `forgotten`, never run); the one after it relinks to its predecessor.
- **`heimdall run … --queued-to ID|N`:** detached; checked now (a config error refuses), planned at its turn. Refused for an ended (not paused) predecessor, a cluster one, `--plan`/`--why`/`--show-config`.
- **Sweeps:** a sweep with a bus becomes a chain: one worker a configuration (`--worker`, a hidden `--sweep-member KEY`), the first running, the next queued to it, and so on. Attached, the terminal follows the chain run after run. Without a terminal (no worker) the sweep runs its configurations one after another in the process, as the unpipelined branch does. `_pipelined` and the shared budget retire (V75 superseded).
- **Queue progress:** `heimdall runs` shows a queue line: `queue <qid tail> · 2 of 5 · next [N]`; the run's log says it at its start and end.

## Phases

Test command, stack loaded: `taskset -c 0-5 nice -n 10 python -m pytest -q <files>`.

| # | Phase | Verified when | Blocked by | Size |
|---|---|---|---|---|
| 1 | Registry and listing | test_queue: states queued/held from entries; the chain's order and places; the listing's queue lines | none | S |
| 2 | Waiting worker, `--queued-to` | test_queue: a queued worker starts when a fake predecessor's entry ends done/failed, holds on stopped, follows a resume and a forget | 1 | M |
| 3 | Dispatch and forget | test_queue: `--dispatch` starts it and splits the queue; `--forget` relinks; the prompt's `d` | 2 | S |
| 4 | Sweeps as chains | test_queue/test_live: a detached sweep makes N entries chained; attached follows them; the in-process sweep runs one after another | 2 | M |
| 5 | Docs | live doc run-queue; runs-listing updated; fast suite as before | 4 | S |

## Decision log

| Decision | Chosen | Why |
|---|---|---|
| Who starts a queued run | its own waiting worker | survives a predecessor that crashes or is killed, which never runs its finish |
| Predecessor not done | failed/lost start it; stopped holds; paused waits (developer) | as a sweep let a failure pass; a stop is the user's word |
| Dispatch in the middle | it heads a queue of its own, its followers with it (developer) | |
| Forget | relinks the follower to the forgotten run's predecessor (developer) | |
| Sweep | a chain, each started on the previous one's end (developer); V75's pipelining retires | each configuration its own run, entry and log |
| Relinking | each waiter rewrites only its own entry | the registry keeps one writer per entry |
| Queue steps' record | the run's log only, not `run.jsonl` | a queued run has no record until its turn (deviation from the design line) |
| Budget, shared view | removed with `_pipelined` | nothing else used them |

## Always / Never

- Always: one writer per entry; a waiter costs a sleeping process, nothing else.
- Never: start a queued run whose predecessor was stopped without a dispatch; write another run's entry.

## Progress

| Phase | Status |
|---|---|
| Plan | approved 2026-11-08 |
| 1 | done 2026-11-08: test_queue states, chain order, listing |
| 2 | done: wait_turn, `--queued-to` (test_queue) |
| 3 | done: `--dispatch`, `--forget`, `d` (test_queue) |
| 4 | done: queue_sweep; `_pipelined`, `execute.Budget` retired; test_queue chain tests, integration `test_a_detached_sweep_is_a_queue_its_runs_one_after_another` (real workers) |
| 5 | docs done: live/run-queue.md, runs-listing, live-parallelism; MAP and reference regenerated; fast suite pending |
