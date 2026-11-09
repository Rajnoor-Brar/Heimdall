---
id: run-queue
summary: a run queued to another waits for it; a sweep of runs is such a queue; dispatch, forget and a queue lost to a reboot
code: framework/runner/runs.py, framework/runner/cli.py
---

# The run queue

`heimdall run CONFIG [cfg] --queued-to ID|N` checks the run now (every configuration is planned: a config error refuses it and nothing starts) and starts it detached as a worker that waits (`cli.queue_run`, then `cli.wait_turn` in the worker). `N` is the live list's `[N]` ([live runs](live-runs.md)), `ID` an id or its tail. It is refused after a run that has ended (not paused) or is lost (it would start at once: run it so), after a cluster submission, and with `--plan`, `--why`, `--show-config` or `--only plot`. `runs.again` leaves `--queued-to` out, so `--resume` and `--again` never queue.

## The entry

A queued run's entry has `queued_to` (the run it waits for), `queue` (the queue's id: its first run's, taken from its predecessor), `queued` (true while it waits), `held` (its predecessor was stopped) and, at its turn, `began` (the time it left the queue; `started` stays the time it was queued). The state words are `queued` and `held`; a waiter whose process died is `lost`, as any run. Both are live: in the live list with an `[N]`, blue and yellow. In `heimdall runs` a queued run has `after [N] …tail` and `queue …tail k of n` on its state line (`runs.queue_of`: the chain from the queue's head by `queued_to`), then `pid P : heimdall runs --dispatch N · heimdall runs --forget N` and its log.

## Waiting

The worker reads its predecessor's entry every `runs.QUEUE_POLL` seconds and says each step in its log (`HH:MM:SS  queue: …`). What it does follows the predecessor's state word (`runs.RunState.gives_turn` and `holds`; the word, not its text):

| The predecessor | The waiter |
|---|---|
| done, failed, not run, lost, forgotten, any other end | starts |
| stopped (or paused and forgotten) | is held, until `--dispatch` |
| paused | waits; a resume (`resumed_by`) is followed to the new run |
| forgotten while queued (`left_queue`) | waits for that run's own predecessor, or starts when it was the head |
| its `queue` changed (a dispatch above) | takes the new `queue` |

Each waiter writes only its own entry. A waiter stopped (Ctrl-C, `heimdall stop`) ends `stopped`, so the runs after it are held. At its turn the run plans and runs as any detached run; when it ends its log says what it lets start (`queue: <id> starts now`, `held`, `waits`).

## Dispatch and forget

`heimdall runs --dispatch ID|N` (`d` at `runs -i N`) asks a queued or held run to start now (`runs.ask_queue`: `runs/<id>.queue.json`, read by its waiter). It keeps its `queued_to` as `dispatched_from` and heads a queue of its own (`queue` is its id), and the runs after it follow it there. `heimdall runs --forget ID|N` (`f`) on a queued or held run ends it unrun (verdict `forgotten`, `left_queue`), and the run after it waits for its predecessor. Anything else is refused. `watch -i N` on a queued run is refused until its turn.

## A queue lost to a reboot

After a reboot every waiter reads `lost`, and the next run would start with nothing before it. `heimdall runs --resume-queue ID|N` (`cli.resume_queue`; `ID|N` names any run of the queue) walks the queue in order and relaunches each `lost` run not relaunched before, detached, as `--resume` does (`relaunch_entry`): the lost entry gets `resumed_by` and reads `lost, resumed`, and a waiter after it waits for the new run. A run that began is relaunched from its record's config snapshot; one that never began has no record, so it runs its own argv against today's `configs/`, and the command says so. Each relaunched run is queued to the nearest earlier run that is live after the command (a relaunched one, or an original running, queued or held), or starts at once. Done, failed, stopped, paused and forgotten runs are left alone and listed. A queue with no lost run, a cluster submission and an entry from a newer Heimdall are refused, and the command stops at the first relaunch that fails. `--queued-to` on a run already queued is not built.

## A sweep is a queue

A sweep of runs (`[errand].sweep_runs`) with `--detach`, or followed on a terminal, is a queue (`cli.queue_sweep`): every configuration is checked first (a config error anywhere starts nothing; `--points` is refused as for any sweep), then one worker a configuration (a hidden `--sweep-member KEY`), the first running and each next queued to the one before, each its own run, entry, `[N]` and log. `--queued-to` with a sweep queues its first to that run. A worker whose entry has not begun within `runs.BEGIN_WAIT` seconds, here or in `--queued-to`, is ended (`cli._begun`: a queued one is asked to forget, then sent SIGTERM if still there), and its log's tail is said; a sweep then forgets the runs queued before it, and its first run, already going, runs on. Followed, the terminal follows each run in turn (`cli.follow_worker`): `d` leaves them all going, and a run stopped holds the rest, the terminal saying how to dispatch the next. Without a terminal (`--plain`, a worker, a pipe) the sweep runs its configurations in its own process, one after another.

A sweep is not pipelined: the runs do not overlap, share no cores budget, view or watch socket, and each is followed alone.

## Why this way

A queued run is its own waiting worker, not started by its predecessor, so a predecessor that crashes or is killed and never finishes still lets it start (`lost`). The waiter asks nothing of the predecessor's process, so the registry keeps one writer per entry. A waiter costs a sleeping process. Steps are said in the run's log, not in `run.jsonl`, whose record does not exist until its turn.
