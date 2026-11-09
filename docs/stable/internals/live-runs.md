---
id: live-runs
summary: a run as a worker and a client; the run registry, an entry and its state as values; signals, pausing, resuming, again, jobs, the listing
code: framework/runner/runs.py, framework/runner/cli.py, framework/runner/watch.py, framework/runner/house.py
---

# Live runs

Runs that wait for another run, and a sweep as such a queue, are on [the run queue](run-queue.md).

## Worker and client

On a terminal (`cli.live`: a terminal in and out, its foreground, not `--plain`, not a Slurm job, `HEIMDALL_DETACH` not `never`), `heimdall run` starts the command again with `--worker <id>` (`runs.spawn`: `start_new_session`, stdin from /dev/null, output in `runs/<id>.log`) and follows it as `heimdall watch` does. The worker has no terminal, so only signals reach it.

Keys (`watch.Keys`, put back on leaving, at exit, on SIGTERM and Ctrl-Z): `d` leaves it running; `p` sends SIGUSR1; Ctrl-C is sent on to the worker. The client takes the worker's exit code; a worker killed by a signal has its entry finished by the client. `--detach` waits for `run started`. A SIGKILLed client leaves the terminal unechoed: `reset` mends it.

In `heimdall watch`: `d` or Ctrl-C leaves; `q` sends one SIGINT; `p` sends SIGUSR1; the last two are refused for another PID namespace's pid. `heimdall stop` signals from the command line and waits until the pid ends. `watch.follow` drops an escape sequence whole, so an arrow key is no letter.

## Stopping and pausing

| Signal | First | Second | Third |
|---|---|---|---|
| SIGINT, SIGTERM, SIGHUP | tools get SIGINT, then SIGTERM after 2 s, SIGKILL after 5 s more; exit 6; rerunning resumes | hard stop: SIGKILL at once, still recorded | default: dies with no bookkeeping |
| SIGUSR1 (`p`) | pause: nothing more begins, running points end, exit 6 with `state = "paused"` | force pause: running points stopped as by a hard stop, still paused | |

`Stopper.halted` is read wherever a dispatch would begin: `run_points`, a point lock's wait, combine's groups, `run_one` before each stage, a sweep's runs. A SIGINT after a pause is a stop; after a force pause it does not kill the process, the next does. After a stop, SIGUSR1 does nothing. A run started with SIGHUP ignored (`nohup`) keeps ignoring it, and `cli.catch_signals` leaves that handler alone. While planning, Ctrl-C ends with exit 6, no traceback.

## The registry

`runs.py`, `<Himinbjorg>/runs/<id>.json`: an entry per run and cluster submission, written whole by one writer: at start and end of each run, progress at most every 2 s (`Recorder.EVERY`). Never under a read-only root. Read only when its file's name has an id's shape and the entry is yours; a path it names is never deleted (V191). Kept 30 days, with its log and the control and queue asks beside it (`runs.prune`).

**An entry is a value.** `runs.entry()` and `runs.entries()` return a `runs.RunEntry`, parsed once from the file: typed fields for every key a run writes (`records`, `parallelism`, `point_cores`, `points_failed`, `counts`, what became of a pause: `resumed_by`, `forgotten`), its queue keys as `entry.queue`, and `extra` for any key this version does not know. `entry.as_dict()` gives back what was read, key for key. Readers (the state, `alive`, `queue_of`, `paused`, `again`, the listing, the actions of `heimdall runs`) take a `RunEntry`; writers (`runs.update`, `finish`, the `Recorder`) write dicts, a field at a time.

**Versions.** `runs.VERSION` is 2, written by `begin` as `v`; an entry with `v` 1 or none reads and acts as before. A newer one (`RunEntry.newer`) is listed with ` (newer Heimdall)` after its state and never acted on: `stop`, `--resume`, `--again`, `--dispatch`, `--forget`, `--resume-queue`, `--jobs` and the keys of `runs -i` refuse it (`cli.refuse_newer`), since an old reader must not act on a meaning it does not know.

**State is a value too.** `runs.state_of(entry, live)` returns a `runs.RunState`: logic reads its `word`, one of `runs.STATES`, and the screen prints its `text` (`done, resumed`, `lost, resumed`, `running (not reachable from here)`, `exit 3`, `on <host>`), so rewording a text changes nothing a program does. The word comes from the entry's fields: its `state`, else the first part of its `verdict` when that is a state word, else the verdict its exit code has, else `exit`. A verdict of free text (`the runner failed: …`) gets the word its code gives (`not run`, `exit`) and prints as written; a finished entry with no verdict, no state and an unlisted code is `ended`. `lost` is a process gone with no verdict (no such pid, another start time, another boot); `unknown`, one on another host or in another PID namespace, which this process cannot tell. `RunState` also holds `shown`, `detail`, `resumed`, `forgotten`, `reachable` and `ended`. `heimdall runs --state` takes the words (`forgotten` is a queued run that left its queue unrun; a paused run that was forgotten is `paused`). A pid's start time (`runs.started_at`, how a reused pid is told from the run's own) is `/proc/<pid>/stat`'s on Linux and where that cannot be read `ps -o lstart=`'s text, or `""`.

**Progress:** `cli._runs` plans every run first and hands the `Recorder` each one's point count. A point ended counts once per run key; stage events carry their stage and are not points. An entry finishes with `counts`, `points_completed`, `points_total`, `active_parallel_points`, `configuration_serials`, `configuration_tags`.

## The live list and its block

`house.live_entries`: jobs still going and pauses neither resumed nor forgotten, ordered by when they began (a resumed run by its chain's first start). `heimdall runs` numbers it; `watch -i N`, `stop -i N`, `runs --resume N`, `--forget N` take the Nth of the same list, made again per command (`cli.live_at`). A history list (`--5` … `--50`, `--week`, `--month`) names each run by its id, with its `[N]` too when it is live.

`house.runs_listing` writes a block a run: the index, host, the work dir's title and the config (cut to `house.CONFIG_WIDTH` characters, its end kept); the start and span; the records, each `<A>/<E>` under `records/` with its Runs (a library entry counted: `<A>/library · N entries`), kept by the entry as the run goes, else read from the config snapshot's folder; the state line (the state, the points ongoing, the points ended of those planned, `NULL` where an entry did not record it, `(1 failed)` while it runs and its counts when it ended, and for a queued run `after [N] …tail` and `queue …tail k of n`); the commands that fit it (`--resume N · --forget N` for a pause, `--again <id>` for a failed, stopped or lost run, `--dispatch N · --forget N` for a queued one, `heimdall watch --pid P · heimdall stop --pid P` for a running one); and its log. Colour only on a terminal, without `--plain`, `NO_COLOR` or `TERM=dumb` (`house.wants_colour`), as plain SGR codes (`house.paint`, not a library: `[N]` is markup to one and a path may hold brackets); the log is an OSC 8 link to `file://<the entry's host>/…` (`house.link`). Without colour the words are the same.

`heimdall runs -i N|ID` shows a run's block and, on a terminal, the keys that fit it (`cli.offered`): `w` watch, `s` stop, `j` jobs for a running one; `r` resume, `f` forget for a paused one; `d` dispatch, `s`, `f` for a queued or held one; `a` run again for a failed, stopped or lost one; `q`. The keys that change something ask for their word typed (`stop`, `resume`, `again`, `dispatch`, `forget`), and anything else cancels. Off a terminal the block is printed alone. Each action is a flag too, which acts without the prompt. `stop -i N` stops the running live run as `stop --pid` does; a paused, cluster or ended one is refused, saying what to do (`cli.running_at`).

## Resuming and running again

`--resume N` (`cli.resume_run`) and `--again ID|N` (`cli.again_run`) share `cli.relaunch_entry`: the entry's own command (`runs.again`: its `argv` without `--worker`, `--queued-to` and `--detach`, a `--rerun` becoming `--rerun-since <start>`, then `--detach`), by the entry's checkout, from its work dir, through `runs.relaunch`, over the config snapshot of the entry's latest record (`resume_snapshot`: its `config/snapshot.toml` and errand file, never the live `configs/`; a missing or unreadable one refuses, with the command to run by hand, V235). The new id is chosen first and handed over as `$HEIMDALL_RUN_ID`. A resume marks the paused entry `resumed_by` first (its worker clears it again if it never runs), so the entry leaves the live list; `--again` leaves the old entry as it is and is refused, with the state, for a run that goes, is paused or is a cluster submission. `--forget` writes `forgotten`; nothing is deleted. A resumed `--rerun` keeps a cut-off (`--rerun-since`, `record.stale`), so what the paused job ran itself is not run again.

## Points at once, while it runs

`heimdall runs -i N --jobs M` (or `j` at the prompt) changes a running job's points at once. It writes `runs/<id>.control.json` (`runs.write_control`: `parallelism`, `by`, `at`, whole and atomically) and sends the worker SIGUSR2, only to a job of this user in this PID namespace; a paused, ended or cluster run is refused. `M` is 1 to `Stopper.CEILING` (256); a note says so when `M` times the costliest point's cores (`point_cores`) exceeds the machine's. The worker catches SIGUSR2 beside SIGUSR1 (`cli.catch_control`; a spawned worker ignores it until then). The handler only sets `Stopper.control`; a daemon thread (`cli.control_thread`, `cli.apply_control`) reads the file and calls `Stopper.set_parallelism`, writes the entry's `parallelism` and a `parallelism` event, which `run.jsonl` keeps and the views say. A missing or bad file, or an `M` over the ceiling, is ignored with a note in the log. The cap is `Stopper.cap(configuration.parallelism)`: the live number once given (for later configurations of a sweep in one process too; each run of a queued sweep takes its own), else the configuration's; `execute.run_points` reads it at every dispatch, and there is no serial branch: a run at 1 is a pool of one, made for the ceiling with its threads made as points start. Raising starts more points within half a second; lowering starts none until fewer than `M` run, and stops none. Parallelism is in no identity.
