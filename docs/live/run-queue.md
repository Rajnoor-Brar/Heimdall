---
id: live-run-queue
summary: heimdall run … --queued-to ID|N starts a run when another ends; a sweep is such a queue; runs shows queues, --dispatch starts one early
affects: live-runs
---

**Now holds:** `heimdall run CONFIG [cfg] --queued-to ID|N` checks the run now (every configuration planned: a config error refuses it, nothing starts) and starts it detached as a worker that waits (`cli.queue_run`, then `cli.wait_turn` in the worker). `N` is the live list's `[N]`, `ID` an id or its tail. It is refused after a run that has ended (not paused) or is lost (it would start at once: run it so), after a cluster submission, and with `--plan`, `--why`, `--show-config` or `--only plot`. `runs.again` leaves `--queued-to` out, so `--resume` and `--again` never queue.

**The entry** of a queued run: `queued_to` (the run it waits for), `queue` (the queue's id, its first run's, taken from its predecessor), `queued` (true while it waits), `held` (its predecessor was stopped), then at its turn `began` (the time it left the queue; `started` stays the time it was queued). `runs.state` reads a live entry with `queued` as `queued`, or `held` with `held`; a waiter whose process died is `lost`, as any run. Both are live: in the live list with `[N]`, coloured blue (queued) and yellow (held).

**Waiting.** The worker reads its predecessor's entry every `runs.QUEUE_POLL` (5) seconds and says each step in its log (`HH:MM:SS  queue: …`):

| The predecessor | The waiter |
|---|---|
| done, failed, not run, lost, forgotten, any other end | starts |
| stopped (or paused and forgotten) | held, until `--dispatch` |
| paused | waits; a resume (`resumed_by`) is followed to the new run |
| forgotten while queued (`left_queue`) | waits for that run's own predecessor (or starts, if it was the head) |
| its `queue` changed (a dispatch above) | takes the new `queue` |

Each waiter writes only its own entry. A waiter stopped (Ctrl-C, `heimdall stop`) ends `stopped`, so the runs after it are held. At its turn the run plans and runs as any detached run, and when it ends its log names what it lets start (`queue: <id> starts now`, `held`, `waits`).

**Dispatch and forget.** `heimdall runs --dispatch ID|N`, or `d` at `runs -i N` (the word `dispatch` typed), asks a queued or held run to start now (`runs.ask_queue`: `runs/<id>.queue.json`, read by its waiter): it keeps its `queued_to` as `dispatched_from` and heads a queue of its own (`queue` = its id), and the runs after it follow it there. `heimdall runs --forget ID|N` (or `f`) on a queued or held run ends it unrun (verdict `forgotten`, `left_queue`), and the run after it waits for its predecessor. Anything else is refused (`… is running, not queued`). `runs -i N` on a queued or held run offers `d`, `s` (stop: it ends unrun, stopped), `f` and `q`; `watch -i N` is refused until its turn (`nothing is watched until its turn`).

**Sweeps.** A sweep of runs (`[errand].sweep_runs`) with `--detach`, or followed on a terminal, is a queue (`cli.queue_sweep`): every configuration is checked first (a config error anywhere starts nothing, and `--points` is refused as for any sweep), then one worker a configuration (a hidden `--sweep-member KEY`), the first running and each next queued to the one before, each its own run, entry, `[N]` and log. `--queued-to` with a sweep queues its first to that run. Followed, the terminal follows each run in turn (`cli.follow_worker`); `d` leaves them all going; a run stopped holds the rest, and the terminal says how to dispatch the next. Without a terminal (`--plain`, a worker, a pipe) the sweep runs its configurations in its process, one after another, as before.

**In `heimdall runs`** a run in a queue has, on its state line, `after [N] …tail` (queued and held runs: the run it waits for) and `queue …tail k of n` (its queue's tail and its place, `runs.queue_of`: the chain from the queue's head by `queued_to`). A queued or held run's last lines are `pid P : heimdall runs --dispatch N · heimdall runs --forget N` and its log.

```
[2] lab | <work dir> | Demo/jets
    11-08 12:00 · 3m
    Demo/jets · pdf
    queued · after [1] …aaaa · NULL/NULL · queue …aaaa 2 of 3
    pid 4242 : heimdall runs --dispatch 2 · heimdall runs --forget 2
    log runs/20261108-120001-pp-bbbb.log
```

**No longer holds:** a sweep of runs pipelined in one process (V75, `cli._pipelined`): the next run starting once the one before had started all its points, the runs sharing one cores `execute.Budget`, one view and one watch socket. `execute.Budget`, `run_points`'s `budget` and `started_all`, `run_one`'s `shown`, `budget` and `gate`, and `Stopper.on_parallelism` are gone. A sweep in one process is not overlapped any more.

**Decisions:** the developer's (2026-11-08): a sweep is a chain started on each end, each run its own; a failed predecessor lets the next start, a stopped one holds it; a dispatch in the middle splits the queue, its followers going with it (C keeps B); a forget relinks. A queued run is its own waiting worker, not started by its predecessor, so a predecessor that crashes or is killed (and never runs its finish) still lets it start (`lost`). The waiter asks nothing of the predecessor's process, so the registry keeps one writer per entry. A waiter costs a sleeping process. Queue steps are said in the run's log, not in `run.jsonl` (its record does not exist until its turn).

**Stable pages need:** `internals/live-runs.md` (the entry's queue fields, queued and held, `queue.json`, `--dispatch`), `internals/run-flow.md` (a sweep as a queue; the pipelined paragraph goes), `guide/sweeps.md` (Several configurations: a queue, not pipelined), `guide/watching.md` (`--queued-to`, `--dispatch`, `d`), `design/decisions/quantities.md` (V75's pipelined sweep superseded).
