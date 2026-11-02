---
id: live-runs
summary: a run as a worker and a client; the run registry; signals, pausing, resuming, heimdall watch and stop
code: framework/runner/runs.py, framework/runner/cli.py, framework/runner/watch.py, framework/runner/house.py
---

# Live runs

## Worker and client

On a terminal (`cli.live`: a terminal in and out, its foreground, not `--plain`, not a Slurm job, `HEIMDALL_DETACH` not `never`), `heimdall run` starts the command again with `--worker <id>` (`runs.spawn`: `start_new_session`, stdin from /dev/null, output in `runs/<id>.log`) and follows it as `heimdall watch` does. The worker has no terminal, so only signals reach it.

Keys (`watch.Keys`, put back on leaving, at exit, on SIGTERM and Ctrl-Z): `d` leaves it running; `p` sends SIGUSR1; Ctrl-C is sent on to the worker. The client takes the worker's exit code; a worker killed by a signal has its entry finished by the client. `--detach` waits for `run started`. A SIGKILLed client leaves the terminal unechoed: `reset` mends it.

In `heimdall watch`: `d` or Ctrl-C leaves; `q` sends one SIGINT; `p` sends SIGUSR1; the last two are refused for another PID namespace's pid. `heimdall stop` signals from the command line and waits until the pid ends. `watch.follow` drops an escape sequence whole, so an arrow key is no letter.

## Stopping and pausing

| Signal | First | Second | Third |
|---|---|---|---|
| SIGINT, SIGTERM, SIGHUP | tools get SIGINT, then SIGTERM after 2 s, SIGKILL after 5 s more; exit 6; rerunning resumes | hard stop: SIGKILL at once, still recorded | default: dies with no bookkeeping |
| SIGUSR1 (`p`) | pause: nothing more begins, running points end, exit 6 with `state = "paused"` | force pause: running points stopped as by a hard stop, still paused | |

`Stopper.halted` is read wherever a dispatch would begin: `run_points`, a point lock's wait, combine's groups, `run_one` before each stage, both sweeps. A SIGINT after a pause is a stop; after a force pause it does not kill the process, the next does. After a stop, SIGUSR1 does nothing. A run started with SIGHUP ignored (`nohup`) keeps ignoring it. While planning, Ctrl-C ends with exit 6, no traceback.

## The registry

`runs.py`, `<machine root>/runs/<id>.json`: an entry per run and cluster submission, written whole by one writer: at start and end of each run, progress at most every 2 s (`Recorder.EVERY`). Never under a read-only root. Read only when its file's name has an id's shape and the entry is yours; a path it names is never deleted (V191). Kept 30 days.

**State** (`runs.state`, `runs.alive`): once finished, `paused` or its verdict; `lost` when its process is gone with no verdict (no such pid, another start time, another boot); `on <host>` or `in another PID namespace` when this process cannot tell.

**Progress:** `cli._runs` plans every run first and hands the `Recorder` each one's point count. A point ended counts once per run key; stage events carry their stage and are not points. An entry finishes with `counts`, `points_completed`, `points_total`, `active_parallel_points`, `configuration_serials`, `configuration_tags`.

## The live list

`house.live_entries`: jobs still going and pauses neither resumed nor forgotten, ordered by when they began (a resumed run by its chain's first start). `heimdall runs` numbers it; `watch -i N`, `runs --resume N` and `--forget N` take the Nth of the same list, made again per command (`cli.live_at`).

`--resume` (`cli.resume_run`) runs `runs.again` (the entry's `argv` without `--worker` and `--detach`, then `--detach`) by the entry's checkout, from its work dir, through `runs.relaunch`. The new id is chosen first and handed over as `$HEIMDALL_RUN_ID`, then the paused entry gets `resumed_by`. `--forget` writes `forgotten`; nothing is deleted.

A resumed `--rerun` keeps a cut-off (`--rerun-since`, `record.stale`), so what the paused job ran itself is not run again.
